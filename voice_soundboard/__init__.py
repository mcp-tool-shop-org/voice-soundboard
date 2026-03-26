"""
Voice Soundboard - Text-to-speech for AI agents and developers.

Architecture:
    Compiler → ControlGraph → Engine → PCM

Public API (stable):
    VoiceEngine     - Main interface. Call .speak() to generate audio.
    SpeechResult    - Returned by .speak(). Contains .audio_path and metadata.
    Config          - Engine configuration.
    quick_speak     - One-liner: quick_speak("Hello") -> Path

Extensions (lazy import):
    realtime        - Real-time streaming engine with <20ms buffering
    plugins         - Plugin architecture for backends, audio effects, compilers
    conversation    - Multi-speaker dialogue support with turn management
    quality         - Voice quality metrics and A/B comparison tools
    formats         - Audio format conversion, sample rate, LUFS normalization
    streaming       - IncrementalSynthesizer for word-by-word streaming
    debug           - Debug mode, visualization, profiler, diff tools
    cloning         - Speaker embedding extraction
    speakers        - SpeakerDB for managing speaker identities
    testing         - VoiceMock, AudioAssertions, test fixtures
    accessibility   - Screen reader integration, captions, motor/visual/cognitive

Internals (for advanced users):
    voice_soundboard.graph      - ControlGraph, TokenEvent, SpeakerRef
    voice_soundboard.compiler   - compile_request()
    voice_soundboard.engine     - TTSBackend protocol, backends

Example:
    from voice_soundboard import VoiceEngine

    engine = VoiceEngine()
    result = engine.speak("Hello world!", voice="af_bella")
    print(result.audio_path)

    # With emotion
    result = engine.speak("I'm thrilled!", emotion="excited")

    # With style
    result = engine.speak("Good morning!", style="warmly and cheerfully")

    # Incremental streaming
    from voice_soundboard.streaming import IncrementalSynthesizer
    synth = IncrementalSynthesizer(backend)
    for chunk in synth.feed("Hello"):
        play(chunk)

    # Multi-speaker conversation
    from voice_soundboard.conversation import Conversation, Speaker
    conv = Conversation(speakers=[Speaker("Alice"), Speaker("Bob")])
    conv.add_turn("Alice", "Hello!")
    conv.add_turn("Bob", "Hi there!")
    audio = conv.synthesize(engine)

    # Testing utilities
    from voice_soundboard.testing import VoiceMock, AudioAssertions
    mock = VoiceMock()
    assertions = AudioAssertions(audio).assert_no_clipping()
"""

__version__ = "3.0.1"
API_VERSION = 3

# Public API - backwards compatible with v1
from voice_soundboard.adapters.api import (  # noqa: E402
    VoiceEngine,
    SpeechResult,
    Config,
    quick_speak,
)

# Voice data
from voice_soundboard.compiler.voices import VOICES, PRESETS  # noqa: E402

# Batch synthesis
from voice_soundboard.runtime.batch import batch_synthesize  # noqa: E402

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
    # Batch
    "batch_synthesize",
]

# Extensions (lazy import for performance)
# Import with: from voice_soundboard.realtime import RealtimeEngine
# Import with: from voice_soundboard.plugins import PluginRegistry
# Import with: from voice_soundboard.conversation import Conversation, Speaker
# Import with: from voice_soundboard.quality import evaluate_pronunciation, ab_test
# Import with: from voice_soundboard.formats import convert_sample_rate, normalize_loudness
# Import with: from voice_soundboard.testing import VoiceMock, AudioAssertions
