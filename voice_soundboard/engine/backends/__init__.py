"""
Engine backends.

v2.4: Added ElevenLabs and Azure Neural TTS backends.
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

# Optional backends - OpenAI
try:
    from voice_soundboard.engine.backends.openai import OpenAITTSBackend
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAITTSBackend = None

# Optional backends - ElevenLabs (v2.4)
try:
    from voice_soundboard.engine.backends.elevenlabs import ElevenLabsBackend, ELEVENLABS_AVAILABLE
except ImportError:
    ELEVENLABS_AVAILABLE = False
    ElevenLabsBackend = None

# Optional backends - Azure (v2.4)
try:
    from voice_soundboard.engine.backends.azure import AzureTTSBackend, AZURE_AVAILABLE
except ImportError:
    AZURE_AVAILABLE = False
    AzureTTSBackend = None

__all__ = [
    "MockBackend",
    "KokoroBackend",
    "KOKORO_AVAILABLE",
    "PiperBackend",
    "PIPER_AVAILABLE",
    "OpenAITTSBackend",
    "OPENAI_AVAILABLE",
    # v2.4 backends
    "ElevenLabsBackend",
    "ELEVENLABS_AVAILABLE",
    "AzureTTSBackend",
    "AZURE_AVAILABLE",
]
