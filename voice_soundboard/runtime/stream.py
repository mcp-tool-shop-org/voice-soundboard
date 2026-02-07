"""
Streaming Synthesis - Runtime layer for incremental audio generation.

Streaming is a runtime concern, not an engine concern.
The engine produces audio; the runtime decides how to deliver it.
"""

from __future__ import annotations

from typing import Iterator, Callable
from dataclasses import dataclass

import numpy as np

from voice_soundboard.graph import ControlGraph
from voice_soundboard.engine.base import TTSBackend


@dataclass
class StreamConfig:
    """Configuration for streaming synthesis."""
    chunk_duration: float = 0.1  # seconds per chunk
    buffer_ahead: int = 2  # chunks to buffer ahead
    
    @property
    def chunk_samples(self) -> int:
        """Samples per chunk at 24kHz."""
        return int(self.chunk_duration * 24000)


class StreamingSynthesizer:
    """Streaming synthesis wrapper.
    
    Takes graph segments from compiler and yields audio chunks.
    
    Example:
        streamer = StreamingSynthesizer(backend)
        for graph in compile_stream(text_iterator):
            for chunk in streamer.stream(graph):
                play(chunk)
    """
    
    def __init__(
        self,
        backend: TTSBackend,
        config: StreamConfig | None = None,
    ):
        self._backend = backend
        self._config = config or StreamConfig()
    
    def stream(self, graph: ControlGraph) -> Iterator[np.ndarray]:
        """Synthesize and stream audio chunks.
        
        Args:
            graph: ControlGraph to synthesize
        
        Yields:
            Audio chunks as float32 numpy arrays
        """
        # Check if backend supports native streaming
        if hasattr(self._backend, 'synthesize_stream'):
            yield from self._backend.synthesize_stream(
                graph, 
                chunk_size=self._config.chunk_samples
            )
        else:
            # Fall back to synthesize-then-chunk
            audio = self._backend.synthesize(graph)
            yield from self._chunk_audio(audio)
    
    def stream_multi(self, graphs: Iterator[ControlGraph]) -> Iterator[np.ndarray]:
        """Stream from multiple graphs (for incremental compilation).
        
        Args:
            graphs: Iterator of ControlGraphs
        
        Yields:
            Audio chunks, seamlessly across graph boundaries
        """
        for graph in graphs:
            yield from self.stream(graph)
    
    def _chunk_audio(self, audio: np.ndarray) -> Iterator[np.ndarray]:
        """Split audio into chunks."""
        chunk_size = self._config.chunk_samples
        for i in range(0, len(audio), chunk_size):
            yield audio[i:i + chunk_size]


class RealtimeSynthesizer:
    """Real-time synthesis with callback-based output.
    
    For applications that need to push audio to a callback
    (e.g., audio device, WebSocket).
    """
    
    def __init__(
        self,
        backend: TTSBackend,
        on_audio: Callable[[np.ndarray], None],
        config: StreamConfig | None = None,
    ):
        self._backend = backend
        self._on_audio = on_audio
        self._config = config or StreamConfig()
        self._streamer = StreamingSynthesizer(backend, config)
    
    def synthesize(self, graph: ControlGraph) -> None:
        """Synthesize and push audio to callback."""
        for chunk in self._streamer.stream(graph):
            self._on_audio(chunk)
    
    def synthesize_stream(self, graphs: Iterator[ControlGraph]) -> None:
        """Synthesize from graph stream and push to callback."""
        for chunk in self._streamer.stream_multi(graphs):
            self._on_audio(chunk)
