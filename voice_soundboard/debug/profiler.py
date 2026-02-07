"""
Timing Profiler - Detailed performance breakdown for synthesis.

Measures each phase of the synthesis pipeline:
- Tokenization
- Compilation
- Lowering
- Synthesis
- I/O

Usage:
    from voice_soundboard.debug import profile_synthesis
    
    with profile_synthesis() as prof:
        engine.speak("Long text here...")
    
    prof.report()
    # Tokenization:  2.1ms
    # Compilation:   3.4ms
    # Lowering:      0.8ms
    # Synthesis:   142.3ms
    # I/O:          12.1ms
    # Total:       160.7ms
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar
from contextlib import contextmanager
from functools import wraps

T = TypeVar('T')


@dataclass
class ProfilePhase:
    """Timing data for a single phase."""
    name: str
    start_ms: float = 0.0
    end_ms: float = 0.0
    
    @property
    def duration_ms(self) -> float:
        return self.end_ms - self.start_ms


@dataclass
class ProfileReport:
    """Complete profiling report."""
    phases: list[ProfilePhase] = field(default_factory=list)
    total_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def add_phase(self, name: str, duration_ms: float):
        """Add a completed phase."""
        phase = ProfilePhase(
            name=name,
            start_ms=self.total_ms,
            end_ms=self.total_ms + duration_ms,
        )
        self.phases.append(phase)
        self.total_ms += duration_ms
    
    def get_phase(self, name: str) -> ProfilePhase | None:
        """Get a specific phase by name."""
        for phase in self.phases:
            if phase.name == name:
                return phase
        return None
    
    def report(self) -> str:
        """Generate a human-readable report."""
        lines = []
        max_name_len = max((len(p.name) for p in self.phases), default=10)
        
        for phase in self.phases:
            pct = (phase.duration_ms / self.total_ms * 100) if self.total_ms > 0 else 0
            bar = "█" * int(pct / 5)
            lines.append(
                f"{phase.name.capitalize():<{max_name_len}}: {phase.duration_ms:7.1f}ms  {bar} {pct:.0f}%"
            )
        
        lines.append("-" * (max_name_len + 25))
        lines.append(f"{'Total':<{max_name_len}}: {self.total_ms:7.1f}ms")
        
        # Add metadata
        if self.metadata:
            lines.append("")
            for key, value in self.metadata.items():
                lines.append(f"{key}: {value}")
        
        return "\n".join(lines)
    
    def __str__(self) -> str:
        return self.report()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "phases": [
                {"name": p.name, "duration_ms": p.duration_ms}
                for p in self.phases
            ],
            "total_ms": self.total_ms,
            "metadata": self.metadata,
        }


class SynthesisProfiler:
    """Context manager for profiling synthesis operations.
    
    Usage:
        with SynthesisProfiler() as prof:
            with prof.phase("tokenize"):
                tokens = tokenize(text)
            
            with prof.phase("compile"):
                graph = compile(tokens)
            
            with prof.phase("synthesize"):
                audio = backend.synthesize(graph)
        
        print(prof.report())
    """
    
    def __init__(self):
        self._report = ProfileReport()
        self._start_time: float | None = None
        self._current_phase_start: float | None = None
        self._current_phase_name: str | None = None
    
    @contextmanager
    def phase(self, name: str):
        """Time a specific phase.
        
        Args:
            name: Phase name (e.g., "tokenize", "compile", "synthesize")
        
        Usage:
            with prof.phase("compile"):
                graph = compile_request(text)
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            self._report.add_phase(name, elapsed)
    
    def set(self, key: str, value: Any):
        """Set metadata value."""
        self._report.metadata[key] = value
    
    def report(self) -> ProfileReport:
        """Get the profiling report."""
        return self._report
    
    def __enter__(self) -> "SynthesisProfiler":
        self._start_time = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        pass


@contextmanager
def profile_synthesis():
    """Context manager for profiling synthesis.
    
    Usage:
        with profile_synthesis() as prof:
            # Use prof.phase() to time specific phases
            with prof.phase("compile"):
                graph = compile_request(text)
            
            with prof.phase("synth"):
                audio = engine.synthesize(graph)
        
        print(prof.report())
    
    Yields:
        SynthesisProfiler instance
    """
    profiler = SynthesisProfiler()
    try:
        yield profiler
    finally:
        pass


def timed(name: str | None = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to time a function and store result in thread-local profiler.
    
    Args:
        name: Phase name (defaults to function name)
    
    Usage:
        @timed("compile")
        def compile_request(text):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        phase_name = name or func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                # Store timing info for later retrieval
                if not hasattr(wrapper, '_timing_info'):
                    wrapper._timing_info = []
                wrapper._timing_info.append((phase_name, elapsed_ms))
        
        return wrapper
    return decorator


def benchmark_synthesis(
    text: str,
    engine,
    *,
    iterations: int = 10,
    warmup: int = 2,
) -> ProfileReport:
    """Benchmark synthesis performance.
    
    Runs multiple iterations and reports statistics.
    
    Args:
        text: Text to synthesize
        engine: VoiceEngine instance
        iterations: Number of timed iterations
        warmup: Number of warmup iterations (not counted)
    
    Returns:
        ProfileReport with statistics
    """
    # Warmup
    for _ in range(warmup):
        engine.speak(text)
    
    # Timed iterations
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        result = engine.speak(text)
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    
    # Build report
    report = ProfileReport()
    
    import statistics
    avg = statistics.mean(times)
    std = statistics.stdev(times) if len(times) > 1 else 0
    min_t = min(times)
    max_t = max(times)
    
    report.add_phase("iteration", avg)
    report.metadata.update({
        "iterations": iterations,
        "min_ms": f"{min_t:.1f}",
        "max_ms": f"{max_t:.1f}",
        "stddev_ms": f"{std:.1f}",
        "text_chars": len(text),
    })
    
    return report
