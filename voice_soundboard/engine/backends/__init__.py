"""
Engine backends.
"""

from voice_soundboard.engine.backends.mock import MockBackend

# Optional backends
try:
    from voice_soundboard.engine.backends.kokoro import KokoroBackend, is_available as kokoro_available
    KOKORO_AVAILABLE = kokoro_available()
except ImportError:
    KOKORO_AVAILABLE = False
    KokoroBackend = None

__all__ = [
    "MockBackend",
    "KokoroBackend",
    "KOKORO_AVAILABLE",
]
