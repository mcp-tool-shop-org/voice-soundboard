"""
Mock Backend - For testing without GPU/models.

Produces silent audio of appropriate duration for testing.
"""

from __future__ import annotations

import numpy as np

from voice_soundboard.engine.base import BaseTTSBackend
from voice_soundboard.graph import ControlGraph


class MockBackend(BaseTTSBackend):
    """Mock TTS backend for testing.
    
    Produces silent audio (or sine wave) of estimated duration.
    Useful for testing the pipeline without model files.
    """
    
    def __init__(self, generate_silence: bool = True):
        """Initialize mock backend.
        
        Args:
            generate_silence: If True, output silence. If False, output sine wave.
        """
        self._silence = generate_silence
    
    @property
    def name(self) -> str:
        return "mock"
    
    @property
    def sample_rate(self) -> int:
        return 24000
    
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Generate mock audio.
        
        Duration is estimated at ~150ms per word.
        Paralinguistic events add their duration to the total.
        """
        # Estimate duration: ~150ms per word, adjusted by speed
        word_count = sum(len(t.text.split()) for t in graph.tokens)
        pause_time = sum(t.pause_after for t in graph.tokens)
        
        # Add event durations (events are lowered to silence in mock)
        event_time = sum(e.duration for e in graph.events)
        
        duration = (word_count * 0.15 + pause_time + event_time) / graph.global_speed
        num_samples = int(duration * self.sample_rate)
        
        if self._silence:
            return np.zeros(num_samples, dtype=np.float32)
        else:
            # Generate 440Hz sine wave
            t = np.linspace(0, duration, num_samples, dtype=np.float32)
            return 0.3 * np.sin(2 * np.pi * 440 * t)
    
    def get_voices(self) -> list[str]:
        """Mock supports all voices."""
        return []  # Empty = supports all
    
    def supports_voice(self, voice_id: str) -> bool:
        return True  # Accepts any voice
