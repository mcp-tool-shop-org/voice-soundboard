"""
Engine module - Pure synthesis from ControlGraph to PCM.

The engine NEVER imports from compiler/. This is architecturally enforced.

v2.4: Added ElevenLabs and Azure Neural TTS backends.
"""

from voice_soundboard.engine.base import TTSBackend, BaseTTSBackend
from voice_soundboard.engine.loader import load_backend, list_backends
from voice_soundboard.engine.backends import (
    MockBackend,
    KOKORO_AVAILABLE,
    PIPER_AVAILABLE,
    OPENAI_AVAILABLE,
    ELEVENLABS_AVAILABLE,
    AZURE_AVAILABLE,
)

__all__ = [
    "TTSBackend",
    "BaseTTSBackend",
    "load_backend",
    "list_backends",
    "MockBackend",
    "KOKORO_AVAILABLE",
    "PIPER_AVAILABLE",
    "OPENAI_AVAILABLE",
    "ELEVENLABS_AVAILABLE",
    "AZURE_AVAILABLE",
]

# Conditional exports
if KOKORO_AVAILABLE:
    from voice_soundboard.engine.backends import KokoroBackend
    __all__.append("KokoroBackend")

if PIPER_AVAILABLE:
    from voice_soundboard.engine.backends import PiperBackend
    __all__.append("PiperBackend")

if OPENAI_AVAILABLE:
    from voice_soundboard.engine.backends import OpenAITTSBackend
    __all__.append("OpenAITTSBackend")

if ELEVENLABS_AVAILABLE:
    from voice_soundboard.engine.backends import ElevenLabsBackend
    __all__.append("ElevenLabsBackend")

if AZURE_AVAILABLE:
    from voice_soundboard.engine.backends import AzureTTSBackend
    __all__.append("AzureTTSBackend")
