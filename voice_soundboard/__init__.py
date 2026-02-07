"""
Voice Soundboard v2.1 - Text-to-speech for AI agents and developers.

Architecture:
    Compiler → ControlGraph → Engine → PCM

Public API (stable):
    VoiceEngine     - Main interface. Call .speak() to generate audio.
    SpeechResult    - Returned by .speak(). Contains .audio_path and metadata.
    Config          - Engine configuration.
    quick_speak     - One-liner: quick_speak("Hello") -> Path

v2.1 Features:
    streaming       - IncrementalSynthesizer for word-by-word streaming
    debug           - Debug mode, visualization, profiler, diff tools
    cloning         - Speaker embedding extraction
    speakers        - SpeakerDB for managing speaker identities
    batch_synthesize- Parallel batch synthesis

Internals (for advanced users):
    voice_soundboard.graph      - ControlGraph, TokenEvent, SpeakerRef
    voice_soundboard.compiler   - compile_request()
    voice_soundboard.engine     - TTSBackend protocol, backends

Example:
    from voice_soundboard import VoiceEngine
    
    engine = VoiceEngine()
    result = engine.speak("Hello world!", voice="af_bella")
    print(result.audio_path)
    
    # v2.1: Incremental streaming
    from voice_soundboard.streaming import IncrementalSynthesizer
    synth = IncrementalSynthesizer(backend)
    for chunk in synth.feed("Hello"):
        play(chunk)

    # v2.1: Debug mode
    engine = VoiceEngine(Config(debug=True))
    result = engine.speak("Hello!")
    print(result.debug_info)
"""

__version__ = "2.1.0"
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

# v2.1: Batch synthesis
from voice_soundboard.runtime.batch import batch_synthesize

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
    # v2.1
    "batch_synthesize",
]
