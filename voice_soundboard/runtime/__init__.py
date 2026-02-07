"""
Runtime module - Streaming, scheduling, and audio processing.

Streaming is a runtime concern, not an engine concern.
"""

from voice_soundboard.runtime.stream import (
    StreamingSynthesizer,
    RealtimeSynthesizer,
    StreamConfig,
)

from voice_soundboard.runtime.timeline import (
    Event,
    Token,
    Pause,
    StreamItem,
    stream_timeline,
    total_duration_ms,
    validate_no_overlap,
)

from voice_soundboard.runtime.ducking import (
    DuckingEnvelope,
    DuckingProcessor,
    apply_gain_envelope,
    apply_constant_gain,
    process_timeline_with_ducking,
    DUCKING_SUBTLE,
    DUCKING_STANDARD,
    DUCKING_DRAMATIC,
    DUCKING_PODCAST,
)

__all__ = [
    # Streaming
    "StreamingSynthesizer",
    "RealtimeSynthesizer",
    "StreamConfig",
    # Timeline
    "Event",
    "Token",
    "Pause",
    "StreamItem",
    "stream_timeline",
    "total_duration_ms",
    "validate_no_overlap",
    # Ducking
    "DuckingEnvelope",
    "DuckingProcessor",
    "apply_gain_envelope",
    "apply_constant_gain",
    "process_timeline_with_ducking",
    "DUCKING_SUBTLE",
    "DUCKING_STANDARD",
    "DUCKING_DRAMATIC",
    "DUCKING_PODCAST",
]
