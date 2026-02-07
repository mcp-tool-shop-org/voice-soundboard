"""
Batch Synthesis - Parallel compilation and batched synthesis.

v2.1 Feature (P2): Efficient batch synthesis for multiple texts.

Provides:
- Parallel compilation
- Batched synthesis
- Progress tracking
- Error handling

Usage:
    from voice_soundboard import batch_synthesize
    
    texts = ["Hello", "World", "How are you?"]
    results = batch_synthesize(texts, voice="af_bella")
    
    for result in results:
        print(result.audio_path)
"""

from __future__ import annotations

import concurrent.futures
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Any

import numpy as np

from voice_soundboard.graph import ControlGraph
from voice_soundboard.compiler import compile_request

logger = logging.getLogger(__name__)


@dataclass
class BatchItem:
    """A single item in a batch."""
    index: int
    text: str
    voice: str | None = None
    emotion: str | None = None
    speed: float | None = None
    
    # Results (filled after processing)
    graph: ControlGraph | None = None
    audio: np.ndarray | None = None
    audio_path: Path | None = None
    duration_seconds: float = 0.0
    error: str | None = None
    
    @property
    def success(self) -> bool:
        return self.error is None and self.audio is not None


@dataclass
class BatchResult:
    """Result of batch synthesis."""
    items: list[BatchItem]
    total_time: float
    compile_time: float
    synth_time: float
    
    @property
    def success_count(self) -> int:
        return sum(1 for item in self.items if item.success)
    
    @property
    def failure_count(self) -> int:
        return len(self.items) - self.success_count
    
    @property
    def total_duration(self) -> float:
        return sum(item.duration_seconds for item in self.items if item.success)
    
    def __iter__(self) -> Iterator[BatchItem]:
        return iter(self.items)
    
    def __len__(self) -> int:
        return len(self.items)
    
    def failures(self) -> list[BatchItem]:
        return [item for item in self.items if not item.success]


class BatchSynthesizer:
    """Batch synthesis with parallel compilation.
    
    Efficiently synthesizes multiple texts using parallel
    compilation and batched backend calls.
    
    Example:
        synth = BatchSynthesizer(backend)
        
        texts = ["Hello", "World", "How are you?"]
        result = synth.synthesize(texts, voice="af_bella")
        
        for item in result:
            if item.success:
                play(item.audio)
    """
    
    def __init__(
        self,
        backend,
        *,
        max_workers: int = 4,
        compile_fn: Callable[..., ControlGraph] | None = None,
    ):
        """Initialize batch synthesizer.
        
        Args:
            backend: TTS backend to use
            max_workers: Max parallel compilation threads
            compile_fn: Override compile function (for testing)
        """
        self.backend = backend
        self.max_workers = max_workers
        self._compile_fn = compile_fn or compile_request
    
    def synthesize(
        self,
        texts: list[str],
        *,
        voice: str | None = None,
        emotion: str | None = None,
        speed: float | None = None,
        output_dir: Path | str | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> BatchResult:
        """Synthesize multiple texts.
        
        Args:
            texts: List of texts to synthesize
            voice: Voice ID for all texts
            emotion: Emotion for all texts
            speed: Speed multiplier for all texts
            output_dir: Optional directory to save audio files
            on_progress: Callback(completed, total) for progress updates
        
        Returns:
            BatchResult with all items and statistics
        """
        start_time = time.perf_counter()
        
        # Create batch items
        items = [
            BatchItem(
                index=i,
                text=text,
                voice=voice,
                emotion=emotion,
                speed=speed,
            )
            for i, text in enumerate(texts)
        ]
        
        # Phase 1: Parallel compilation
        compile_start = time.perf_counter()
        self._compile_batch(items)
        compile_time = time.perf_counter() - compile_start
        
        # Phase 2: Sequential synthesis (backends may batch internally)
        synth_start = time.perf_counter()
        self._synthesize_batch(items, output_dir, on_progress)
        synth_time = time.perf_counter() - synth_start
        
        total_time = time.perf_counter() - start_time
        
        logger.info(
            f"Batch complete: {len(items)} items, "
            f"{compile_time:.2f}s compile, {synth_time:.2f}s synth"
        )
        
        return BatchResult(
            items=items,
            total_time=total_time,
            compile_time=compile_time,
            synth_time=synth_time,
        )
    
    def _compile_batch(self, items: list[BatchItem]):
        """Compile items in parallel."""
        def compile_item(item: BatchItem) -> BatchItem:
            try:
                item.graph = self._compile_fn(
                    item.text,
                    voice=item.voice,
                    emotion=item.emotion,
                    speed=item.speed,
                )
            except Exception as e:
                item.error = f"Compilation failed: {e}"
                logger.warning(f"Failed to compile item {item.index}: {e}")
            return item
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(compile_item, item) for item in items]
            concurrent.futures.wait(futures)
    
    def _synthesize_batch(
        self,
        items: list[BatchItem],
        output_dir: Path | str | None,
        on_progress: Callable[[int, int], None] | None,
    ):
        """Synthesize items sequentially."""
        output_path = Path(output_dir) if output_dir else None
        if output_path:
            output_path.mkdir(parents=True, exist_ok=True)
        
        total = len(items)
        for i, item in enumerate(items):
            if item.error:
                continue
            
            if item.graph is None:
                item.error = "No graph (compilation failed)"
                continue
            
            try:
                # Synthesize
                audio = self.backend.synthesize(item.graph)
                item.audio = audio
                item.duration_seconds = len(audio) / self.backend.sample_rate
                
                # Save if output dir specified
                if output_path:
                    import soundfile as sf
                    filename = f"batch_{item.index:04d}.wav"
                    item.audio_path = output_path / filename
                    sf.write(str(item.audio_path), audio, self.backend.sample_rate)
                
            except Exception as e:
                item.error = f"Synthesis failed: {e}"
                logger.warning(f"Failed to synthesize item {item.index}: {e}")
            
            # Progress callback
            if on_progress:
                on_progress(i + 1, total)


def batch_synthesize(
    texts: list[str],
    *,
    voice: str = "af_bella",
    emotion: str | None = None,
    speed: float = 1.0,
    backend: str = "auto",
    output_dir: Path | str | None = None,
    max_workers: int = 4,
) -> BatchResult:
    """Convenience function for batch synthesis.
    
    Creates engine and synthesizes multiple texts.
    
    Args:
        texts: List of texts to synthesize
        voice: Voice ID
        emotion: Emotion name
        speed: Speed multiplier
        backend: Backend name ("auto", "kokoro", "piper", etc.)
        output_dir: Optional directory for audio files
        max_workers: Parallel compilation threads
    
    Returns:
        BatchResult with all items
    
    Example:
        texts = ["Hello", "World", "How are you?"]
        results = batch_synthesize(texts, voice="af_bella")
        
        for item in results:
            if item.success:
                print(f"{item.text}: {item.duration_seconds:.1f}s")
    """
    from voice_soundboard.engine import load_backend
    
    backend_inst = load_backend(backend=backend)
    synth = BatchSynthesizer(backend_inst, max_workers=max_workers)
    
    return synth.synthesize(
        texts,
        voice=voice,
        emotion=emotion,
        speed=speed,
        output_dir=output_dir,
    )
