"""
v3.1 Hardening Tests - Multi-Speaker Conversation.

Tests for conversation helpers including:
- Turn-taking
- Automatic crossfades
- Per-speaker defaults
- Timeline calculation
"""

import pytest
from voice_soundboard.v3.conversation import (
    Conversation,
    Speaker,
    Turn,
    Position,
    ConversationConfig,
    TurnTakingStyle,
    CrossfadeConfig,
    apply_turn_taking_style,
    calculate_crossfades,
)


class TestSpeaker:
    """Tests for Speaker class."""
    
    def test_create_speaker(self):
        """Basic speaker creation."""
        speaker = Speaker(
            name="Alice",
            voice="af_bella",
            position=Position(x=-0.5, y=0, z=1),
            defaults={"eq_preset": "female_voice"},
            gain_db=1.0,
        )
        
        assert speaker.name == "Alice"
        assert speaker.voice == "af_bella"
        assert speaker.position.x == -0.5
        assert speaker.gain_db == 1.0
    
    def test_speaker_without_position(self):
        """Speaker can be created without position."""
        speaker = Speaker(name="Bob", voice="am_adam")
        
        assert speaker.position is None


class TestPosition:
    """Tests for Position class."""
    
    def test_create_position(self):
        """Basic position creation."""
        pos = Position(x=-0.5, y=0.2, z=1.5)
        
        assert pos.x == -0.5
        assert pos.y == 0.2
        assert pos.z == 1.5
    
    def test_default_position(self):
        """Default position should be center."""
        pos = Position()
        
        assert pos.x == 0.0
        assert pos.y == 0.0
        assert pos.z == 1.0


class TestTurn:
    """Tests for Turn class."""
    
    def test_create_turn(self):
        """Basic turn creation."""
        turn = Turn(
            speaker="Alice",
            text="Hello, world!",
            overlap_ms=50,
            emotion="happy",
        )
        
        assert turn.speaker == "Alice"
        assert turn.text == "Hello, world!"
        assert turn.overlap_ms == 50
        assert turn.emotion == "happy"
    
    def test_turn_defaults(self):
        """Turn should have sensible defaults."""
        turn = Turn(speaker="Bob", text="Hi")
        
        assert turn.overlap_ms == 0.0
        assert turn.emotion is None
        assert turn.style == {}


class TestConversation:
    """Tests for Conversation class."""
    
    def test_create_empty_conversation(self):
        """Empty conversation creation."""
        conv = Conversation()
        
        assert conv.turn_count == 0
        assert len(conv.speakers) == 0
    
    def test_add_speaker(self):
        """Adding speakers."""
        conv = Conversation()
        alice = Speaker(name="Alice", voice="af_bella")
        bob = Speaker(name="Bob", voice="am_adam")
        
        conv.add_speaker(alice)
        conv.add_speaker(bob)
        
        assert len(conv.speakers) == 2
        assert conv.get_speaker("Alice") == alice
        assert conv.get_speaker("Bob") == bob
    
    def test_add_turn(self):
        """Adding turns."""
        conv = Conversation()
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        conv.add_speaker(Speaker(name="Bob", voice="am_adam"))
        
        conv.add_turn("Alice", "Hello!")
        conv.add_turn("Bob", "Hi there!")
        conv.add_turn("Alice", "How are you?")
        
        assert conv.turn_count == 3
        assert conv.turns[0].text == "Hello!"
        assert conv.turns[1].speaker == "Bob"
    
    def test_add_turn_unknown_speaker_raises(self):
        """Adding turn for unknown speaker should raise."""
        conv = Conversation()
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        
        with pytest.raises(ValueError) as exc_info:
            conv.add_turn("Unknown", "Hello?")
        
        assert "Unknown" in str(exc_info.value)
    
    def test_add_turn_with_overlap(self):
        """Adding overlapping turn."""
        conv = Conversation()
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        conv.add_speaker(Speaker(name="Bob", voice="am_adam"))
        
        conv.add_turn("Alice", "So what do you think—")
        turn = conv.add_turn("Bob", "Actually...", overlap_ms=200)
        
        assert turn.overlap_ms == 200
    
    def test_add_turn_with_emotion(self):
        """Adding turn with emotion."""
        conv = Conversation()
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        
        turn = conv.add_turn("Alice", "Amazing!", emotion="excited")
        
        assert turn.emotion == "excited"
    
    def test_remove_speaker(self):
        """Removing speakers."""
        conv = Conversation()
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        
        assert conv.remove_speaker("Alice") is True
        assert conv.get_speaker("Alice") is None
        assert conv.remove_speaker("Alice") is False  # Already removed


class TestConversationConfig:
    """Tests for ConversationConfig."""
    
    def test_default_config(self):
        """Default config values."""
        config = ConversationConfig()
        
        assert config.ducking is True
        assert config.duck_amount == 0.7
        assert config.crossfade_ms == 100.0
        assert config.turn_gap_ms == 200.0
    
    def test_custom_config(self):
        """Custom config values."""
        config = ConversationConfig(
            ducking=False,
            duck_amount=0.5,
            crossfade_ms=50,
            turn_gap_ms=300,
        )
        
        assert config.ducking is False
        assert config.duck_amount == 0.5


class TestConversationInitialization:
    """Tests for Conversation initialization."""
    
    def test_init_with_speakers(self):
        """Initialize with speakers list."""
        alice = Speaker(name="Alice", voice="af_bella")
        bob = Speaker(name="Bob", voice="am_adam")
        
        conv = Conversation(speakers=[alice, bob])
        
        assert len(conv.speakers) == 2
    
    def test_init_with_config(self):
        """Initialize with custom config."""
        config = ConversationConfig(crossfade_ms=50)
        conv = Conversation(config=config)
        
        assert conv.config.crossfade_ms == 50


class TestTimelineCalculation:
    """Tests for timeline calculation."""
    
    def test_sequential_timeline(self):
        """Calculate sequential turn timeline."""
        conv = Conversation()
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        conv.add_speaker(Speaker(name="Bob", voice="am_adam"))
        
        conv.add_turn("Alice", "Hello!")      # 0
        conv.add_turn("Bob", "Hi!")           # 1
        conv.add_turn("Alice", "How are you?") # 2
        
        durations = {0: 1.0, 1: 0.5, 2: 1.5}
        timeline = conv.calculate_timeline(durations)
        
        assert len(timeline) == 3
        
        # First turn starts at 0
        assert timeline[0] == (0, 0.0, 1.0)
        
        # Second turn starts after first + gap
        gap = conv.config.turn_gap_ms / 1000
        assert timeline[1][1] == pytest.approx(1.0 + gap, abs=0.01)
    
    def test_overlapping_timeline(self):
        """Calculate timeline with overlapping turns."""
        conv = Conversation(config=ConversationConfig(turn_gap_ms=0))
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        conv.add_speaker(Speaker(name="Bob", voice="am_adam"))
        
        conv.add_turn("Alice", "So what do you—")
        conv.add_turn("Bob", "Actually...", overlap_ms=200)
        
        durations = {0: 1.0, 1: 0.5}
        timeline = conv.calculate_timeline(durations)
        
        # Second turn starts 200ms before first ends
        assert timeline[1][1] == pytest.approx(0.8, abs=0.01)


class TestConversationToAudioGraph:
    """Tests for converting conversation to AudioGraph."""
    
    def test_to_audio_graph_creates_tracks(self):
        """Conversion should create tracks per speaker."""
        conv = Conversation()
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        conv.add_speaker(Speaker(name="Bob", voice="am_adam"))
        
        conv.add_turn("Alice", "Hello!")
        conv.add_turn("Bob", "Hi!")
        
        graph = conv.to_audio_graph()
        
        assert graph.track_count == 2
        assert graph.get_track("Alice") is not None
        assert graph.get_track("Bob") is not None
    
    def test_to_audio_graph_applies_position(self):
        """Conversion should apply spatial positioning."""
        conv = Conversation()
        conv.add_speaker(Speaker(
            name="Alice",
            voice="af_bella",
            position=Position(x=-0.5, y=0, z=1),
        ))
        
        conv.add_turn("Alice", "Left side!")
        
        graph = conv.to_audio_graph()
        track = graph.get_track("Alice")
        
        assert track.pan == -0.5
    
    def test_to_audio_graph_applies_ducking(self):
        """Conversion should setup ducking."""
        conv = Conversation(config=ConversationConfig(
            ducking=True,
            duck_amount=0.8,
        ))
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        conv.add_speaker(Speaker(name="Bob", voice="am_adam"))
        
        conv.add_turn("Alice", "Hello!")
        conv.add_turn("Bob", "Hi!")
        
        graph = conv.to_audio_graph()
        
        alice_track = graph.get_track("Alice")
        bob_track = graph.get_track("Bob")
        
        # Alice ducks for Bob
        assert "Bob" in alice_track.duck_for
        assert alice_track.duck_amount == 0.8
        
        # Bob ducks for Alice
        assert "Alice" in bob_track.duck_for


class TestConversationSerialization:
    """Tests for conversation serialization."""
    
    def test_to_dict(self):
        """Should serialize to dict."""
        conv = Conversation()
        conv.add_speaker(Speaker(
            name="Alice",
            voice="af_bella",
            position=Position(x=-0.5, y=0, z=1),
        ))
        conv.add_turn("Alice", "Hello!")
        
        data = conv.to_dict()
        
        assert "speakers" in data
        assert "turns" in data
        assert "config" in data
        assert data["speakers"][0]["name"] == "Alice"
        assert data["turns"][0]["text"] == "Hello!"
    
    def test_from_dict(self):
        """Should deserialize from dict."""
        data = {
            "speakers": [
                {"name": "Alice", "voice": "af_bella", "position": None, "defaults": {}, "gain_db": 0},
                {"name": "Bob", "voice": "am_adam", "position": {"x": 0.5, "y": 0, "z": 1}, "defaults": {}, "gain_db": 0},
            ],
            "turns": [
                {"speaker": "Alice", "text": "Hello!", "overlap_ms": 0, "emotion": None, "style": {}},
                {"speaker": "Bob", "text": "Hi!", "overlap_ms": 0, "emotion": "happy", "style": {}},
            ],
            "config": {"ducking": True, "duck_amount": 0.7, "crossfade_ms": 100, "turn_gap_ms": 200},
        }
        
        conv = Conversation.from_dict(data)
        
        assert len(conv.speakers) == 2
        assert conv.turn_count == 2
        assert conv.get_speaker("Bob").position.x == 0.5
        assert conv.turns[1].emotion == "happy"
    
    def test_round_trip(self):
        """Serialization should round-trip."""
        original = Conversation(config=ConversationConfig(crossfade_ms=75))
        original.add_speaker(Speaker(name="Alice", voice="af_bella", gain_db=2.0))
        original.add_turn("Alice", "Test!", emotion="neutral")
        
        data = original.to_dict()
        restored = Conversation.from_dict(data)
        
        assert restored.turn_count == 1
        assert restored.config.crossfade_ms == 75
        assert restored.speakers[0].gain_db == 2.0


class TestScriptParsing:
    """Tests for script parsing."""
    
    def test_from_script_basic(self):
        """Should parse basic script format."""
        script = """
        ALICE: Welcome to the show!
        BOB: Thanks for having me.
        ALICE: Let's get started.
        """
        
        conv = Conversation.from_script(script)
        
        assert conv.turn_count == 3
        assert len(conv.speakers) == 2
    
    def test_from_script_auto_creates_speakers(self):
        """Script parsing should auto-create speakers."""
        script = """
        CHARLIE: Hello everyone.
        DAVID: Nice to meet you.
        """
        
        conv = Conversation.from_script(script)
        
        assert conv.get_speaker("Charlie") is not None
        assert conv.get_speaker("David") is not None
    
    def test_from_script_ignores_comments(self):
        """Script parsing should ignore # comments."""
        script = """
        # This is a comment
        ALICE: Hello!
        # Another comment
        BOB: Hi!
        """
        
        conv = Conversation.from_script(script)
        
        assert conv.turn_count == 2


class TestTurnTakingStyles:
    """Tests for turn-taking style application."""
    
    def test_sequential_style(self):
        """Sequential style should have no overlap."""
        conv = Conversation()
        apply_turn_taking_style(conv, TurnTakingStyle.SEQUENTIAL)
        
        assert conv.config.turn_gap_ms == 300
        assert conv.config.crossfade_ms == 0
    
    def test_natural_style(self):
        """Natural style should have small crossfades."""
        conv = Conversation()
        apply_turn_taking_style(conv, TurnTakingStyle.NATURAL)
        
        assert conv.config.turn_gap_ms == 150
        assert conv.config.crossfade_ms == 100
    
    def test_formal_style(self):
        """Formal style should have longer gaps."""
        conv = Conversation()
        apply_turn_taking_style(conv, TurnTakingStyle.FORMAL)
        
        assert conv.config.turn_gap_ms == 500
        assert conv.config.crossfade_ms == 50
    
    def test_casual_style(self):
        """Casual style should have more overlap."""
        conv = Conversation()
        apply_turn_taking_style(conv, TurnTakingStyle.CASUAL)
        
        assert conv.config.turn_gap_ms == 100
        assert conv.config.crossfade_ms == 150


class TestCrossfadeCalculation:
    """Tests for crossfade calculation."""
    
    def test_crossfade_on_speaker_change(self):
        """Should calculate crossfades on speaker changes."""
        conv = Conversation()
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        conv.add_speaker(Speaker(name="Bob", voice="am_adam"))
        
        conv.add_turn("Alice", "Hello!")
        conv.add_turn("Bob", "Hi!")
        conv.add_turn("Alice", "How are you?")
        
        config = CrossfadeConfig(duration_ms=100, apply_on_speaker_change=True)
        crossfades = calculate_crossfades(conv, config)
        
        # Should have crossfade between turns 0-1 and 1-2
        assert len(crossfades) == 2
        assert crossfades[0] == (0, 1, 100)
        assert crossfades[1] == (1, 2, 100)
    
    def test_no_crossfade_same_speaker(self):
        """Should not crossfade between same speaker turns."""
        conv = Conversation()
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        
        conv.add_turn("Alice", "Hello!")
        conv.add_turn("Alice", "It's nice to see you.")
        
        config = CrossfadeConfig(apply_on_speaker_change=True, apply_always=False)
        crossfades = calculate_crossfades(conv, config)
        
        assert len(crossfades) == 0
    
    def test_crossfade_always(self):
        """apply_always should crossfade all turns."""
        conv = Conversation()
        conv.add_speaker(Speaker(name="Alice", voice="af_bella"))
        
        conv.add_turn("Alice", "One")
        conv.add_turn("Alice", "Two")
        conv.add_turn("Alice", "Three")
        
        config = CrossfadeConfig(apply_always=True)
        crossfades = calculate_crossfades(conv, config)
        
        assert len(crossfades) == 2
