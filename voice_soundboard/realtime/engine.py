"""
Real-Time Engine for Voice Soundboard v2.3.

Provides low-latency synthesis with real-time guarantees.
"""

from __future__ import annotations

import threading
import time
import queue
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Callable, Any
from enum import Enum

import numpy as np

from voice_soundboard.engine.base import TTSBackend
from voice_soundboard.graph import ControlGraph
from voice_soundboard.realtime.config import (
    RealtimeConfig,
    SessionConfig,
    BackpressurePolicy,
    DropPolicy,
)
from voice_soundboard.realtime.buffer import RealtimeBuffer, RollbackMarker


class SessionState(Enum):
    """State of a real-time session."""
    
    IDLE = "idle"
    SYNTHESIZING = "synthesizing"
    INTERRUPTED = "interrupted"
    CLOSED = "closed"


@dataclass
class SynthesisRequest:
    """A request for synthesis in the queue."""
    
    text: str
    priority: int = 0
    marker: RollbackMarker | None = None
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def __lt__(self, other: "SynthesisRequest") -> bool:
        # Higher priority first, then earlier timestamp
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.timestamp < other.timestamp


class RealtimeSession:
    """A real-time synthesis session.
    
    Sessions provide:
    - Continuous audio streaming
    - Interruption handling
    - Priority-based queuing
    - Speculative execution with rollback
    
    Example:
        with engine.session() as session:
            session.speak("Hello")
            session.speak("World", priority=1)  # Higher priority
            
            if user_interrupted:
                session.interrupt()
    """
    
    def __init__(
        self,
        engine: "RealtimeEngine",
        config: SessionConfig | None = None,
    ):
        self._engine = engine
        self._config = config or SessionConfig()
        self._state = SessionState.IDLE
        
        # Request queue (priority queue)
        self._queue: queue.PriorityQueue[SynthesisRequest] = queue.PriorityQueue()
        
        # Current synthesis state
        self._current_request: SynthesisRequest | None = None
        self._current_marker: RollbackMarker | None = None
        
        # Threading
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._interrupt_event = threading.Event()
        
        # Callbacks
        self._on_start: Callable[[str], None] | None = None
        self._on_complete: Callable[[str], None] | None = None
        self._on_interrupt: Callable[[str], None] | None = None
    
    @property
    def state(self) -> SessionState:
        """Current session state."""
        return self._state
    
    @property
    def is_active(self) -> bool:
        """Whether session is actively synthesizing."""
        return self._state == SessionState.SYNTHESIZING
    
    @property
    def queue_depth(self) -> int:
        """Number of requests waiting in queue."""
        return self._queue.qsize()
    
    def speak(
        self,
        text: str,
        priority: int = 0,
        interrupt_current: bool = False,
        metadata: dict | None = None,
    ) -> None:
        """Queue text for synthesis.
        
        Args:
            text: Text to synthesize.
            priority: Priority level (higher = more urgent).
            interrupt_current: Interrupt current synthesis immediately.
            metadata: Additional metadata for this request.
        """
        if self._state == SessionState.CLOSED:
            raise RuntimeError("Session is closed")
        
        request = SynthesisRequest(
            text=text,
            priority=priority,
            metadata=metadata or {},
        )
        
        if interrupt_current and self._state == SessionState.SYNTHESIZING:
            self.interrupt(reason="new_priority_request")
        
        self._queue.put(request)
    
    def interrupt(self, reason: str = "user_request") -> None:
        """Interrupt current synthesis.
        
        Args:
            reason: Reason for interruption (for logging/callbacks).
        """
        if self._state != SessionState.SYNTHESIZING:
            return
        
        self._interrupt_event.set()
        self._state = SessionState.INTERRUPTED
        
        # Rollback to last marker if available
        if self._current_marker and not self._current_marker.committed:
            self._engine._buffer.rollback(self._current_marker)
        
        if self._on_interrupt and self._current_request:
            self._on_interrupt(self._current_request.text)
    
    def clear_queue(self) -> int:
        """Clear all pending requests.
        
        Returns:
            Number of requests cleared.
        """
        count = 0
        try:
            while True:
                self._queue.get_nowait()
                count += 1
        except queue.Empty:
            pass
        return count
    
    def on_start(self, callback: Callable[[str], None]) -> "RealtimeSession":
        """Set callback for synthesis start."""
        self._on_start = callback
        return self
    
    def on_complete(self, callback: Callable[[str], None]) -> "RealtimeSession":
        """Set callback for synthesis completion."""
        self._on_complete = callback
        return self
    
    def on_interrupt(self, callback: Callable[[str], None]) -> "RealtimeSession":
        """Set callback for synthesis interruption."""
        self._on_interrupt = callback
        return self
    
    def _start(self) -> None:
        """Start the session worker thread."""
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="realtime-session-worker",
        )
        self._worker_thread.start()
    
    def _stop(self) -> None:
        """Stop the session worker thread."""
        self._stop_event.set()
        self._state = SessionState.CLOSED
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
    
    def _worker_loop(self) -> None:
        """Main worker loop for processing synthesis requests."""
        while not self._stop_event.is_set():
            try:
                request = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            self._current_request = request
            self._state = SessionState.SYNTHESIZING
            self._interrupt_event.clear()
            
            # Create rollback marker
            self._current_marker = self._engine._buffer.create_marker(
                metadata={"text": request.text}
            )
            
            if self._on_start:
                self._on_start(request.text)
            
            try:
                # Compile and synthesize
                self._engine._process_request(
                    request,
                    self._interrupt_event,
                    self._current_marker,
                )
                
                if not self._interrupt_event.is_set():
                    # Commit the marker on successful completion
                    self._engine._buffer.commit(self._current_marker)
                    
                    if self._on_complete:
                        self._on_complete(request.text)
                    
                    self._state = SessionState.IDLE
            
            except Exception as e:
                # Rollback on error
                if self._current_marker and not self._current_marker.committed:
                    self._engine._buffer.rollback(self._current_marker)
                raise
            
            finally:
                self._current_request = None
                self._current_marker = None
                self._queue.task_done()


class RealtimeEngine:
    """Real-time synthesis engine with latency guarantees.
    
    Provides:
    - Low-latency audio synthesis (<20ms internal buffering)
    - Deterministic scheduling under load
    - Backpressure handling
    - Bounded memory guarantees
    
    Args:
        backend: TTS backend to use for synthesis.
        config: Real-time configuration.
        compiler: Optional custom compiler function.
    
    Example:
        from voice_soundboard.realtime import RealtimeEngine, RealtimeConfig
        
        engine = RealtimeEngine(
            backend=my_backend,
            config=RealtimeConfig(max_latency_ms=50),
        )
        
        with engine.session() as session:
            for word in llm_stream():
                session.speak(word)
            
            for chunk in engine.read_audio():
                play(chunk)
    """
    
    def __init__(
        self,
        backend: TTSBackend,
        config: RealtimeConfig | None = None,
        compiler: Callable[[str, dict], ControlGraph] | None = None,
    ):
        self._backend = backend
        self._config = config or RealtimeConfig()
        self._compiler = compiler or self._default_compiler
        
        # Calculate buffer size from config
        buffer_samples = int(
            self._config.buffer_size_ms * backend.sample_rate / 1000
        )
        crossfade_samples = int(
            10 * backend.sample_rate / 1000  # 10ms crossfade
        )
        
        self._buffer = RealtimeBuffer(
            size_samples=buffer_samples,
            crossfade_samples=crossfade_samples,
            sample_rate=backend.sample_rate,
        )
        
        # Active sessions
        self._sessions: list[RealtimeSession] = []
        self._lock = threading.Lock()
        
        # Statistics
        self._total_requests = 0
        self._total_samples = 0
        self._start_time = time.time()
    
    @property
    def backend(self) -> TTSBackend:
        """The TTS backend."""
        return self._backend
    
    @property
    def config(self) -> RealtimeConfig:
        """Real-time configuration."""
        return self._config
    
    @property
    def sample_rate(self) -> int:
        """Output sample rate."""
        return self._backend.sample_rate
    
    @property
    def buffer_stats(self):
        """Get buffer statistics."""
        return self._buffer.stats
    
    @contextmanager
    def session(
        self,
        config: SessionConfig | None = None,
    ) -> Iterator[RealtimeSession]:
        """Create a real-time synthesis session.
        
        Args:
            config: Optional session-specific configuration.
        
        Yields:
            RealtimeSession for queuing synthesis requests.
        
        Example:
            with engine.session() as session:
                session.speak("Hello world!")
        """
        session = RealtimeSession(self, config)
        
        with self._lock:
            self._sessions.append(session)
        
        try:
            session._start()
            yield session
        finally:
            session._stop()
            with self._lock:
                self._sessions.remove(session)
    
    def speak_immediate(
        self,
        text: str,
        voice: str | None = None,
        **kwargs: Any,
    ) -> int:
        """Synthesize text immediately without session.
        
        Args:
            text: Text to synthesize.
            voice: Optional voice override.
            **kwargs: Additional parameters for compiler.
        
        Returns:
            Number of samples written to buffer.
        """
        graph = self._compiler(text, {"voice": voice, **kwargs})
        audio = self._backend.synthesize(graph)
        return self._buffer.write(audio)
    
    def read_audio(
        self,
        chunk_size: int | None = None,
        block: bool = True,
        timeout: float = 1.0,
    ) -> Iterator[np.ndarray]:
        """Read audio chunks from the buffer.
        
        Args:
            chunk_size: Size of each chunk (default: from config).
            block: Block until audio is available.
            timeout: Timeout for blocking.
        
        Yields:
            Audio chunks as numpy arrays.
        """
        chunk_size = chunk_size or self._config.chunk_size_samples
        yield from self._buffer.read_chunks(
            chunk_size=chunk_size,
            block=block,
            timeout=timeout,
        )
    
    def read_samples(
        self,
        n_samples: int,
        block: bool = True,
        timeout: float = 1.0,
    ) -> np.ndarray:
        """Read a specific number of samples.
        
        Args:
            n_samples: Number of samples to read.
            block: Block until samples are available.
            timeout: Timeout for blocking.
        
        Returns:
            Audio samples as numpy array.
        """
        return self._buffer.read(n_samples, block=block, timeout=timeout)
    
    def clear(self) -> None:
        """Clear all buffers and pending requests."""
        self._buffer.clear()
        for session in self._sessions:
            session.clear_queue()
    
    def health(self) -> dict[str, Any]:
        """Get engine health status.
        
        Returns:
            Dictionary with health information.
        """
        stats = self._buffer.stats
        uptime = time.time() - self._start_time
        
        return {
            "backend": self._backend.name,
            "status": "healthy",
            "buffer_fill": stats.buffer_fill_ratio,
            "samples_processed": self._total_samples,
            "total_requests": self._total_requests,
            "active_sessions": len(self._sessions),
            "underruns": stats.underruns,
            "overruns": stats.overruns,
            "avg_latency_ms": stats.avg_latency_ms,
            "uptime_seconds": uptime,
        }
    
    def _process_request(
        self,
        request: SynthesisRequest,
        interrupt_event: threading.Event,
        marker: RollbackMarker,
    ) -> None:
        """Process a synthesis request.
        
        Internal method called by session workers.
        """
        # Compile
        graph = self._compiler(request.text, request.metadata)
        
        # Check for interrupt before expensive synthesis
        if interrupt_event.is_set():
            return
        
        # Synthesize with streaming if backend supports it
        chunk_size = self._config.chunk_size_samples
        
        for audio_chunk in self._backend.synthesize_stream(graph, chunk_size):
            if interrupt_event.is_set():
                return
            
            # Handle backpressure
            self._handle_backpressure(len(audio_chunk))
            
            # Write to buffer
            written = self._buffer.write(audio_chunk)
            self._total_samples += written
        
        self._total_requests += 1
    
    def _handle_backpressure(self, incoming_samples: int) -> None:
        """Handle backpressure when buffer is nearly full."""
        policy = self._config.backpressure
        free = self._buffer.free_space
        
        if free >= incoming_samples:
            return
        
        if policy == BackpressurePolicy.BLOCK:
            # Wait for space
            while self._buffer.free_space < incoming_samples:
                time.sleep(0.001)
        
        elif policy == BackpressurePolicy.DROP_OLDEST:
            # Let write() handle dropping oldest
            pass
        
        elif policy == BackpressurePolicy.DROP_NEWEST:
            # Skip this chunk if no space
            if free < incoming_samples:
                if self._config.callback_on_drop:
                    self._config.callback_on_drop(
                        incoming_samples - free,
                        "backpressure_drop_newest",
                    )
        
        elif policy == BackpressurePolicy.ADAPTIVE:
            # TODO: Implement adaptive quality reduction
            pass
    
    def _default_compiler(self, text: str, params: dict) -> ControlGraph:
        """Default compiler using voice_soundboard.compiler."""
        from voice_soundboard.compiler import compile_request
        
        voice = params.get("voice")
        emotion = params.get("emotion")
        
        return compile_request(text, voice=voice, emotion=emotion)
