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

__all__ = [
    "VoiceEngine",
    "SpeechResult",
    "Config",
    "quick_speak",
]
