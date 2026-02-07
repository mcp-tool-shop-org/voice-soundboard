"""
Test Fixtures - Common fixtures for testing.

Provides:
    - Sample texts
    - Test audio generation
    - Test graph creation
    - Test engine setup
"""

from __future__ import annotations

import struct
import math
from typing import Any, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from voice_soundboard.graph import ControlGraph
    from voice_soundboard.adapters import VoiceEngine


# Sample texts for testing
SAMPLE_TEXTS = {
    "hello": "Hello, world!",
    "short": "Hi.",
    "medium": "The quick brown fox jumps over the lazy dog.",
    "long": (
        "In a hole in the ground there lived a hobbit. Not a nasty, dirty, "
        "wet hole, filled with the ends of worms and an oozy smell, nor yet "
        "a dry, bare, sandy hole with nothing in it to sit down on or to eat: "
        "it was a hobbit-hole, and that means comfort."
    ),
    "punctuation": "Hello! How are you? I'm fine, thanks.",
    "numbers": "The year is 2024, and I have 42 items.",
    "ssml_like": "<speak>Hello <break time='500ms'/> world!</speak>",
    "multilingual": "Hello! Bonjour! Hallo! こんにちは!",
    "emotional": "I am so happy! This is wonderful! I can't believe it!",
    "question": "What is the meaning of life?",
}


def create_test_audio(
    duration: float = 1.0,
    sample_rate: int = 24000,
    frequency: float = 440.0,
    amplitude: float = 0.5,
    audio_type: str = "tone",
) -> np.ndarray:
    """
    Create test audio data.
    
    Args:
        duration: Duration in seconds
        sample_rate: Sample rate in Hz
        frequency: Frequency for tone (if audio_type == "tone")
        amplitude: Amplitude (0-1)
        audio_type: Type of audio ("tone", "silence", "noise", "speech_like")
        
    Returns:
        Float32 numpy array
    """
    num_samples = int(duration * sample_rate)
    
    if audio_type == "silence":
        return np.zeros(num_samples, dtype=np.float32)
    
    elif audio_type == "tone":
        t = np.linspace(0, duration, num_samples, dtype=np.float32)
        return (np.sin(2 * np.pi * frequency * t) * amplitude).astype(np.float32)
    
    elif audio_type == "noise":
        return np.random.uniform(-amplitude, amplitude, num_samples).astype(np.float32)
    
    elif audio_type == "speech_like":
        # Generate something that looks like speech (modulated noise)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)
        
        # Envelope (simulates speech patterns)
        envelope = np.abs(np.sin(2 * np.pi * 3 * t))  # ~3 Hz modulation
        
        # Carrier (voice-like frequencies)
        carrier = np.sin(2 * np.pi * 150 * t)  # Fundamental ~150 Hz
        carrier += 0.5 * np.sin(2 * np.pi * 300 * t)  # First harmonic
        carrier += 0.25 * np.sin(2 * np.pi * 450 * t)  # Second harmonic
        
        # Combine
        audio = envelope * carrier * amplitude
        
        return audio.astype(np.float32)
    
    else:
        return np.zeros(num_samples, dtype=np.float32)


def create_test_audio_bytes(
    duration: float = 1.0,
    sample_rate: int = 24000,
    **kwargs,
) -> bytes:
    """Create test audio as PCM bytes (int16)."""
    audio = create_test_audio(duration, sample_rate, **kwargs)
    
    # Convert to int16
    audio_int = (audio * 32767).astype(np.int16)
    
    return audio_int.tobytes()


def create_test_graph(
    text: str = "Hello, world!",
    voice_id: str = "default",
    speed: float = 1.0,
    pitch: float = 1.0,
    energy: float = 1.0,
) -> "ControlGraph":
    """
    Create a test ControlGraph.
    
    Args:
        text: Text to synthesize
        voice_id: Voice identifier
        speed: Speed multiplier
        pitch: Pitch multiplier
        energy: Energy multiplier
        
    Returns:
        ControlGraph
    """
    from voice_soundboard.graph import ControlGraph, ControlToken
    
    # Tokenize text (simplified)
    words = text.split()
    tokens = []
    
    for i, word in enumerate(words):
        token = ControlToken(
            text=word,
            speed_scale=speed,
            pitch_scale=pitch,
            energy_scale=energy,
            pause_before=0.1 if i > 0 else 0.0,
        )
        tokens.append(token)
    
    return ControlGraph(
        tokens=tokens,
        voice_id=voice_id,
    )


def create_test_engine(
    backend: str = "mock",
    **config_kwargs,
) -> "VoiceEngine":
    """
    Create a test VoiceEngine.
    
    Args:
        backend: Backend to use ("mock" for testing)
        **config_kwargs: Additional config parameters
        
    Returns:
        Configured VoiceEngine
    """
    from voice_soundboard.adapters import VoiceEngine, Config
    
    config = Config(backend=backend, **config_kwargs)
    return VoiceEngine(config)


class AudioBuilder:
    """
    Fluent builder for test audio.
    
    Example:
        audio = (
            AudioBuilder(sample_rate=24000)
            .add_silence(0.5)
            .add_tone(440, 1.0)
            .add_silence(0.5)
            .add_noise(0.5)
            .build()
        )
    """
    
    def __init__(self, sample_rate: int = 24000):
        self.sample_rate = sample_rate
        self._segments: list[np.ndarray] = []
    
    def add_silence(self, duration: float) -> "AudioBuilder":
        """Add silence."""
        self._segments.append(create_test_audio(
            duration,
            self.sample_rate,
            audio_type="silence",
        ))
        return self
    
    def add_tone(
        self,
        frequency: float,
        duration: float,
        amplitude: float = 0.5,
    ) -> "AudioBuilder":
        """Add a tone."""
        self._segments.append(create_test_audio(
            duration,
            self.sample_rate,
            frequency=frequency,
            amplitude=amplitude,
            audio_type="tone",
        ))
        return self
    
    def add_noise(
        self,
        duration: float,
        amplitude: float = 0.3,
    ) -> "AudioBuilder":
        """Add noise."""
        self._segments.append(create_test_audio(
            duration,
            self.sample_rate,
            amplitude=amplitude,
            audio_type="noise",
        ))
        return self
    
    def add_speech_like(
        self,
        duration: float,
        amplitude: float = 0.5,
    ) -> "AudioBuilder":
        """Add speech-like audio."""
        self._segments.append(create_test_audio(
            duration,
            self.sample_rate,
            amplitude=amplitude,
            audio_type="speech_like",
        ))
        return self
    
    def build(self) -> np.ndarray:
        """Build the final audio array."""
        if not self._segments:
            return np.array([], dtype=np.float32)
        
        return np.concatenate(self._segments)
    
    def build_bytes(self) -> bytes:
        """Build as PCM bytes."""
        audio = self.build()
        audio_int = (audio * 32767).astype(np.int16)
        return audio_int.tobytes()


# Convenience functions
def silence(duration: float, sample_rate: int = 24000) -> np.ndarray:
    """Create silence."""
    return create_test_audio(duration, sample_rate, audio_type="silence")


def tone(
    frequency: float,
    duration: float,
    sample_rate: int = 24000,
    amplitude: float = 0.5,
) -> np.ndarray:
    """Create a tone."""
    return create_test_audio(
        duration,
        sample_rate,
        frequency=frequency,
        amplitude=amplitude,
        audio_type="tone",
    )


def noise(
    duration: float,
    sample_rate: int = 24000,
    amplitude: float = 0.3,
) -> np.ndarray:
    """Create noise."""
    return create_test_audio(
        duration,
        sample_rate,
        amplitude=amplitude,
        audio_type="noise",
    )
