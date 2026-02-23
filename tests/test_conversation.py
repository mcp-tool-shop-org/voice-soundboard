"""
Tests for v2.3 conversation module.
"""

import pytest
from unittest.mock import Mock, MagicMock
import numpy as np

from voice_soundboard.conversation import (
    Speaker,
    SpeakerStyle,
    Turn,
    TurnType,
    Timeline,
    Conversation,
    ScriptParser,
)


class TestSpeaker:
    """Tests for Speaker class."""
    
    def test_speaker_creation(self):
        speaker = Speaker(name="Alice")
        assert speaker.name == "Alice"
        assert speaker.voice is None
        
    def test_speaker_with_voice(self):
        speaker = Speaker(name="Bob", voice="af_bob", language="en")
        assert speaker.name == "Bob"
        assert speaker.voice == "af_bob"
        assert speaker.language == "en"
        
    def test_speaker_style(self):
        style = SpeakerStyle(
            pitch=1.1,
            speed=0.9,
            emotion="excited",
        )
        speaker = Speaker(name="Alice", style=style)
        
        assert speaker.style.pitch == 1.1
        assert speaker.style.speed == 0.9
        assert speaker.style.emotion == "excited"


class TestTurn:
    """Tests for Turn class."""
    
    def test_turn_creation(self):
        turn = Turn(
            speaker_id="Alice",
            text="Hello, world!",
        )
        assert turn.speaker_id == "Alice"
        assert turn.text == "Hello, world!"
        assert turn.turn_type == TurnType.SPEECH
        
    def test_turn_with_timing(self):
        turn = Turn(
            speaker_id="Alice",
            text="Hello!",
            start_time_ms=0.0,
            duration_ms=1500.0,
        )
        assert turn.start_time == 0.0
        assert turn.duration_ms == 1500.0
        assert turn.end_time_ms is None # Computed later or manual
        
    def test_pause_turn(self):
        turn = Turn(
            speaker_id="",
            text="",
            turn_type=TurnType.PAUSE,
            duration_ms=500.0,
        )
        assert turn.turn_type == TurnType.PAUSE
        assert turn.duration_ms == 500.0


class TestTimeline:
    """Tests for Timeline class."""
    
    def test_timeline_creation(self):
        timeline = Timeline()
        assert len(timeline.turns) == 0
        assert timeline.total_duration == 0.0
        
    def test_add_turn(self):
        timeline = Timeline()
        
        # Turn requires duration to advance timeline
        turn1 = Turn(speaker="Alice", text="Hello!", duration=1.0)
        turn2 = Turn(speaker="Bob", text="Hi there!", duration=1.5)
        
        timeline.add_turn(turn1)
        timeline.add_turn(turn2)
        
        assert len(timeline.turns) == 2
        assert timeline.turns[0].start_time == 0.0
        assert timeline.turns[1].start_time == 1.0 
        # total_duration calculates from turns
        assert timeline.total_duration == 2.5
        
    def test_turn_at_time(self):
        timeline = Timeline()
        
        turn1 = Turn(speaker="Alice", text="First", duration=1.0)
        turn2 = Turn(speaker="Bob", text="Second", duration=1.0)
        
        timeline.add_turn(turn1)
        timeline.add_turn(turn2)
        
        assert timeline.turn_at(0.5) == turn1
        assert timeline.turn_at(1.5) == turn2
        assert timeline.turn_at(2.5) is None


class TestConversation:
    """Tests for Conversation class."""
    
    def test_conversation_creation(self):
        alice = Speaker(name="Alice", voice="af_sky")
        bob = Speaker(name="Bob", voice="am_adam")
        
        conv = Conversation(speakers={"Alice": alice, "Bob": bob})
        
        assert len(conv.speakers) == 2
        assert conv.speakers["Alice"] == alice
        assert conv.speakers["Bob"] == bob
        
    def test_add_turn_by_name(self):
        alice = Speaker(name="Alice")
        bob = Speaker(name="Bob")
        
        conv = Conversation(speakers={"Alice": alice, "Bob": bob})
        
        conv.add("Alice", "Hello, Bob!")
        conv.add("Bob", "Hi, Alice!")
        
        assert len(conv.turns) == 2
        assert conv.turns[0].text == "Hello, Bob!"
        assert conv.turns[1].text == "Hi, Alice!"
        
    def test_add_pause(self):
        alice = Speaker(name="Alice")
        conv = Conversation(speakers={"Alice": alice})
        
        conv.add("Alice", "Hello...")
        conv.add_pause(1000.0)
        conv.add("Alice", "Are you there?")
        
        assert len(conv.turns) == 3
        assert conv.turns[1].turn_type == TurnType.PAUSE
        assert conv.turns[1].duration_ms == 1000.0
        
    def test_conversation_synthesis(self):
        alice = Speaker(name="Alice", voice="af_sky")
        
        conv = Conversation(speakers={"Alice": alice})
        conv.add("Alice", "Hello!")
        
        # Mock engine
        mock_engine = Mock()
        # Engine mock needs to return array or object with audio
        mock_audio = np.zeros(1000, dtype=np.int16)
        # Configure return value to have sample_rate property
        result_mock = Mock(audio=mock_audio)
        result_mock.sample_rate = 24000
        mock_engine.speak.return_value = result_mock
        
        # Synthesize
        result = conv.synthesize(mock_engine)
        
        # Should have called speak
        mock_engine.speak.assert_called()
        assert result.audio is not None


class TestScriptParser:
    """Tests for ScriptParser."""
    
    def test_parse_simple_dialogue(self):
        script = """
        ALICE: Hello, Bob!
        BOB: Hi, Alice! How are you?
        ALICE: I'm doing great, thanks!
        """
        
        parser = ScriptParser()
        turns = parser.parse(script)
        
        # Default normalize_speakers=True so keys are lowercased in internal dict
        # parse() returns Turns, which have speaker_id
        # ScriptParser logic: speaker_id matches script name (normalized?)
        # Let's check Parser output from snippet - it lowercases keys but uses original name for display?
        # Actually register_speaker uses key = name.lower().
        # _parse_lines lowercases if normalize_speakers is True.
        
        assert len(turns) == 3
        
        # Verify turns
        assert turns[0].speaker_id == "alice"
        assert turns[0].text == "Hello, Bob!"
        assert turns[1].speaker_id == "bob"
        
    def test_parse_with_bracket_format(self):
        script = """
        [ALICE] Hello!
        [BOB] Hi there.
        [ALICE] Nice to meet you.
        """
        
        parser = ScriptParser()
        turns = parser.parse(script)
        
        assert len(turns) == 3
        assert turns[0].speaker_id == "alice"
        
    def test_parse_empty_script(self):
        parser = ScriptParser()
        turns = parser.parse("")
        
        assert len(turns) == 0
        
    def test_parse_comments(self):
        script = """
        # This is a comment
        ALICE: Hello!
        # Another comment
        BOB: Hi!
        """
        
        parser = ScriptParser()
        turns = parser.parse(script)
        
        # Comments should be ignored
        assert len(turns) == 2
