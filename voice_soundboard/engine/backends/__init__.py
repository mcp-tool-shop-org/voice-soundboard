"""
Engine backends.
"""

from voice_soundboard.engine.backends.mock import MockBackend

# Optional backends - Kokoro
try:
    from voice_soundboard.engine.backends.kokoro import KokoroBackend, is_available as kokoro_available
    KOKORO_AVAILABLE = kokoro_available()
except ImportError:
    KOKORO_AVAILABLE = False
    KokoroBackend = None

# Optional backends - Piper
try:
    from voice_soundboard.engine.backends.piper import PiperBackend, is_available as piper_available
    PIPER_AVAILABLE = piper_available()
except ImportError:
    PIPER_AVAILABLE = False
    PiperBackend = None

__all__ = [
    "MockBackend",
    "KokoroBackend",
    "KOKORO_AVAILABLE",
    "PiperBackend",
    "PIPER_AVAILABLE",
]
