"""Tests for the graph module."""

import pytest
from voice_soundboard.graph import (
    GRAPH_VERSION,
    ControlGraph,
    TokenEvent,
    SpeakerRef,
    Paralinguistic,
    ParalinguisticEvent,
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


class TestParalinguisticEvent:
    """Tests for ParalinguisticEvent."""
    
    def test_basic_event(self):
        event = ParalinguisticEvent(
            type=Paralinguistic.LAUGH,
            start_time=0.0,
        )
        assert event.type == Paralinguistic.LAUGH
        assert event.start_time == 0.0
        assert event.duration == 0.2  # Default
        assert event.intensity == 1.0  # Default
    
    def test_end_time_property(self):
        event = ParalinguisticEvent(
            type=Paralinguistic.SIGH,
            start_time=1.0,
            duration=0.5,
        )
        assert event.end_time == 1.5
    
    def test_intensity_range(self):
        event = ParalinguisticEvent(
            type=Paralinguistic.BREATH,
            start_time=0.0,
            intensity=0.5,
        )
        assert event.intensity == 0.5


class TestControlGraphEvents:
    """Tests for ControlGraph with paralinguistic events."""
    
    def test_graph_with_events(self):
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello!")],
            speaker=SpeakerRef.from_voice("af_bella"),
            events=[
                ParalinguisticEvent(Paralinguistic.LAUGH, start_time=0.0),
            ],
        )
        assert len(graph.events) == 1
        assert graph.events[0].type == Paralinguistic.LAUGH
    
    def test_validate_event_negative_start(self):
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hi")],
            speaker=SpeakerRef.from_voice("af_bella"),
            events=[ParalinguisticEvent(Paralinguistic.SIGH, start_time=-1.0)],
        )
        issues = graph.validate()
        assert any("negative start_time" in issue for issue in issues)
    
    def test_validate_event_invalid_duration(self):
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hi")],
            speaker=SpeakerRef.from_voice("af_bella"),
            events=[ParalinguisticEvent(Paralinguistic.SIGH, start_time=0.0, duration=0.0)],
        )
        issues = graph.validate()
        assert any("invalid duration" in issue for issue in issues)
    
    def test_validate_overlapping_events(self):
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hi")],
            speaker=SpeakerRef.from_voice("af_bella"),
            events=[
                ParalinguisticEvent(Paralinguistic.LAUGH, start_time=0.0, duration=0.5),
                ParalinguisticEvent(Paralinguistic.SIGH, start_time=0.2, duration=0.5),
            ],
        )
        issues = graph.validate()
        assert any("overlap" in issue for issue in issues)
    
    def test_validate_non_overlapping_events(self):
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hi")],
            speaker=SpeakerRef.from_voice("af_bella"),
            events=[
                ParalinguisticEvent(Paralinguistic.LAUGH, start_time=0.0, duration=0.2),
                ParalinguisticEvent(Paralinguistic.SIGH, start_time=0.5, duration=0.2),
            ],
        )
        issues = graph.validate()
        assert issues == []
