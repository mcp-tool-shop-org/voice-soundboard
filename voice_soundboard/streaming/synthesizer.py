"""
Incremental Synthesizer - Word-by-word streaming with speculative execution.

v2.1 Feature (P0): The most requested feature.

Architecture:
    LLM output (stream)
            ↓
    IncrementalCompiler
            ↓
    SpeculativeGraph (partial, rollback-capable)
            ↓
    Engine.synthesize()
            ↓
    Audio chunks (immediate playback)
            ↓
    [Rollback + re-synthesize if correction detected]

Key Design Decisions:
    1. Commit boundaries: Commit at punctuation (. , ; : ? !)
    2. Buffer size: 50-100ms (1-2 words) before playback
    3. Rollback strategy: Crossfade to silence, re-synthesize from last commit
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from collections import deque
from typing import Iterator, Callable, Any

import numpy as np

from voice_soundboard.graph import ControlGraph, TokenEvent, SpeakerRef
from voice_soundboard.compiler import compile_request
from voice_soundboard.engine import TTSBackend


# Word boundary pattern - handles punctuation as commit points
WORD_PATTERN = re.compile(r'(\S+)')
COMMIT_PUNCT = re.compile(r'[.!?,;:]$')


@dataclass
class AudioChunk:
    """An audio chunk with rollback metadata.
    
    Attributes:
        audio: PCM audio data (float32)
        sample_rate: Sample rate in Hz
        is_committed: If True, cannot be rolled back
        word_index: Index of the word that generated this chunk
        timestamp_ms: When this chunk was generated
    """
    audio: np.ndarray
    sample_rate: int
    is_committed: bool = False
    word_index: int = 0
    timestamp_ms: float = 0.0
    
    @property
    def duration_ms(self) -> float:
        """Duration of this chunk in milliseconds."""
        return (len(self.audio) / self.sample_rate) * 1000


@dataclass
class RollbackMarker:
    """Marks a position that can be rolled back to.
    
    Rollback markers are placed at commit boundaries (punctuation).
    When a correction is detected, we roll back to the nearest marker.
    """
    word_index: int
    audio_sample_offset: int
    text_so_far: str
    timestamp_ms: float


@dataclass 
class StreamState:
    """Internal state for the streaming synthesizer."""
    words: list[str] = field(default_factory=list)
    pending_text: str = ""
    committed_text: str = ""
    audio_buffer: deque = field(default_factory=lambda: deque(maxlen=100))
    rollback_markers: list[RollbackMarker] = field(default_factory=list)
    total_samples_emitted: int = 0
    current_word_index: int = 0
    start_time: float = field(default_factory=time.time)


class SpeculativeGraph:
    """A partial graph that supports rollback.
    
    Wraps a ControlGraph with rollback markers so we can
    discard synthesized audio if the LLM corrects itself.
    """
    
    def __init__(self, graph: ControlGraph, word_index: int, is_committed: bool = False):
        self.graph = graph
        self.word_index = word_index
        self.is_committed = is_committed
        self.timestamp = time.time()
    
    def commit(self) -> "SpeculativeGraph":
        """Mark this graph as committed (no rollback possible)."""
        return SpeculativeGraph(
            graph=self.graph,
            word_index=self.word_index,
            is_committed=True,
        )
    
    def can_rollback(self) -> bool:
        """Check if this graph can be rolled back."""
        return not self.is_committed


class StreamBuffer:
    """Ring buffer for audio with rollback support.
    
    Holds uncommitted audio chunks and supports rolling back
    to a previous state when corrections are detected.
    
    Design:
        - Fixed max size to prevent memory growth
        - Chunks older than max_buffer_ms are auto-committed
        - Crossfade on rollback to avoid pops
    """
    
    def __init__(
        self,
        sample_rate: int = 24000,
        max_buffer_ms: float = 500.0,
        crossfade_ms: float = 10.0,
    ):
        self.sample_rate = sample_rate
        self.max_buffer_ms = max_buffer_ms
        self.crossfade_ms = crossfade_ms
        self.crossfade_samples = int(sample_rate * crossfade_ms / 1000)
        
        self._chunks: deque[AudioChunk] = deque()
        self._total_samples = 0
        
    def add(self, chunk: AudioChunk) -> list[AudioChunk]:
        """Add a chunk and return any chunks ready for playback.
        
        Chunks become playable when:
        - They are committed, OR
        - Buffer is full (oldest uncommitted becomes committed)
        
        Returns:
            List of chunks ready for playback (committed)
        """
        self._chunks.append(chunk)
        self._total_samples += len(chunk.audio)
        
        # Auto-commit old chunks if buffer is full
        max_samples = int(self.sample_rate * self.max_buffer_ms / 1000)
        ready = []
        
        while self._total_samples > max_samples and self._chunks:
            oldest = self._chunks[0]
            if not oldest.is_committed:
                oldest.is_committed = True
            ready.append(self._chunks.popleft())
            self._total_samples -= len(oldest.audio)
        
        return ready
    
    def commit_all(self) -> list[AudioChunk]:
        """Commit and return all buffered chunks."""
        ready = []
        while self._chunks:
            chunk = self._chunks.popleft()
            chunk.is_committed = True
            ready.append(chunk)
        self._total_samples = 0
        return ready
    
    def rollback_to(self, word_index: int) -> np.ndarray | None:
        """Roll back to a specific word index.
        
        Discards all chunks after the given word index.
        Returns a crossfade-out buffer to smooth the transition.
        
        Args:
            word_index: Roll back to this word's audio
        
        Returns:
            Crossfade buffer if audio was discarded, None otherwise
        """
        discarded = []
        while self._chunks and self._chunks[-1].word_index > word_index:
            chunk = self._chunks.pop()
            self._total_samples -= len(chunk.audio)
            discarded.append(chunk)
        
        if not discarded:
            return None
        
        # Generate crossfade out
        crossfade = self._generate_crossfade_out()
        return crossfade
    
    def _generate_crossfade_out(self) -> np.ndarray:
        """Generate a smooth crossfade to silence."""
        fade = np.linspace(1.0, 0.0, self.crossfade_samples, dtype=np.float32)
        return np.zeros(self.crossfade_samples, dtype=np.float32) * fade
    
    def get_buffer_duration_ms(self) -> float:
        """Get current buffer duration in milliseconds."""
        return (self._total_samples / self.sample_rate) * 1000


class CorrectionDetector:
    """Detects when an LLM corrects itself.
    
    Patterns detected:
    - Repetition with changes: "Hello, how ar—" → "Hello, I'm fine"
    - Explicit corrections: "I mean...", "Actually..."
    - Backspace sequences in text
    
    Conservative by default - only triggers on clear corrections.
    """
    
    # Patterns that indicate correction
    CORRECTION_PATTERNS = [
        re.compile(r'\b(I mean|actually|sorry|wait|no,)\b', re.IGNORECASE),
        re.compile(r'—'),  # Em-dash often indicates interruption
        re.compile(r'\.\.\.'),  # Ellipsis can indicate restart
    ]
    
    def __init__(self, sensitivity: float = 0.5):
        """Initialize detector.
        
        Args:
            sensitivity: 0.0-1.0, higher = more sensitive to corrections
        """
        self.sensitivity = sensitivity
        self._history: list[str] = []
        self._last_committed: str = ""
    
    def feed(self, word: str) -> tuple[bool, int | None]:
        """Check if this word indicates a correction.
        
        Args:
            word: The new word from the stream
        
        Returns:
            (is_correction, rollback_to_word_index)
            If is_correction is True, rollback_to_word_index indicates
            where to roll back to (None = roll back to last commit)
        """
        self._history.append(word)
        
        # Check for explicit correction patterns
        for pattern in self.CORRECTION_PATTERNS:
            if pattern.search(word):
                if self.sensitivity > 0.3:
                    return True, None
        
        # Check for repetition (word appears again after gap)
        if len(self._history) > 3:
            recent = self._history[-4:-1]
            if word.lower() in [w.lower() for w in recent]:
                if self.sensitivity > 0.5:
                    # Find where to roll back to
                    for i, w in enumerate(reversed(self._history[:-1])):
                        if w.lower() == word.lower():
                            return True, len(self._history) - i - 2
                    return True, None
        
        return False, None
    
    def commit(self, text: str):
        """Mark text as committed (rollback point)."""
        self._last_committed = text
        self._history.clear()
    
    def reset(self):
        """Reset detector state."""
        self._history.clear()
        self._last_committed = ""


class IncrementalSynthesizer:
    """Word-by-word streaming synthesizer with rollback support.
    
    The main entry point for v2.1 incremental streaming.
    
    Usage:
        synth = IncrementalSynthesizer(backend)
        
        for word in llm_stream():
            for chunk in synth.feed(word):
                play(chunk)
        
        for chunk in synth.finalize():
            play(chunk)
    
    Features:
        - First audio chunk ≤ 100ms after first word
        - Rollback latency ≤ 50ms
        - No audible glitches on correction
        - Deterministic output (same input → same audio)
    """
    
    def __init__(
        self,
        backend: TTSBackend,
        *,
        voice: str | None = None,
        emotion: str | None = None,
        speed: float = 1.0,
        buffer_ms: float = 100.0,
        enable_rollback: bool = True,
        correction_sensitivity: float = 0.5,
        on_rollback: Callable[[int], None] | None = None,
    ):
        """Initialize the incremental synthesizer.
        
        Args:
            backend: TTS backend to use for synthesis
            voice: Voice ID (e.g., "af_bella")
            emotion: Emotion name (e.g., "happy")
            speed: Speed multiplier
            buffer_ms: Audio buffer before playback (50-100ms recommended)
            enable_rollback: Enable rollback on corrections
            correction_sensitivity: 0.0-1.0, how sensitive to corrections
            on_rollback: Callback when rollback occurs
        """
        self.backend = backend
        self.voice = voice or "af_bella"
        self.emotion = emotion
        self.speed = speed
        self.buffer_ms = buffer_ms
        self.enable_rollback = enable_rollback
        self.on_rollback = on_rollback
        
        self._buffer = StreamBuffer(
            sample_rate=backend.sample_rate,
            max_buffer_ms=buffer_ms * 2,
        )
        self._detector = CorrectionDetector(sensitivity=correction_sensitivity)
        self._state = StreamState()
        self._speculative_graphs: list[SpeculativeGraph] = []
        
        # Metrics
        self._first_word_time: float | None = None
        self._first_audio_time: float | None = None
        self._rollback_count: int = 0
    
    def feed(self, word: str) -> Iterator[AudioChunk]:
        """Feed a word and yield audio chunks.
        
        This is the main streaming interface. Feed words as they
        arrive from the LLM and play the returned chunks.
        
        Args:
            word: A word (or partial word) from the stream
        
        Yields:
            AudioChunk objects ready for playback
        
        Example:
            for word in llm_stream():
                for chunk in synth.feed(word):
                    audio_output.write(chunk.audio)
        """
        if self._first_word_time is None:
            self._first_word_time = time.perf_counter()
        
        # Check for correction
        if self.enable_rollback:
            is_correction, rollback_to = self._detector.feed(word)
            if is_correction:
                yield from self._handle_rollback(rollback_to)
        
        # Add word to state
        self._state.words.append(word)
        self._state.pending_text += word + " "
        self._state.current_word_index = len(self._state.words) - 1
        
        # Check for commit boundary
        is_commit = bool(COMMIT_PUNCT.search(word))
        
        # Synthesize current segment
        graph = self._compile_word(word)
        if graph:
            spec = SpeculativeGraph(
                graph=graph,
                word_index=self._state.current_word_index,
                is_committed=is_commit,
            )
            self._speculative_graphs.append(spec)
            
            for chunk in self._synthesize_graph(spec):
                ready = self._buffer.add(chunk)
                for r in ready:
                    if self._first_audio_time is None:
                        self._first_audio_time = time.perf_counter()
                    yield r
        
        # If commit boundary, mark detector
        if is_commit:
            self._detector.commit(self._state.pending_text)
            self._state.committed_text += self._state.pending_text
            self._state.pending_text = ""
            self._state.rollback_markers.append(RollbackMarker(
                word_index=self._state.current_word_index,
                audio_sample_offset=self._state.total_samples_emitted,
                text_so_far=self._state.committed_text,
                timestamp_ms=time.time() * 1000,
            ))
    
    def finalize(self) -> Iterator[AudioChunk]:
        """Finalize the stream and yield remaining audio.
        
        Call this when the input stream ends to flush
        any remaining buffered audio.
        
        Yields:
            Remaining AudioChunk objects
        """
        # Synthesize any remaining pending text
        if self._state.pending_text.strip():
            graph = compile_request(
                self._state.pending_text.strip(),
                voice=self.voice,
                emotion=self.emotion,
                speed=self.speed,
            )
            spec = SpeculativeGraph(
                graph=graph,
                word_index=self._state.current_word_index,
                is_committed=True,
            )
            for chunk in self._synthesize_graph(spec):
                self._buffer.add(chunk)
        
        # Flush buffer
        for chunk in self._buffer.commit_all():
            yield chunk
        
        # Reset state
        self._detector.reset()
    
    def reset(self):
        """Reset synthesizer state for reuse."""
        self._state = StreamState()
        self._speculative_graphs.clear()
        self._detector.reset()
        self._first_word_time = None
        self._first_audio_time = None
        self._rollback_count = 0
    
    def get_latency_ms(self) -> float | None:
        """Get latency from first word to first audio chunk.
        
        Returns None if no audio has been generated yet.
        """
        if self._first_word_time is None or self._first_audio_time is None:
            return None
        return (self._first_audio_time - self._first_word_time) * 1000
    
    def get_stats(self) -> dict[str, Any]:
        """Get streaming statistics."""
        return {
            "words_processed": len(self._state.words),
            "committed_text": self._state.committed_text,
            "pending_text": self._state.pending_text,
            "rollback_count": self._rollback_count,
            "first_audio_latency_ms": self.get_latency_ms(),
            "buffer_duration_ms": self._buffer.get_buffer_duration_ms(),
        }
    
    def _compile_word(self, word: str) -> ControlGraph | None:
        """Compile a single word to a graph."""
        word = word.strip()
        if not word:
            return None
        
        return compile_request(
            word,
            voice=self.voice,
            emotion=self.emotion,
            speed=self.speed,
        )
    
    def _synthesize_graph(self, spec: SpeculativeGraph) -> Iterator[AudioChunk]:
        """Synthesize a speculative graph to audio chunks."""
        try:
            audio = self.backend.synthesize(spec.graph)
            
            # Split into small chunks for low latency
            chunk_size = int(self.backend.sample_rate * 0.05)  # 50ms chunks
            
            for i in range(0, len(audio), chunk_size):
                chunk_audio = audio[i:i + chunk_size]
                yield AudioChunk(
                    audio=chunk_audio,
                    sample_rate=self.backend.sample_rate,
                    is_committed=spec.is_committed,
                    word_index=spec.word_index,
                    timestamp_ms=time.time() * 1000,
                )
                self._state.total_samples_emitted += len(chunk_audio)
        except Exception as e:
            # Log error but don't crash the stream
            import logging
            logging.getLogger(__name__).warning(f"Synthesis failed for word: {e}")
    
    def _handle_rollback(self, rollback_to: int | None) -> Iterator[AudioChunk]:
        """Handle a detected correction by rolling back.
        
        Args:
            rollback_to: Word index to roll back to, or None for last commit
        
        Yields:
            Crossfade chunk if needed
        """
        self._rollback_count += 1
        
        # Find rollback point
        if rollback_to is None:
            # Roll back to last commit marker
            if self._state.rollback_markers:
                marker = self._state.rollback_markers[-1]
                rollback_to = marker.word_index
            else:
                rollback_to = 0
        
        # Roll back audio buffer
        crossfade = self._buffer.rollback_to(rollback_to)
        if crossfade is not None and len(crossfade) > 0:
            yield AudioChunk(
                audio=crossfade,
                sample_rate=self.backend.sample_rate,
                is_committed=True,
                word_index=rollback_to,
            )
        
        # Roll back state
        self._state.words = self._state.words[:rollback_to + 1]
        self._state.pending_text = " ".join(self._state.words[len(self._state.committed_text.split()):])
        
        # Remove speculative graphs after rollback point
        self._speculative_graphs = [
            g for g in self._speculative_graphs
            if g.word_index <= rollback_to
        ]
        
        # Notify callback
        if self.on_rollback:
            self.on_rollback(rollback_to)
