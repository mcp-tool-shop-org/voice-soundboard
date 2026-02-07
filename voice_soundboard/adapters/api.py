"""
Public API Adapter - Backwards compatible with v1.

This module provides the VoiceEngine class that users know and love.
Internally, it uses compiler → engine architecture.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from voice_soundboard.graph import ControlGraph
from voice_soundboard.compiler import compile_request
from voice_soundboard.engine import load_backend, TTSBackend

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Voice Soundboard configuration.
    
    Compatible with v1 Config API.
    """
    output_dir: Path = field(default_factory=lambda: Path.cwd() / "output")
    model_dir: Path = field(default_factory=lambda: Path(os.environ.get("VOICE_SOUNDBOARD_MODELS", "models")))
    device: str = "auto"
    default_voice: str = "af_bella"
    default_speed: float = 1.0
    sample_rate: int = 24000
    backend: str = "auto"
    
    def __post_init__(self):
        self.output_dir = Path(self.output_dir)
        self.model_dir = Path(self.model_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class SpeechResult:
    """Result from speech synthesis.
    
    Compatible with v1 SpeechResult API.
    """
    audio_path: Path
    duration_seconds: float
    generation_time: float
    voice_used: str
    sample_rate: int
    realtime_factor: float
    
    # v2 additions
    graph: ControlGraph | None = field(default=None, repr=False)


class VoiceEngine:
    """Voice Engine - Main TTS interface.
    
    Backwards compatible with v1 API. Internally uses compiler→engine.
    
    Example:
        engine = VoiceEngine()
        result = engine.speak("Hello world!", voice="af_bella")
        print(result.audio_path)
    """
    
    def __init__(self, config: Config | None = None):
        """Initialize the voice engine.
        
        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or Config()
        self._backend: TTSBackend | None = None
    
    def _ensure_backend(self) -> TTSBackend:
        """Lazy-load the backend on first use."""
        if self._backend is None:
            self._backend = load_backend(
                backend=self.config.backend,
                model_dir=self.config.model_dir,
                device=self.config.device,
            )
        return self._backend
    
    def speak(
        self,
        text: str,
        voice: str | None = None,
        preset: str | None = None,
        speed: float | None = None,
        style: str | None = None,
        emotion: str | None = None,
        save_as: str | None = None,
        normalize: bool = True,
    ) -> SpeechResult:
        """Generate speech from text.
        
        Args:
            text: The text to speak
            voice: Voice ID (e.g., "af_bella", "bm_george")
            preset: Voice preset (e.g., "assistant", "narrator")
            speed: Speech speed multiplier (0.5-2.0)
            style: Natural language style (e.g., "warmly", "excitedly")
            emotion: Emotion name (e.g., "happy", "calm")
            save_as: Output filename (auto-generated if not provided)
            normalize: Expand numbers/abbreviations (default True)
        
        Returns:
            SpeechResult with audio path and metadata
        
        Example:
            result = engine.speak("Hello!", voice="af_bella", speed=1.1)
            result = engine.speak("Hello!", style="warmly and cheerfully")
            result = engine.speak("I'm thrilled!", emotion="excited")
        """
        start_time = time.perf_counter()
        
        # 1. Compile request to graph
        # Only use default voice if no other voice source is specified
        effective_voice = voice
        if not voice and not preset and not emotion and not style:
            effective_voice = self.config.default_voice
        
        effective_speed = speed
        if speed is None and not preset and not emotion:
            effective_speed = self.config.default_speed
        
        graph = compile_request(
            text,
            voice=effective_voice,
            preset=preset,
            emotion=emotion,
            style=style,
            speed=effective_speed,
            normalize=normalize,
        )
        
        # 2. Synthesize
        backend = self._ensure_backend()
        synth_start = time.perf_counter()
        audio = backend.synthesize(graph)
        synth_time = time.perf_counter() - synth_start
        
        # 3. Calculate metrics
        duration = len(audio) / backend.sample_rate
        realtime_factor = duration / synth_time if synth_time > 0 else 0
        
        # 4. Save audio
        output_path = self._save_audio(audio, backend.sample_rate, save_as, text, graph.speaker.value)
        
        total_time = time.perf_counter() - start_time
        logger.debug(
            "speak() completed in %.3fs (synth: %.3fs, rtf: %.1fx)",
            total_time, synth_time, realtime_factor
        )
        
        return SpeechResult(
            audio_path=output_path,
            duration_seconds=duration,
            generation_time=synth_time,
            voice_used=graph.speaker.value if isinstance(graph.speaker.value, str) else "custom",
            sample_rate=backend.sample_rate,
            realtime_factor=realtime_factor,
            graph=graph,
        )
    
    def _save_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
        save_as: str | None,
        text: str,
        voice: str,
    ) -> Path:
        """Save audio to file."""
        if save_as:
            filename = save_as if save_as.endswith('.wav') else f"{save_as}.wav"
        else:
            # Generate filename from text hash
            text_hash = hashlib.sha256(text.encode()).hexdigest()[:8]
            filename = f"{voice}_{text_hash}.wav"
        
        output_path = self.config.output_dir / filename
        sf.write(str(output_path), audio, sample_rate)
        
        return output_path
    
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Synthesize directly from a ControlGraph.
        
        For advanced users who want to build graphs manually.
        
        Args:
            graph: Pre-compiled ControlGraph
        
        Returns:
            Audio as float32 numpy array
        """
        backend = self._ensure_backend()
        return backend.synthesize(graph)
    
    def get_voices(self) -> list[str]:
        """Get list of available voices."""
        backend = self._ensure_backend()
        return backend.get_voices()


def quick_speak(
    text: str,
    voice: str = "af_bella",
    speed: float = 1.0,
    output_dir: Path | str = "output",
) -> Path:
    """One-liner TTS.
    
    Args:
        text: Text to speak
        voice: Voice ID
        speed: Speed multiplier
        output_dir: Where to save audio
    
    Returns:
        Path to generated .wav file
    
    Example:
        path = quick_speak("Hello world!")
    """
    config = Config(output_dir=Path(output_dir))
    engine = VoiceEngine(config)
    result = engine.speak(text, voice=voice, speed=speed)
    return result.audio_path
