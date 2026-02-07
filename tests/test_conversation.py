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
            speaker="Alice",
            text="Hello, world!",
        )
        assert turn.speaker == "Alice"
        assert turn.text == "Hello, world!"
        assert turn.turn_type == TurnType.SPEECH
        
    def test_turn_with_timing(self):
        turn = Turn(
            speaker="Alice",
            text="Hello!",
            start_time=0.0,
            duration=1.5,
        )
        assert turn.start_time == 0.0
        assert turn.duration == 1.5
        assert turn.end_time == 1.5
        
    def test_pause_turn(self):
        turn = Turn(
            speaker="",
            text="",
            turn_type=TurnType.PAUSE,
            duration=0.5,
        )
        assert turn.turn_type == TurnType.PAUSE
        assert turn.duration == 0.5


class TestTimeline:
    """Tests for Timeline class."""
    
    def test_timeline_creation(self):
        timeline = Timeline()
        assert len(timeline.turns) == 0
        assert timeline.total_duration == 0.0
        
    def test_add_turn(self):
        timeline = Timeline()
        
        turn1 = Turn(speaker="Alice", text="Hello!", duration=1.0)
        turn2 = Turn(speaker="Bob", text="Hi there!", duration=1.5)
        
        timeline.add_turn(turn1)
        timeline.add_turn(turn2)
        
        assert len(timeline.turns) == 2
        assert timeline.turns[0].start_time == 0.0
        assert timeline.turns[1].start_time == 1.0
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
        
        conv = Conversation(speakers=[alice, bob])
        
        assert len(conv.speakers) == 2
        assert conv.get_speaker("Alice") == alice
        assert conv.get_speaker("Bob") == bob
        
    def test_add_turn_by_name(self):
        alice = Speaker(name="Alice")
        bob = Speaker(name="Bob")
        
        conv = Conversation(speakers=[alice, bob])
        
        conv.add_turn("Alice", "Hello, Bob!")
        conv.add_turn("Bob", "Hi, Alice!")
        
        assert len(conv.timeline.turns) == 2
        assert conv.timeline.turns[0].text == "Hello, Bob!"
        assert conv.timeline.turns[1].text == "Hi, Alice!"
        
    def test_add_pause(self):
        conv = Conversation(speakers=[Speaker(name="Alice")])
        
        conv.add_turn("Alice", "Hello...")
        conv.add_pause(1.0)
        conv.add_turn("Alice", "Are you there?")
        
        assert len(conv.timeline.turns) == 3
        assert conv.timeline.turns[1].turn_type == TurnType.PAUSE
        assert conv.timeline.turns[1].duration == 1.0
        
    def test_conversation_synthesis(self):
        alice = Speaker(name="Alice", voice="af_sky")
        
        conv = Conversation(speakers=[alice])
        conv.add_turn("Alice", "Hello!")
        
        # Mock engine
        mock_engine = Mock()
        mock_engine.speak.return_value = Mock(
            audio=np.zeros(1000, dtype=np.int16),
        )
        
        # Synthesize
        audio = conv.synthesize(mock_engine)
        
        # Should have called speak
        mock_engine.speak.assert_called()


class TestScriptParser:
    """Tests for ScriptParser."""
    
    def test_parse_simple_dialogue(self):
        script = """
        ALICE: Hello, Bob!
        BOB: Hi, Alice! How are you?
        ALICE: I'm doing great, thanks!
        """
        
        parser = ScriptParser()
        conversation = parser.parse(script)
        
        assert len(conversation.speakers) == 2
        assert len(conversation.timeline.turns) == 3
        
        # Verify turns
        assert conversation.timeline.turns[0].speaker == "ALICE"
        assert conversation.timeline.turns[0].text == "Hello, Bob!"
        assert conversation.timeline.turns[1].speaker == "BOB"
        
    def test_parse_with_stage_directions(self):
        script = """
        ALICE: Hello!
        [pause 0.5]
        BOB: Hi there.
        [pause 1.0]
        ALICE: Nice to meet you.
        """
        
        parser = ScriptParser()
        conversation = parser.parse(script)
        
        # Should include pauses
        assert any(t.turn_type == TurnType.PAUSE for t in conversation.timeline.turns)
        
    def test_parse_with_emotions(self):
        script = """
        ALICE (excited): I got the job!
        BOB (surprised): That's amazing!
        """
        
        parser = ScriptParser()
        conversation = parser.parse(script)
        
        # Check emotions are captured
        assert conversation.timeline.turns[0].metadata.get("emotion") == "excited"
        assert conversation.timeline.turns[1].metadata.get("emotion") == "surprised"
        
    def test_parse_empty_script(self):
        parser = ScriptParser()
        conversation = parser.parse("")
        
        assert len(conversation.timeline.turns) == 0
        
    def test_parse_comments(self):
        script = """
        # This is a comment
        ALICE: Hello!
        # Another comment
        BOB: Hi!
        """
        
        parser = ScriptParser()
        conversation = parser.parse(script)
        
        # Comments should be ignored
        assert len(conversation.timeline.turns) == 2


class TestConversationExport:
    """Tests for conversation export/import."""
    
    def test_export_to_dict(self):
        alice = Speaker(name="Alice", voice="af_sky")
        bob = Speaker(name="Bob", voice="am_adam")
        
        conv = Conversation(speakers=[alice, bob])
        conv.add_turn("Alice", "Hello!")
        conv.add_turn("Bob", "Hi!")
        
        data = conv.to_dict()
        
        assert "speakers" in data
        assert "turns" in data
        assert len(data["speakers"]) == 2
        assert len(data["turns"]) == 2
        
    def test_import_from_dict(self):
        data = {
            "speakers": [
                {"name": "Alice", "voice": "af_sky"},
                {"name": "Bob", "voice": "am_adam"},
            ],
            "turns": [
                {"speaker": "Alice", "text": "Hello!"},
                {"speaker": "Bob", "text": "Hi there!"},
            ],
        }
        
        conv = Conversation.from_dict(data)
        
        assert len(conv.speakers) == 2
        assert len(conv.timeline.turns) == 2
        assert conv.timeline.turns[0].speaker == "Alice"
