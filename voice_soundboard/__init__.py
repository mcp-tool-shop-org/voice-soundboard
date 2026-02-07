"""
Voice Soundboard v2 - Text-to-speech for AI agents and developers.

Architecture:
    Compiler → ControlGraph → Engine → PCM

Public API (stable):
    VoiceEngine     - Main interface. Call .speak() to generate audio.
    SpeechResult    - Returned by .speak(). Contains .audio_path and metadata.
    Config          - Engine configuration.
    quick_speak     - One-liner: quick_speak("Hello") -> Path

Internals (for advanced users):
    voice_soundboard.graph      - ControlGraph, TokenEvent, SpeakerRef
    voice_soundboard.compiler   - compile_request()
    voice_soundboard.engine     - TTSBackend protocol, backends

Example:
    from voice_soundboard import VoiceEngine
    
    engine = VoiceEngine()
    result = engine.speak("Hello world!", voice="af_bella")
    print(result.audio_path)
"""

__version__ = "2.0.0"
API_VERSION = 2

# Public API - backwards compatible with v1
from voice_soundboard.adapters.api import (
    VoiceEngine,
    SpeechResult,
    Config,
    quick_speak,
)

# Voice data
from voice_soundboard.compiler.voices import VOICES, PRESETS

__all__ = [
    # Version
    "__version__",
    "API_VERSION",
    # Core
    "VoiceEngine",
    "SpeechResult", 
    "Config",
    "quick_speak",
    # Data
    "VOICES",
    "PRESETS",
]
