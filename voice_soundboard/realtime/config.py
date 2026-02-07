"""
Real-time configuration for Voice Soundboard v2.3.

Defines execution modes and constraints for real-time synthesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Callable, Any


class BackpressurePolicy(Enum):
    """How to handle when synthesis can't keep up with input."""
    
    BLOCK = "block"
    """Block the caller until buffer has space. Simple but can cause latency spikes."""
    
    DROP_OLDEST = "drop_oldest"
    """Drop the oldest queued items. Good for live audio where freshness matters."""
    
    DROP_NEWEST = "drop_newest"
    """Drop incoming items if buffer is full. Preserves queue order."""
    
    ADAPTIVE = "adaptive"
    """Dynamically adjust quality/speed tradeoff to maintain latency target."""


class DropPolicy(Enum):
    """How to handle dropped audio gracefully."""
    
    SILENT = "silent"
    """Drop with no audible indication."""
    
    GRACEFUL = "graceful"
    """Fade out dropped audio and fade in resumed audio."""
    
    NOTIFY = "notify"
    """Call a callback when audio is dropped."""


@dataclass
class RealtimeConfig:
    """Configuration for real-time synthesis mode.
    
    Real-time mode provides:
    - Bounded latency guarantees
    - Deterministic scheduling
    - Backpressure handling
    - Memory limits
    
    Args:
        max_latency_ms: Maximum allowed latency from input to audio output.
            Engine will trade quality for speed to meet this target.
        buffer_size_ms: Size of the audio buffer in milliseconds.
            Larger buffers are more tolerant of jitter but add latency.
        backpressure: How to handle when synthesis can't keep up.
        drop_policy: How to handle dropped audio gracefully.
        max_memory_mb: Maximum memory usage for buffers and caches.
        priority: Thread/process priority for synthesis.
        enable_jitter_buffer: Use jitter buffer for smoother playback.
        callback_on_drop: Called when audio is dropped (if drop_policy=NOTIFY).
    
    Example:
        config = RealtimeConfig(
            max_latency_ms=50,
            buffer_size_ms=100,
            backpressure=BackpressurePolicy.ADAPTIVE,
            drop_policy=DropPolicy.GRACEFUL,
        )
    """
    
    max_latency_ms: int = 50
    """Maximum allowed end-to-end latency in milliseconds."""
    
    buffer_size_ms: int = 100
    """Audio buffer size in milliseconds."""
    
    backpressure: BackpressurePolicy = BackpressurePolicy.ADAPTIVE
    """How to handle backpressure when synthesis can't keep up."""
    
    drop_policy: DropPolicy = DropPolicy.GRACEFUL
    """How to handle dropped audio."""
    
    max_memory_mb: int = 256
    """Maximum memory for buffers and internal caches."""
    
    priority: Literal["normal", "high", "realtime"] = "high"
    """Thread priority for synthesis work."""
    
    enable_jitter_buffer: bool = True
    """Enable jitter buffer for smoother playback despite timing variance."""
    
    jitter_buffer_ms: int = 20
    """Size of jitter buffer in milliseconds."""
    
    callback_on_drop: Callable[[int, str], None] | None = None
    """Called when audio is dropped: (dropped_samples, reason)."""
    
    # Internal tuning
    chunk_size_samples: int = 512
    """Size of audio chunks for processing. Smaller = lower latency, higher CPU."""
    
    commit_threshold_ms: int = 30
    """Threshold for committing speculative synthesis."""
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.max_latency_ms < 10:
            raise ValueError("max_latency_ms must be >= 10ms")
        if self.buffer_size_ms < self.max_latency_ms:
            raise ValueError("buffer_size_ms must be >= max_latency_ms")
        if self.max_memory_mb < 32:
            raise ValueError("max_memory_mb must be >= 32MB")
    
    def effective_latency_budget(self) -> dict[str, int]:
        """Break down latency budget across components."""
        total = self.max_latency_ms
        return {
            "synthesis": int(total * 0.6),  # 60% for TTS synthesis
            "buffering": int(total * 0.2),  # 20% for buffering
            "scheduling": int(total * 0.1), # 10% for scheduling overhead
            "margin": int(total * 0.1),     # 10% safety margin
        }


@dataclass 
class SessionConfig:
    """Per-session configuration overrides.
    
    Allows tweaking real-time parameters for specific use cases.
    """
    
    voice: str | None = None
    """Override default voice for this session."""
    
    speed: float = 1.0
    """Playback speed multiplier."""
    
    interruptible: bool = True
    """Allow interruption of current synthesis."""
    
    priority_level: int = 0
    """Priority for this session (higher = more important)."""
    
    metadata: dict[str, Any] = field(default_factory=dict)
    """Custom metadata attached to session."""
