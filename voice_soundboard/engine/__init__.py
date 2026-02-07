"""
Engine module - Pure synthesis from ControlGraph to PCM.

The engine NEVER imports from compiler/. This is architecturally enforced.
"""

from voice_soundboard.engine.base import TTSBackend, BaseTTSBackend
from voice_soundboard.engine.loader import load_backend, list_backends
from voice_soundboard.engine.backends import MockBackend, KOKORO_AVAILABLE

__all__ = [
    "TTSBackend",
    "BaseTTSBackend",
    "load_backend",
    "list_backends",
    "MockBackend",
    "KOKORO_AVAILABLE",
]

# Conditional exports
if KOKORO_AVAILABLE:
    from voice_soundboard.engine.backends import KokoroBackend
    __all__.append("KokoroBackend")
