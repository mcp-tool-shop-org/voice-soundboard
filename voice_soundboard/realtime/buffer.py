"""
Real-time audio buffer with rollback support.

Provides bounded-memory buffering with:
- Ring buffer implementation
- Crossfade for seamless transitions
- Rollback markers for speculative execution
- Statistics for monitoring
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Iterator, Callable
from collections import deque

import numpy as np


@dataclass
class BufferStats:
    """Statistics about buffer usage and performance.
    
    Useful for monitoring and debugging real-time performance.
    """
    
    buffer_fill_ratio: float = 0.0
    """Current fill level as ratio (0.0 - 1.0)."""
    
    samples_written: int = 0
    """Total samples written to buffer."""
    
    samples_read: int = 0
    """Total samples read from buffer."""
    
    samples_dropped: int = 0
    """Total samples dropped due to overflow."""
    
    underruns: int = 0
    """Number of buffer underruns (read from empty buffer)."""
    
    overruns: int = 0
    """Number of buffer overruns (write to full buffer)."""
    
    rollbacks: int = 0
    """Number of rollback operations performed."""
    
    avg_latency_ms: float = 0.0
    """Average latency from write to read."""
    
    peak_latency_ms: float = 0.0
    """Peak latency observed."""
    
    last_update: float = field(default_factory=time.time)
    """Timestamp of last stats update."""


@dataclass
class RollbackMarker:
    """Marker for speculative execution rollback."""
    
    position: int
    """Buffer position at time of marker."""
    
    timestamp: float
    """When the marker was created."""
    
    committed: bool = False
    """Whether this position has been committed (cannot rollback)."""
    
    metadata: dict = field(default_factory=dict)
    """Additional data associated with marker."""


class RealtimeBuffer:
    """Lock-free ring buffer for real-time audio.
    
    Features:
    - Bounded memory with configurable size
    - Rollback support for speculative synthesis
    - Crossfade for seamless audio transitions
    - Thread-safe read/write operations
    
    Args:
        size_samples: Maximum buffer size in samples.
        crossfade_samples: Samples for crossfade transitions.
        sample_rate: Audio sample rate for timing calculations.
    
    Example:
        buffer = RealtimeBuffer(
            size_samples=48000,  # 1 second at 48kHz
            crossfade_samples=480,  # 10ms crossfade
        )
        
        # Write audio
        buffer.write(audio_chunk)
        
        # Read for playback
        for chunk in buffer.read_chunks(chunk_size=1024):
            play(chunk)
    """
    
    def __init__(
        self,
        size_samples: int,
        crossfade_samples: int = 256,
        sample_rate: int = 24000,
    ):
        self._size = size_samples
        self._crossfade = crossfade_samples
        self._sample_rate = sample_rate
        
        # Ring buffer
        self._buffer = np.zeros(size_samples, dtype=np.float32)
        self._write_pos = 0
        self._read_pos = 0
        self._count = 0
        
        # Thread safety
        self._lock = threading.Lock()
        self._write_event = threading.Event()
        
        # Rollback support
        self._markers: deque[RollbackMarker] = deque(maxlen=100)
        self._last_committed_pos = 0
        
        # Statistics
        self._stats = BufferStats()
        self._latency_samples: deque[float] = deque(maxlen=1000)
        
        # Crossfade window
        self._fade_in = np.linspace(0, 1, crossfade_samples, dtype=np.float32)
        self._fade_out = np.linspace(1, 0, crossfade_samples, dtype=np.float32)
    
    @property
    def size(self) -> int:
        """Maximum buffer size in samples."""
        return self._size
    
    @property
    def available(self) -> int:
        """Number of samples available to read."""
        with self._lock:
            return self._count
    
    @property
    def free_space(self) -> int:
        """Number of samples that can be written."""
        with self._lock:
            return self._size - self._count
    
    @property
    def stats(self) -> BufferStats:
        """Get current buffer statistics."""
        with self._lock:
            self._stats.buffer_fill_ratio = self._count / self._size
            self._stats.last_update = time.time()
            if self._latency_samples:
                self._stats.avg_latency_ms = (
                    np.mean(list(self._latency_samples)) / self._sample_rate * 1000
                )
            return BufferStats(**vars(self._stats))
    
    def write(
        self,
        audio: np.ndarray,
        allow_drop: bool = True,
    ) -> int:
        """Write audio samples to buffer.
        
        Args:
            audio: Audio samples as float32 numpy array.
            allow_drop: If True, drop oldest samples when full.
        
        Returns:
            Number of samples actually written.
        """
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        n_samples = len(audio)
        
        with self._lock:
            if n_samples > self._size:
                # Audio larger than buffer, take only the end
                audio = audio[-self._size:]
                n_samples = self._size
                self._stats.samples_dropped += len(audio) - n_samples
            
            space = self._size - self._count
            
            if n_samples > space:
                if allow_drop:
                    # Drop oldest samples to make room
                    to_drop = n_samples - space
                    self._read_pos = (self._read_pos + to_drop) % self._size
                    self._count -= to_drop
                    self._stats.samples_dropped += to_drop
                    self._stats.overruns += 1
                else:
                    # Only write what fits
                    n_samples = space
                    audio = audio[:n_samples]
            
            # Write to ring buffer
            end_pos = (self._write_pos + n_samples) % self._size
            
            if end_pos > self._write_pos:
                # Contiguous write
                self._buffer[self._write_pos:end_pos] = audio
            else:
                # Wrap around
                first_part = self._size - self._write_pos
                self._buffer[self._write_pos:] = audio[:first_part]
                self._buffer[:end_pos] = audio[first_part:]
            
            self._write_pos = end_pos
            self._count += n_samples
            self._stats.samples_written += n_samples
            
            self._write_event.set()
        
        return n_samples
    
    def read(self, n_samples: int, block: bool = False, timeout: float = 1.0) -> np.ndarray:
        """Read audio samples from buffer.
        
        Args:
            n_samples: Number of samples to read.
            block: If True, block until samples are available.
            timeout: Timeout for blocking in seconds.
        
        Returns:
            Audio samples as float32 numpy array.
        """
        if block:
            deadline = time.time() + timeout
            while self.available < n_samples:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self._write_event.wait(timeout=remaining)
                self._write_event.clear()
        
        with self._lock:
            available = min(n_samples, self._count)
            
            if available == 0:
                self._stats.underruns += 1
                return np.zeros(n_samples, dtype=np.float32)
            
            # Read from ring buffer
            result = np.zeros(available, dtype=np.float32)
            end_pos = (self._read_pos + available) % self._size
            
            if end_pos > self._read_pos:
                # Contiguous read
                result[:] = self._buffer[self._read_pos:end_pos]
            else:
                # Wrap around
                first_part = self._size - self._read_pos
                result[:first_part] = self._buffer[self._read_pos:]
                result[first_part:] = self._buffer[:end_pos]
            
            self._read_pos = end_pos
            self._count -= available
            self._stats.samples_read += available
            
            # Pad with zeros if not enough samples
            if available < n_samples:
                self._stats.underruns += 1
                result = np.pad(result, (0, n_samples - available))
            
            return result
    
    def read_chunks(
        self,
        chunk_size: int,
        block: bool = True,
        timeout: float = 1.0,
    ) -> Iterator[np.ndarray]:
        """Iterate over audio chunks.
        
        Args:
            chunk_size: Size of each chunk in samples.
            block: Block until data is available.
            timeout: Timeout for blocking.
        
        Yields:
            Audio chunks as numpy arrays.
        """
        while True:
            chunk = self.read(chunk_size, block=block, timeout=timeout)
            if np.all(chunk == 0) and self.available == 0:
                break
            yield chunk
    
    def create_marker(self, metadata: dict | None = None) -> RollbackMarker:
        """Create a rollback marker at current position.
        
        Returns:
            Marker that can be used for rollback.
        """
        with self._lock:
            marker = RollbackMarker(
                position=self._write_pos,
                timestamp=time.time(),
                metadata=metadata or {},
            )
            self._markers.append(marker)
            return marker
    
    def rollback(self, marker: RollbackMarker) -> int:
        """Rollback buffer to a previous marker.
        
        Args:
            marker: Marker to rollback to.
        
        Returns:
            Number of samples rolled back.
        
        Raises:
            ValueError: If marker is already committed.
        """
        if marker.committed:
            raise ValueError("Cannot rollback to committed marker")
        
        with self._lock:
            # Calculate samples to rollback
            if self._write_pos >= marker.position:
                rolled_back = self._write_pos - marker.position
            else:
                rolled_back = (self._size - marker.position) + self._write_pos
            
            # Apply crossfade at rollback point
            if rolled_back > 0 and rolled_back > self._crossfade:
                fade_start = (marker.position - self._crossfade) % self._size
                for i, fade in enumerate(self._fade_out):
                    pos = (fade_start + i) % self._size
                    self._buffer[pos] *= fade
            
            self._write_pos = marker.position
            self._count = max(0, self._count - rolled_back)
            self._stats.rollbacks += 1
            
            # Remove newer markers
            while self._markers and self._markers[-1].timestamp > marker.timestamp:
                self._markers.pop()
            
            return rolled_back
    
    def commit(self, marker: RollbackMarker) -> None:
        """Commit a marker, preventing rollback past this point.
        
        Args:
            marker: Marker to commit.
        """
        marker.committed = True
        self._last_committed_pos = marker.position
        
        # Mark older markers as committed too
        for m in self._markers:
            if m.timestamp <= marker.timestamp:
                m.committed = True
    
    def clear(self) -> None:
        """Clear the buffer."""
        with self._lock:
            self._buffer.fill(0)
            self._write_pos = 0
            self._read_pos = 0
            self._count = 0
            self._markers.clear()
    
    def apply_crossfade(
        self,
        new_audio: np.ndarray,
        position: int | None = None,
    ) -> np.ndarray:
        """Apply crossfade transition to new audio.
        
        Args:
            new_audio: New audio to fade in.
            position: Position to crossfade from (default: current write pos).
        
        Returns:
            Audio with crossfade applied.
        """
        if len(new_audio) < self._crossfade:
            return new_audio * self._fade_in[:len(new_audio)]
        
        result = new_audio.copy()
        result[:self._crossfade] *= self._fade_in
        return result
