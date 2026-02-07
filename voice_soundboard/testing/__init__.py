"""
Voice Soundboard v2.4 - Testing Utilities

Tools for testing voice synthesis code.

Components:
    VoiceMock          - Mock backend for testing
    AudioAssertions    - Audio quality assertions
    TestFixtures       - Common test fixtures

Usage:
    from voice_soundboard.testing import VoiceMock, AudioAssertions

    # Use mock backend
    mock = VoiceMock()
    engine = VoiceEngine(Config(backend=mock))

    # Assert audio quality
    assertions = AudioAssertions(audio_pcm)
    assertions.assert_duration(5.0, tolerance=0.1)
    assertions.assert_no_clipping()
"""

from voice_soundboard.testing.mock import (
    VoiceMock,
    MockConfig,
    CallRecord,
)

from voice_soundboard.testing.assertions import (
    AudioAssertions,
    AudioAnalysis,
)

from voice_soundboard.testing.fixtures import (
    create_test_audio,
    create_test_graph,
    create_test_engine,
    SAMPLE_TEXTS,
)

__all__ = [
    # Mock
    "VoiceMock",
    "MockConfig",
    "CallRecord",
    # Assertions
    "AudioAssertions",
    "AudioAnalysis",
    # Fixtures
    "create_test_audio",
    "create_test_graph",
    "create_test_engine",
    "SAMPLE_TEXTS",
]
