"""
Tests for v2.3 conversation module.
"""

from unittest.mock import Mock
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


class TestSpeakerVoiceMappings:
    """Tests for Speaker creation with voice mappings and style handling."""

    def test_speaker_defaults(self):
        speaker = Speaker()
        assert speaker.name == ""
        assert speaker.voice is None
        assert speaker.language == "en"
        assert speaker.speed == 1.0
        assert speaker.pitch == 1.0
        assert speaker.volume == 1.0
        assert speaker.custom_params == {}

    def test_speaker_emotion_from_style_preset(self):
        speaker = Speaker(name="Alice", style="friendly")
        assert speaker.emotion == "friendly"

    def test_speaker_emotion_from_speaker_style_object(self):
        style = SpeakerStyle(emotion="calm")
        speaker = Speaker(name="Bob", style=style)
        assert speaker.emotion == "calm"

    def test_speaker_emotion_when_no_style(self):
        speaker = Speaker(name="Charlie")
        assert speaker.emotion == "neutral"

    def test_speaker_emotion_from_unknown_string_style(self):
        speaker = Speaker(name="Dave", style="sarcastic")
        # "sarcastic" is not in SpeakerStylePreset, stays as string
        assert speaker.emotion == "sarcastic"

    def test_speaker_with_style_creates_copy(self):
        original = Speaker(name="Alice", voice="af_bella", speed=1.2)
        copy = original.with_style("excited")
        assert copy.name == "Alice"
        assert copy.voice == "af_bella"
        assert copy.speed == 1.2
        assert copy.emotion == "excited"
        # Original is unchanged
        assert original.emotion == "neutral"

    def test_speaker_with_speed_creates_copy(self):
        original = Speaker(name="Bob", voice="am_adam", speed=1.0)
        copy = original.with_speed(1.5)
        assert copy.speed == 1.5
        assert original.speed == 1.0

    def test_speaker_to_compile_params_basic(self):
        speaker = Speaker(voice="af_bella")
        params = speaker.to_compile_params()
        assert params["voice"] == "af_bella"
        assert params["emotion"] == "neutral"
        assert "speed" not in params  # default 1.0 excluded
        assert "pitch" not in params  # default 1.0 excluded

    def test_speaker_to_compile_params_with_overrides(self):
        speaker = Speaker(voice="am_adam", speed=1.3, pitch=0.8)
        params = speaker.to_compile_params()
        assert params["voice"] == "am_adam"
        assert params["speed"] == 1.3
        assert params["pitch"] == 0.8

    def test_speaker_to_compile_params_with_custom_params(self):
        speaker = Speaker(voice="af_bella", custom_params={"backend": "kokoro"})
        params = speaker.to_compile_params()
        assert params["backend"] == "kokoro"

    def test_speaker_metadata_fields(self):
        speaker = Speaker(
            name="Narrator",
            description="Main narrator",
            avatar_url="https://example.com/avatar.png",
        )
        assert speaker.description == "Main narrator"
        assert speaker.avatar_url == "https://example.com/avatar.png"


class TestTurnManagement:
    """Tests for Turn factory methods, ordering, and properties."""

    def test_speech_factory(self):
        turn = Turn.speech("alice", "Hello!")
        assert turn.speaker_id == "alice"
        assert turn.text == "Hello!"
        assert turn.turn_type == TurnType.SPEECH
        assert turn.is_speech is True
        assert turn.is_pause is False
        assert turn.is_action is False

    def test_pause_factory(self):
        turn = Turn.pause(500)
        assert turn.speaker_id == ""
        assert turn.turn_type == TurnType.PAUSE
        assert turn.duration_ms == 500
        assert turn.is_pause is True

    def test_action_factory(self):
        turn = Turn.action("bob", "laughs")
        assert turn.speaker_id == "bob"
        assert turn.text == "[laughs]"
        assert turn.turn_type == TurnType.ACTION
        assert turn.is_action is True

    def test_speech_factory_with_metadata(self):
        turn = Turn.speech("alice", "Hello!", emotion="happy", priority=1)
        assert turn.metadata["emotion"] == "happy"
        assert turn.metadata["priority"] == 1

    def test_turn_speaker_alias(self):
        turn = Turn(speaker="alice", text="Hi")
        assert turn.speaker_id == "alice"
        assert turn.speaker == "alice"

    def test_turn_duration_seconds_to_ms(self):
        turn = Turn(speaker_id="alice", text="Hi", duration=2.5)
        assert turn.duration_ms == 2500.0

    def test_turn_duration_ms_to_seconds(self):
        turn = Turn(speaker_id="alice", text="Hi", duration_ms=3000)
        assert turn.duration == 3.0

    def test_turn_with_timing_creates_copy(self):
        original = Turn.speech("alice", "Hello!")
        timed = original.with_timing(start_ms=1000, duration_ms=500)
        assert timed.start_time_ms == 1000
        assert timed.duration_ms == 500
        assert timed.end_time_ms == 1500
        assert timed.audio_duration_ms == 500
        # Original unchanged
        assert original.start_time_ms is None

    def test_turn_start_time_property(self):
        turn = Turn.speech("alice", "Hello!")
        turn.start_time = 1.5
        assert turn.start_time_ms == 1500

    def test_turn_start_time_none(self):
        turn = Turn.speech("alice", "Hello!")
        assert turn.start_time is None
        turn.start_time = None
        assert turn.start_time_ms is None


class TestConversationAddTurnOrdering:
    """Tests for Conversation add/turn ordering and chaining."""

    def test_add_returns_self_for_chaining(self):
        conv = Conversation(speakers={"a": Speaker(name="A")})
        result = conv.add("a", "Hello!")
        assert result is conv

    def test_add_speaker_returns_self_for_chaining(self):
        conv = Conversation()
        result = conv.add_speaker("a", Speaker(name="A"))
        assert result is conv

    def test_add_pause_returns_self_for_chaining(self):
        conv = Conversation()
        result = conv.add_pause(500)
        assert result is conv

    def test_chained_add_calls(self):
        conv = Conversation(speakers={
            "a": Speaker(name="A"),
            "b": Speaker(name="B"),
        })
        conv.add("a", "First").add("b", "Second").add("a", "Third")
        assert len(conv.turns) == 3
        assert conv.turns[0].text == "First"
        assert conv.turns[1].text == "Second"
        assert conv.turns[2].text == "Third"

    def test_add_unknown_speaker_raises(self):
        conv = Conversation(speakers={"a": Speaker(name="A")})
        try:
            conv.add("unknown", "Hello!")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown speaker" in str(e)

    def test_add_action_unknown_speaker_raises(self):
        conv = Conversation(speakers={"a": Speaker(name="A")})
        try:
            conv.add_action("unknown", "laughs")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown speaker" in str(e)

    def test_turn_ordering_preserved(self):
        conv = Conversation(speakers={
            "a": Speaker(name="A"),
            "b": Speaker(name="B"),
        })
        conv.add("a", "Line 1")
        conv.add("b", "Line 2")
        conv.add_pause(500)
        conv.add("a", "Line 3")

        turns = conv.turns
        assert turns[0].speaker_id == "a"
        assert turns[1].speaker_id == "b"
        assert turns[2].is_pause
        assert turns[3].speaker_id == "a"

    def test_add_speaker_then_add_turn(self):
        conv = Conversation()
        conv.add_speaker("narrator", Speaker(name="Narrator", voice="af_bella"))
        conv.add("narrator", "Once upon a time...")
        assert len(conv.turns) == 1
        assert conv.turns[0].speaker_id == "narrator"

    def test_add_action_turn(self):
        conv = Conversation(speakers={"a": Speaker(name="A")})
        conv.add_action("a", "clears throat")
        assert len(conv.turns) == 1
        assert conv.turns[0].is_action
        assert "[clears throat]" in conv.turns[0].text

    def test_from_script(self):
        conv = Conversation(speakers={
            "a": Speaker(name="A"),
            "b": Speaker(name="B"),
        })
        conv.from_script([
            ("a", "Hello!"),
            ("b", "Hi!"),
            ("a", "How are you?"),
        ])
        assert len(conv.turns) == 3
        assert conv.turns[2].text == "How are you?"

    def test_clear(self):
        conv = Conversation(speakers={"a": Speaker(name="A")})
        conv.add("a", "Hello!")
        conv.add("a", "World!")
        assert len(conv.turns) == 2
        conv.clear()
        assert len(conv.turns) == 0

    def test_speakers_returns_copy(self):
        conv = Conversation(speakers={"a": Speaker(name="A")})
        speakers = conv.speakers
        speakers["b"] = Speaker(name="B")
        # Original should be unchanged
        assert len(conv.speakers) == 1

    def test_turns_returns_copy(self):
        conv = Conversation(speakers={"a": Speaker(name="A")})
        conv.add("a", "Hello!")
        turns = conv.turns
        turns.append(Turn.speech("a", "Extra"))
        # Original should be unchanged
        assert len(conv.turns) == 1


class TestScriptParserExtended:
    """Extended tests for ScriptParser."""

    def test_colon_format_explicit(self):
        script = "ALICE: Hello!"
        parser = ScriptParser()
        turns = parser.parse(script, format="colon")
        assert len(turns) == 1
        assert turns[0].text == "Hello!"

    def test_bracket_format_explicit(self):
        script = "[ALICE] Hello!"
        parser = ScriptParser()
        turns = parser.parse(script, format="bracket")
        assert len(turns) == 1
        assert turns[0].text == "Hello!"

    def test_colon_format_ignores_bracket(self):
        script = "[ALICE] Hello!"
        parser = ScriptParser()
        turns = parser.parse(script, format="colon")
        assert len(turns) == 0

    def test_bracket_format_ignores_colon(self):
        script = "ALICE: Hello!"
        parser = ScriptParser()
        turns = parser.parse(script, format="bracket")
        assert len(turns) == 0

    def test_normalize_speakers_true(self):
        script = "ALICE: Hello!\nBOB: Hi!"
        parser = ScriptParser(normalize_speakers=True)
        turns = parser.parse(script)
        assert turns[0].speaker_id == "alice"
        assert turns[1].speaker_id == "bob"

    def test_normalize_speakers_false(self):
        script = "ALICE: Hello!\nBOB: Hi!"
        parser = ScriptParser(normalize_speakers=False)
        turns = parser.parse(script)
        assert turns[0].speaker_id == "ALICE"
        assert turns[1].speaker_id == "BOB"

    def test_infer_speakers(self):
        script = "ALICE: Hello!"
        parser = ScriptParser(infer_speakers=True)
        parser.parse(script)
        speakers = parser.get_speakers()
        assert "alice" in speakers
        assert speakers["alice"].name == "ALICE"

    def test_infer_speakers_disabled(self):
        script = "ALICE: Hello!"
        parser = ScriptParser(infer_speakers=False)
        parser.parse(script)
        speakers = parser.get_speakers()
        assert len(speakers) == 0

    def test_register_speaker(self):
        parser = ScriptParser()
        custom = Speaker(name="Alice", voice="af_bella")
        parser.register_speaker("ALICE", custom)
        speakers = parser.get_speakers()
        assert "alice" in speakers
        assert speakers["alice"].voice == "af_bella"

    def test_registered_speaker_used_over_inferred(self):
        parser = ScriptParser()
        custom = Speaker(name="Alice", voice="custom_voice")
        parser.register_speaker("ALICE", custom)
        parser.parse("ALICE: Hello!")
        speakers = parser.get_speakers()
        assert speakers["alice"].voice == "custom_voice"

    def test_action_detection_asterisk(self):
        script = "ALICE: *laughs*"
        parser = ScriptParser()
        turns = parser.parse(script)
        assert len(turns) == 1
        assert turns[0].is_action

    def test_action_detection_parentheses(self):
        script = "ALICE: (sighs deeply)"
        parser = ScriptParser()
        turns = parser.parse(script)
        assert len(turns) == 1
        assert turns[0].is_action

    def test_non_action_text(self):
        script = "ALICE: Hello, how are you?"
        parser = ScriptParser()
        turns = parser.parse(script)
        assert len(turns) == 1
        assert turns[0].is_speech

    def test_multiline_script(self):
        script = """
        ALICE: Line one.
        BOB: Line two.
        CHARLIE: Line three.
        ALICE: Line four.
        """
        parser = ScriptParser()
        turns = parser.parse(script)
        assert len(turns) == 4
        assert turns[3].speaker_id == "alice"

    def test_get_speakers_returns_copy(self):
        parser = ScriptParser()
        parser.register_speaker("ALICE", Speaker(name="Alice"))
        speakers = parser.get_speakers()
        speakers["bob"] = Speaker(name="Bob")
        # Original should be unchanged
        assert len(parser.get_speakers()) == 1

    def test_whitespace_handling(self):
        script = "ALICE:    Hello with spaces!   "
        parser = ScriptParser()
        turns = parser.parse(script)
        assert len(turns) == 1
        assert turns[0].text == "Hello with spaces!"

    def test_speaker_name_with_numbers(self):
        script = "AGENT007: Mission accepted."
        parser = ScriptParser()
        turns = parser.parse(script)
        assert len(turns) == 1
        assert turns[0].speaker_id == "agent007"

    def test_speaker_name_with_underscore(self):
        script = "DR_SMITH: The results are in."
        parser = ScriptParser()
        turns = parser.parse(script)
        assert len(turns) == 1
        assert turns[0].speaker_id == "dr_smith"


class TestConversationEdgeCases:
    """Edge cases: empty conversation, single speaker, duplicate speakers."""

    def test_empty_conversation_no_speakers(self):
        conv = Conversation()
        assert len(conv.speakers) == 0
        assert len(conv.turns) == 0

    def test_empty_conversation_synthesis(self):
        conv = Conversation()
        mock_engine = Mock()
        result = conv.synthesize(mock_engine)
        assert len(result.audio) == 0
        assert result.sample_rate == 24000
        assert result.duration_seconds == 0.0
        assert result.duration_ms == 0.0
        mock_engine.speak.assert_not_called()

    def test_single_speaker_conversation(self):
        conv = Conversation(speakers={"narrator": Speaker(name="Narrator")})
        conv.add("narrator", "Once upon a time.")
        conv.add("narrator", "The end.")
        assert len(conv.turns) == 2
        assert all(t.speaker_id == "narrator" for t in conv.turns)

    def test_duplicate_speaker_id_overwrites(self):
        alice1 = Speaker(name="Alice", voice="voice_1")
        alice2 = Speaker(name="Alice v2", voice="voice_2")
        conv = Conversation(speakers={"alice": alice1})
        conv.add_speaker("alice", alice2)
        assert conv.speakers["alice"].voice == "voice_2"

    def test_conversation_with_only_pauses(self):
        conv = Conversation()
        conv.add_pause(500)
        conv.add_pause(1000)
        assert len(conv.turns) == 2
        assert all(t.is_pause for t in conv.turns)

    def test_gap_ms_default(self):
        conv = Conversation()
        assert conv._gap_ms == 100

    def test_gap_ms_custom(self):
        conv = Conversation(gap_ms=250)
        assert conv._gap_ms == 250


class TestTimelineExtended:
    """Extended tests for Timeline."""

    def test_empty_timeline_total_duration(self):
        tl = Timeline()
        assert tl.total_duration_ms == 0
        assert tl.total_duration == 0.0

    def test_compute_timing(self):
        turns = [
            Turn.speech("alice", "Hello!"),
            Turn.speech("bob", "Hi!"),
        ]
        tl = Timeline(turns=turns, gap_ms=100)
        timed = tl.compute_timing([500, 300])

        assert len(timed.turns) == 2
        assert timed.turns[0].start_time_ms == 0
        assert timed.turns[0].duration_ms == 500
        assert timed.turns[0].end_time_ms == 500
        # Second turn starts after first duration + gap
        assert timed.turns[1].start_time_ms == 600
        assert timed.turns[1].duration_ms == 300
        assert timed.turns[1].end_time_ms == 900

    def test_compute_timing_with_pause(self):
        turns = [
            Turn.speech("alice", "Hello!"),
            Turn.pause(1000),
            Turn.speech("alice", "Still here?"),
        ]
        tl = Timeline(turns=turns, gap_ms=100)
        timed = tl.compute_timing([500, 1000, 400])

        assert timed.turns[0].start_time_ms == 0
        assert timed.turns[0].end_time_ms == 500
        # Pause starts after speech + gap
        assert timed.turns[1].start_time_ms == 600
        assert timed.turns[1].duration_ms == 1000
        # Third turn starts after pause (no gap added for pause)
        assert timed.turns[2].start_time_ms == 1600

    def test_get_speaker_timeline(self):
        tl = Timeline()
        turn_a = Turn(speaker="alice", text="A1", duration=1.0)
        turn_b = Turn(speaker="bob", text="B1", duration=1.0)
        turn_a2 = Turn(speaker="alice", text="A2", duration=1.0)
        tl.add_turn(turn_a)
        tl.add_turn(turn_b)
        tl.add_turn(turn_a2)

        alice_turns = tl.get_speaker_timeline("alice")
        assert len(alice_turns) == 2
        assert alice_turns[0].text == "A1"
        assert alice_turns[1].text == "A2"

        bob_turns = tl.get_speaker_timeline("bob")
        assert len(bob_turns) == 1

    def test_get_speaker_timeline_empty(self):
        tl = Timeline()
        result = tl.get_speaker_timeline("nobody")
        assert result == []

    def test_turn_at_boundaries(self):
        tl = Timeline()
        turn = Turn(speaker="alice", text="Hello", duration=1.0)
        tl.add_turn(turn)
        # At exact start
        assert tl.turn_at(0.0) == turn
        # Just before end
        assert tl.turn_at(0.999) == turn
        # At exact end (exclusive)
        assert tl.turn_at(1.0) is None

    def test_total_duration_ms_from_end_time(self):
        turn = Turn.speech("alice", "Hello!")
        timed = turn.with_timing(0, 1500)
        tl = Timeline(turns=[timed])
        assert tl.total_duration_ms == 1500


class TestConversationResult:
    """Tests for ConversationResult."""

    def test_duration_calculations(self):
        from voice_soundboard.conversation.conversation import ConversationResult
        audio = np.zeros(48000, dtype=np.float32)
        result = ConversationResult(
            audio=audio,
            sample_rate=24000,
            timeline=Timeline(),
        )
        assert result.duration_seconds == 2.0
        assert result.duration_ms == 2000.0

    def test_empty_result_duration(self):
        from voice_soundboard.conversation.conversation import ConversationResult
        audio = np.array([], dtype=np.float32)
        result = ConversationResult(
            audio=audio,
            sample_rate=24000,
            timeline=Timeline(),
        )
        assert result.duration_seconds == 0.0


class TestParseScriptConvenience:
    """Tests for the parse_script convenience function."""

    def test_parse_script_function(self):
        from voice_soundboard.conversation.parser import parse_script
        turns = parse_script("ALICE: Hello!\nBOB: Hi!")
        assert len(turns) == 2
        assert turns[0].speaker_id == "alice"
        assert turns[1].speaker_id == "bob"

    def test_parse_script_with_kwargs(self):
        from voice_soundboard.conversation.parser import parse_script
        turns = parse_script("ALICE: Hello!", normalize_speakers=False)
        assert turns[0].speaker_id == "ALICE"
