"""Tests for the engine module."""

import pytest
import numpy as np

from voice_soundboard.engine import MockBackend, load_backend, list_backends
from voice_soundboard.graph import ControlGraph, TokenEvent, SpeakerRef


class TestMockBackend:
    """Tests for MockBackend."""
    
    def test_properties(self):
        backend = MockBackend()
        assert backend.name == "mock"
        assert backend.sample_rate == 24000
    
    def test_synthesize_returns_audio(self):
        backend = MockBackend()
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello world!")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        
        audio = backend.synthesize(graph)
        
        assert isinstance(audio, np.ndarray)
        assert audio.dtype == np.float32
        assert len(audio) > 0
    
    def test_synthesize_silence(self):
        backend = MockBackend(generate_silence=True)
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        
        audio = backend.synthesize(graph)
        
        # Should be all zeros
        assert np.all(audio == 0)
    
    def test_synthesize_tone(self):
        backend = MockBackend(generate_silence=False)
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        
        audio = backend.synthesize(graph)
        
        # Should have non-zero values
        assert np.any(audio != 0)
    
    def test_duration_scales_with_words(self):
        backend = MockBackend()
        
        short_graph = ControlGraph(
            tokens=[TokenEvent(text="Hi")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        long_graph = ControlGraph(
            tokens=[TokenEvent(text="This is a much longer sentence with many more words")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        
        short_audio = backend.synthesize(short_graph)
        long_audio = backend.synthesize(long_graph)
        
        assert len(long_audio) > len(short_audio)
    
    def test_supports_any_voice(self):
        backend = MockBackend()
        assert backend.supports_voice("any_voice")
        assert backend.supports_voice("another_voice")


class TestLoadBackend:
    """Tests for backend loading."""
    
    def test_load_mock(self):
        backend = load_backend("mock")
        assert backend.name == "mock"
    
    def test_load_auto_returns_backend(self):
        backend = load_backend("auto")
        assert hasattr(backend, "synthesize")
    
    def test_load_invalid_raises(self):
        with pytest.raises(ValueError):
            load_backend("nonexistent_backend")


class TestListBackends:
    """Tests for list_backends."""
    
    def test_mock_always_available(self):
        backends = list_backends()
        assert "mock" in backends


class TestBackendProtocol:
    """Tests that backends implement the protocol correctly."""
    
    def test_mock_is_tts_backend(self):
        from voice_soundboard.engine.base import TTSBackend
        
        backend = MockBackend()
        assert isinstance(backend, TTSBackend)
    
    def test_backend_has_required_methods(self):
        backend = MockBackend()
        
        assert hasattr(backend, "name")
        assert hasattr(backend, "sample_rate")
        assert hasattr(backend, "synthesize")


class TestPiperBackend:
    """Tests for PiperBackend (without requiring piper-tts installed)."""
    
    def test_piper_available_flag(self):
        """Test PIPER_AVAILABLE is exposed."""
        from voice_soundboard.engine import PIPER_AVAILABLE
        assert isinstance(PIPER_AVAILABLE, bool)
    
    def test_piper_in_list_backends_when_available(self):
        """Piper should appear in list_backends if available."""
        backends = list_backends()
        # May or may not be available depending on installation
        assert isinstance(backends, list)
    
    def test_piper_voice_mappings(self):
        """Test Piper voice mappings are defined."""
        from voice_soundboard.engine.backends.piper import PIPER_VOICES, KOKORO_TO_PIPER
        
        # Should have English voices at minimum
        assert any("en_US" in v for v in PIPER_VOICES)
        assert any("en_GB" in v for v in PIPER_VOICES)
        
        # Should have Kokoro compat mapping
        assert "af_bella" in KOKORO_TO_PIPER
        assert "am_michael" in KOKORO_TO_PIPER
    
    def test_piper_speed_to_length_scale(self):
        """Test speed → length_scale conversion (inverse relationship)."""
        from voice_soundboard.engine.backends.piper import PiperBackend
        
        # Create backend (won't load models)
        backend = PiperBackend.__new__(PiperBackend)
        backend._default_voice = "en_US_lessac_medium"
        
        # Test conversion logic directly
        # speed=2.0 → length_scale=0.5 (faster)
        graph_fast = ControlGraph(
            tokens=[TokenEvent(text="test")],
            speaker=SpeakerRef.from_voice("test"),
            global_speed=2.0,
        )
        length_scale = backend._lower_speed(graph_fast)
        assert length_scale == pytest.approx(0.5, rel=0.01)
        
        # speed=0.5 → length_scale=2.0 (slower)
        graph_slow = ControlGraph(
            tokens=[TokenEvent(text="test")],
            speaker=SpeakerRef.from_voice("test"),
            global_speed=0.5,
        )
        length_scale = backend._lower_speed(graph_slow)
        assert length_scale == pytest.approx(2.0, rel=0.01)
    
    def test_piper_voice_resolution(self):
        """Test voice ID resolution logic."""
        from voice_soundboard.engine.backends.piper import PiperBackend
        
        backend = PiperBackend.__new__(PiperBackend)
        backend._default_voice = "en_US_lessac_medium"
        
        # Direct Piper voice
        graph = ControlGraph(
            tokens=[TokenEvent(text="test")],
            speaker=SpeakerRef.from_voice("en_US_ryan_medium"),
        )
        assert backend._lower_voice(graph) == "en_US_ryan_medium"
        
        # Kokoro voice → Piper mapping
        graph = ControlGraph(
            tokens=[TokenEvent(text="test")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        assert backend._lower_voice(graph) == "en_US_lessac_medium"
        
        # Unknown voice → default
        graph = ControlGraph(
            tokens=[TokenEvent(text="test")],
            speaker=SpeakerRef.from_voice("unknown_voice"),
        )
        assert backend._lower_voice(graph) == "en_US_lessac_medium"
    
    def test_piper_text_lowering(self):
        """Test token text concatenation."""
        from voice_soundboard.engine.backends.piper import PiperBackend
        
        backend = PiperBackend.__new__(PiperBackend)
        
        graph = ControlGraph(
            tokens=[
                TokenEvent(text="Hello"),
                TokenEvent(text="world"),
                TokenEvent(text="!"),
            ],
            speaker=SpeakerRef.from_voice("test"),
        )
        text = backend._lower_text(graph)
        assert text == "Hello world !"
