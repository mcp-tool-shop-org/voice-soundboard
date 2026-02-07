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
