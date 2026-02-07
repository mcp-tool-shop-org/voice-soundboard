"""
Debug Info - Structured debug information from synthesis.

Provides DebugInfo attached to SpeechResult when debug=True.

Usage:
    engine = VoiceEngine(Config(debug=True))
    result = engine.speak("Hello!")
    
    print(result.debug_info)
    # {
    #   "compile_time_ms": 2.3,
    #   "synth_time_ms": 145.2,
    #   "graph_tokens": 3,
    #   "graph_events": 0,
    #   "backend": "kokoro",
    #   "cache_hit": False,
    # }
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from contextlib import contextmanager


@dataclass
class TimingInfo:
    """Timing information for a phase of synthesis.
    
    Attributes:
        name: Phase name (e.g., "compile", "synthesize")
        start_time: Start timestamp
        end_time: End timestamp
        duration_ms: Duration in milliseconds
    """
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    
    @classmethod
    def start(cls, name: str) -> "TimingInfo":
        """Start timing a phase."""
        return cls(name=name, start_time=time.perf_counter())
    
    def stop(self) -> "TimingInfo":
        """Stop timing and calculate duration."""
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        return self


@dataclass
class DebugInfo:
    """Debug information from a synthesis operation.
    
    Attached to SpeechResult when debug mode is enabled.
    """
    # Timing (milliseconds)
    compile_time_ms: float = 0.0
    synth_time_ms: float = 0.0
    total_time_ms: float = 0.0
    io_time_ms: float = 0.0
    
    # Timing dictionary for flexible timing tracking
    timing: dict[str, float] = field(default_factory=dict)
    
    # Graph statistics
    graph_tokens: int = 0
    graph_events: int = 0
    graph_source_chars: int = 0
    
    # Backend info
    backend: str = "unknown"
    backend_version: str = ""
    sample_rate: int = 0
    
    # Cache
    cache_hit: bool = False
    cache_key: str = ""
    
    # Audio metrics
    audio_samples: int = 0
    audio_duration_ms: float = 0.0
    realtime_factor: float = 0.0
    
    # Memory (if available)
    peak_memory_mb: float = 0.0
    
    def add_timing(self, name: str, duration_ms: float) -> None:
        """Add timing for a named phase.
        
        Args:
            name: Phase name (e.g., "compile", "synthesize")
            duration_ms: Duration in milliseconds
        """
        self.timing[name] = duration_ms
        
        # Also update specific fields if applicable
        if name == "compile":
            self.compile_time_ms = duration_ms
        elif name == "synth" or name == "synthesize":
            self.synth_time_ms = duration_ms
        elif name == "io":
            self.io_time_ms = duration_ms
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        # Ensure timing is included
        if "timing" not in result:
            result["timing"] = self.timing
        return result
    
    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Compile:  {self.compile_time_ms:6.1f}ms",
            f"Synth:    {self.synth_time_ms:6.1f}ms",
            f"I/O:      {self.io_time_ms:6.1f}ms",
            f"Total:    {self.total_time_ms:6.1f}ms",
            f"",
            f"Tokens:   {self.graph_tokens}",
            f"Events:   {self.graph_events}",
            f"Backend:  {self.backend}",
            f"Cache:    {'HIT' if self.cache_hit else 'MISS'}",
            f"",
            f"Audio:    {self.audio_duration_ms:.1f}ms ({self.audio_samples} samples)",
            f"RTF:      {self.realtime_factor:.1f}x",
        ]
        return "\n".join(lines)
    
    def __str__(self) -> str:
        return self.summary()


@dataclass
class DebugContext:
    """Context manager for collecting debug info during synthesis.
    
    Usage:
        with DebugContext() as ctx:
            ctx.start_phase("compile")
            # ... compile ...
            ctx.end_phase("compile")
            
            ctx.start_phase("synth")
            # ... synthesize ...
            ctx.end_phase("synth")
        
        debug_info = ctx.build()
    """
    _phases: dict[str, float] = field(default_factory=dict)
    _phase_starts: dict[str, float] = field(default_factory=dict)
    _metadata: dict[str, Any] = field(default_factory=dict)
    _start_time: float = field(default_factory=time.perf_counter)
    _records: list[str] = field(default_factory=list)
    _record_times: dict[str, float] = field(default_factory=dict)
    
    def start_phase(self, name: str):
        """Start timing a phase."""
        self._phase_starts[name] = time.perf_counter()
    
    def end_phase(self, name: str):
        """End timing a phase."""
        if name in self._phase_starts:
            elapsed = time.perf_counter() - self._phase_starts[name]
            self._phases[name] = elapsed * 1000  # Convert to ms
            del self._phase_starts[name]
    
    def record(self, name: str):
        """Record a timing checkpoint.
        
        Call this to mark a point in time. The time between
        consecutive records is captured in the timing dict.
        
        Args:
            name: Name of the checkpoint/phase.
        """
        now = time.perf_counter()
        
        if self._records:
            # Calculate time since last record
            prev_name = self._records[-1]
            if prev_name in self._record_times:
                elapsed = (now - self._record_times[prev_name]) * 1000
                self._phases[prev_name] = elapsed
        
        self._records.append(name)
        self._record_times[name] = now
    
    def set(self, key: str, value: Any):
        """Set a metadata value."""
        self._metadata[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a metadata value."""
        return self._metadata.get(key, default)
    
    def get_info(self) -> DebugInfo:
        """Get the debug info built from recorded data.
        
        Alias for build() that can be called during or after the context.
        
        Returns:
            DebugInfo with timing and metadata.
        """
        return self.build()
    
    def build(self) -> DebugInfo:
        """Build the final DebugInfo object."""
        total_time = (time.perf_counter() - self._start_time) * 1000
        
        info = DebugInfo(
            compile_time_ms=self._phases.get("compile", 0.0),
            synth_time_ms=self._phases.get("synth", 0.0),
            io_time_ms=self._phases.get("io", 0.0),
            total_time_ms=total_time,
            timing=dict(self._phases),
            graph_tokens=self._metadata.get("graph_tokens", 0),
            graph_events=self._metadata.get("graph_events", 0),
            graph_source_chars=self._metadata.get("graph_source_chars", 0),
            backend=self._metadata.get("backend", "unknown"),
            backend_version=self._metadata.get("backend_version", ""),
            sample_rate=self._metadata.get("sample_rate", 0),
            cache_hit=self._metadata.get("cache_hit", False),
            cache_key=self._metadata.get("cache_key", ""),
            audio_samples=self._metadata.get("audio_samples", 0),
            audio_duration_ms=self._metadata.get("audio_duration_ms", 0.0),
            realtime_factor=self._metadata.get("realtime_factor", 0.0),
            peak_memory_mb=self._metadata.get("peak_memory_mb", 0.0),
        )
        return info
    
    def __enter__(self) -> "DebugContext":
        self._start_time = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        pass


@contextmanager
def debug_context():
    """Create a debug context for collecting synthesis info.
    
    Usage:
        with debug_context() as ctx:
            ctx.start_phase("compile")
            graph = compile_request(text)
            ctx.end_phase("compile")
            ctx.set("graph_tokens", len(graph.tokens))
        
        info = ctx.build()
    """
    ctx = DebugContext()
    try:
        yield ctx
    finally:
        pass
