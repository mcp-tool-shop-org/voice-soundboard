"""
Voice Mock - Mock TTS backend for testing.

Features:
    - Configurable output
    - Call recording
    - Failure injection
"""

from __future__ import annotations

import time
import struct
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from voice_soundboard.graph import ControlGraph
from voice_soundboard.engine.base import BaseTTSBackend


@dataclass
class CallRecord:
    """Record of a mock backend call."""
    
    method: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    graph: ControlGraph | None = None
    result: Any = None
    error: Exception | None = None
    
    @property
    def text(self) -> str:
        """Get synthesized text from graph."""
        if self.graph:
            return " ".join(t.text for t in self.graph.tokens if t.text.strip())
        return ""


@dataclass
class MockConfig:
    """Configuration for mock backend."""
    
    # Output settings
    sample_rate: int = 24000
    output_type: str = "silence"  # silence, tone, noise, pattern
    
    # Tone settings (if output_type == "tone")
    tone_frequency: float = 440.0
    tone_amplitude: float = 0.5
    
    # Timing
    duration_per_char: float = 0.05  # 50ms per character
    min_duration: float = 0.1
    max_duration: float = 60.0
    
    # Latency simulation
    latency_ms: float = 0.0
    latency_variance: float = 0.0
    
    # Failure injection
    fail_rate: float = 0.0  # 0-1, fraction of calls to fail
    fail_error: Exception | None = None


class VoiceMock(BaseTTSBackend):
    """
    Mock TTS backend for testing.
    
    Example:
        # Basic usage
        mock = VoiceMock()
        engine = VoiceEngine(Config(backend=mock))
        result = engine.speak("Hello!")
        
        # Verify calls
        assert mock.call_count == 1
        assert mock.last_call.text == "Hello!"
        
        # Configure output
        mock = VoiceMock(MockConfig(
            output_type="tone",
            tone_frequency=440,
            latency_ms=100,
        ))
        
        # Inject failures
        mock.configure(fail_rate=0.5)
    """
    
    def __init__(
        self,
        config: MockConfig | None = None,
        output_type: str = "silence",
        sample_rate: int = 24000,
    ):
        if config:
            self._config = config
        else:
            self._config = MockConfig(
                output_type=output_type,
                sample_rate=sample_rate,
            )
        
        self._calls: list[CallRecord] = []
        self._name = "mock"
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def sample_rate(self) -> int:
        return self._config.sample_rate
    
    @property
    def calls(self) -> list[CallRecord]:
        """Get all call records."""
        return self._calls
    
    @property
    def call_count(self) -> int:
        """Get number of calls."""
        return len(self._calls)
    
    @property
    def last_call(self) -> CallRecord | None:
        """Get the last call record."""
        return self._calls[-1] if self._calls else None
    
    def configure(self, **kwargs) -> None:
        """Update mock configuration."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
    
    def reset(self) -> None:
        """Clear all call records."""
        self._calls.clear()
    
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Synthesize audio from ControlGraph (mock)."""
        record = CallRecord(
            method="synthesize",
            graph=graph,
        )
        
        try:
            # Simulate latency
            if self._config.latency_ms > 0:
                import random
                latency = self._config.latency_ms
                if self._config.latency_variance > 0:
                    latency += random.uniform(
                        -self._config.latency_variance,
                        self._config.latency_variance,
                    )
                time.sleep(latency / 1000)
            
            # Check for failure injection
            if self._config.fail_rate > 0:
                import random
                if random.random() < self._config.fail_rate:
                    error = self._config.fail_error or RuntimeError("Mock failure")
                    record.error = error
                    self._calls.append(record)
                    raise error
            
            # Generate audio
            duration = self._calculate_duration(graph)
            audio = self._generate_audio(duration)
            
            record.result = audio
            self._calls.append(record)
            
            return audio
            
        except Exception as e:
            record.error = e
            self._calls.append(record)
            raise
    
    def _calculate_duration(self, graph: ControlGraph) -> float:
        """Calculate output duration from graph."""
        # Sum up text length
        text_length = sum(len(t.text) for t in graph.tokens)
        
        # Add pauses
        total_pause = sum(t.pause_before for t in graph.tokens)
        
        # Calculate duration
        duration = text_length * self._config.duration_per_char + total_pause
        
        # Apply limits
        duration = max(self._config.min_duration, duration)
        duration = min(self._config.max_duration, duration)
        
        return duration
    
    def _generate_audio(self, duration: float) -> np.ndarray:
        """Generate mock audio."""
        num_samples = int(duration * self._config.sample_rate)
        
        if self._config.output_type == "silence":
            return np.zeros(num_samples, dtype=np.float32)
        
        elif self._config.output_type == "tone":
            t = np.linspace(0, duration, num_samples, dtype=np.float32)
            return (
                np.sin(2 * np.pi * self._config.tone_frequency * t)
                * self._config.tone_amplitude
            ).astype(np.float32)
        
        elif self._config.output_type == "noise":
            return np.random.uniform(-0.5, 0.5, num_samples).astype(np.float32)
        
        elif self._config.output_type == "pattern":
            # Generate a recognizable pattern for testing
            pattern = np.zeros(num_samples, dtype=np.float32)
            chunk_size = self._config.sample_rate // 10  # 100ms chunks
            
            for i in range(num_samples // chunk_size):
                start = i * chunk_size
                end = min(start + chunk_size, num_samples)
                
                # Alternating high/low values
                if i % 2 == 0:
                    pattern[start:end] = 0.5
                else:
                    pattern[start:end] = -0.5
            
            return pattern
        
        else:
            return np.zeros(num_samples, dtype=np.float32)
    
    def assert_called(self) -> None:
        """Assert that the mock was called."""
        assert self.call_count > 0, "Mock was not called"
    
    def assert_called_once(self) -> None:
        """Assert that the mock was called exactly once."""
        assert self.call_count == 1, f"Mock was called {self.call_count} times, expected 1"
    
    def assert_called_with_text(self, text: str) -> None:
        """Assert that the mock was called with specific text."""
        assert self.call_count > 0, "Mock was not called"
        
        for call in self._calls:
            if call.text == text:
                return
        
        actual_texts = [call.text for call in self._calls]
        assert False, f"Text '{text}' not found in calls. Actual: {actual_texts}"
    
    def get_all_texts(self) -> list[str]:
        """Get all synthesized texts."""
        return [call.text for call in self._calls]
    
    def get_total_duration(self) -> float:
        """Get total duration of all synthesized audio."""
        total = 0.0
        for call in self._calls:
            if call.result is not None:
                total += len(call.result) / self._config.sample_rate
        return total


class StreamingVoiceMock(VoiceMock):
    """Mock backend with streaming support."""
    
    def __init__(
        self,
        config: MockConfig | None = None,
        chunk_size: int = 1024,
    ):
        super().__init__(config)
        self._chunk_size = chunk_size
    
    def synthesize_streaming(self, graph: ControlGraph):
        """Stream mock audio in chunks."""
        # Get full audio
        audio = self.synthesize(graph)
        
        # Yield in chunks
        for i in range(0, len(audio), self._chunk_size):
            yield audio[i:i + self._chunk_size]
