"""Tests for the graph module."""

import pytest
from voice_soundboard.graph import (
    GRAPH_VERSION,
    ControlGraph,
    TokenEvent,
    SpeakerRef,
    Paralinguistic,
)


class TestGraphVersion:
    """Tests for graph version stability."""
    
    def test_graph_version_exists(self):
        assert GRAPH_VERSION == 1
    
    def test_graph_version_is_int(self):
        assert isinstance(GRAPH_VERSION, int)


class TestTokenEvent:
    """Tests for TokenEvent."""
    
    def test_default_values(self):
        token = TokenEvent(text="Hello")
        assert token.text == "Hello"
        assert token.pitch_scale == 1.0
        assert token.energy_scale == 1.0
        assert token.duration_scale == 1.0
        assert token.pause_after == 0.0
    
    def test_custom_prosody(self):
        token = TokenEvent(
            text="Excited!",
            pitch_scale=1.2,
            energy_scale=1.3,
            duration_scale=0.8,
        )
        assert token.pitch_scale == 1.2
        assert token.energy_scale == 1.3
        assert token.duration_scale == 0.8
    
    def test_paralinguistic(self):
        token = TokenEvent(text="", paralinguistic=Paralinguistic.LAUGH)
        assert token.paralinguistic == Paralinguistic.LAUGH


class TestSpeakerRef:
    """Tests for SpeakerRef."""
    
    def test_from_voice(self):
        speaker = SpeakerRef.from_voice("af_bella")
        assert speaker.type == "voice_id"
        assert speaker.value == "af_bella"
        assert speaker.name == "af_bella"
    
    def test_from_embedding(self):
        embedding = [0.1, 0.2, 0.3]
        speaker = SpeakerRef.from_embedding(embedding, name="cloned_voice")
        assert speaker.type == "embedding"
        assert speaker.value == embedding
        assert speaker.name == "cloned_voice"
    
    def test_from_preset(self):
        speaker = SpeakerRef.from_preset("narrator")
        assert speaker.type == "preset"
        assert speaker.value == "narrator"
    
    def test_embedding_is_float_list(self):
        """Embeddings must be numeric vectors, not raw audio data."""
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        speaker = SpeakerRef.from_embedding(embedding)
        
        # Value should be the embedding, not bytes or large arrays
        assert isinstance(speaker.value, list)
        assert all(isinstance(x, float) for x in speaker.value)


class TestControlGraph:
    """Tests for ControlGraph."""
    
    def test_basic_graph(self):
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello world!")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        assert graph.text == "Hello world!"
        assert graph.global_speed == 1.0
        assert graph.sample_rate == 24000
    
    def test_multi_token_text(self):
        graph = ControlGraph(
            tokens=[
                TokenEvent(text="Hello,"),
                TokenEvent(text="world!"),
            ],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        assert graph.text == "Hello, world!"
    
    def test_total_pause(self):
        graph = ControlGraph(
            tokens=[
                TokenEvent(text="Hello", pause_after=0.3),
                TokenEvent(text="world", pause_after=0.2),
            ],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        assert graph.total_pause == 0.5
    
    def test_validate_empty_tokens(self):
        graph = ControlGraph(
            tokens=[],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        issues = graph.validate()
        assert "no tokens" in issues[0].lower()
    
    def test_validate_invalid_speed(self):
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hi")],
            speaker=SpeakerRef.from_voice("af_bella"),
            global_speed=-1.0,
        )
        issues = graph.validate()
        assert any("global_speed" in issue for issue in issues)
    
    def test_validate_valid_graph(self):
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello world!")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        issues = graph.validate()
        assert issues == []
