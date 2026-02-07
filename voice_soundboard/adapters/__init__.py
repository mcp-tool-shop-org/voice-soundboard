"""
Adapters module - I/O surfaces.

Adapters are thin wrappers that forward to compiler + engine.
They do no synthesis, no feature logic - only I/O.
"""

from voice_soundboard.adapters.api import (
    VoiceEngine,
    SpeechResult,
    Config,
    quick_speak,
)
from voice_soundboard.adapters.audio_events import (
    AudioEventAdapter,
    AudioEventManifest,
    render_timeline_with_events,
    stream_timeline_with_events,
)

__all__ = [
    "VoiceEngine",
    "SpeechResult",
    "Config",
    "quick_speak",
    # Audio events
    "AudioEventAdapter",
    "AudioEventManifest",
    "render_timeline_with_events",
    "stream_timeline_with_events",
]
