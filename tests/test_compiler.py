"""Tests for the compiler module."""

import pytest
from voice_soundboard.compiler import (
    compile_request,
    tokenize,
    normalize_text,
    apply_emotion,
    EMOTIONS,
    PRESETS,
    VOICES,
)
from voice_soundboard.graph import TokenEvent


class TestTextNormalization:
    """Tests for text normalization."""
    
    def test_number_expansion(self):
        assert "one hundred" in normalize_text("There are 100 items")
    
    def test_currency_expansion(self):
        result = normalize_text("It costs $50")
        assert "fifty dollars" in result
    
    def test_currency_with_cents(self):
        result = normalize_text("Price: $19.99")
        assert "nineteen dollars" in result
        assert "ninety nine cents" in result
    
    def test_abbreviation_dr(self):
        result = normalize_text("Dr. Smith is here")
        assert "Doctor Smith" in result
    
    def test_whitespace_normalization(self):
        result = normalize_text("Hello   world")
        assert result == "Hello world"


class TestTokenize:
    """Tests for tokenization."""
    
    def test_simple_sentence(self):
        tokens = tokenize("Hello world!")
        assert len(tokens) == 1
        assert tokens[0].text == "Hello world!"
    
    def test_multiple_sentences(self):
        tokens = tokenize("Hello. World.")
        assert len(tokens) == 2
    
    def test_clause_separation(self):
        tokens = tokenize("Hello, how are you?")
        # Should have at least one pause
        assert any(t.pause_after > 0 for t in tokens)
    
    def test_sentence_end_pause(self):
        tokens = tokenize("Hello world.")
        # Last token should have longer pause
        assert tokens[-1].pause_after >= 0.2


class TestEmotion:
    """Tests for emotion compilation."""
    
    def test_emotion_exists(self):
        assert "happy" in EMOTIONS
        assert "sad" in EMOTIONS
        assert "neutral" in EMOTIONS
    
    def test_happy_speeds_up(self):
        profile = EMOTIONS["happy"]
        assert profile.speed > 1.0
    
    def test_sad_slows_down(self):
        profile = EMOTIONS["sad"]
        assert profile.speed < 1.0
    
    def test_apply_emotion_modifies_prosody(self):
        tokens = [TokenEvent(text="Hello")]
        modified = apply_emotion(tokens, "excited")
        
        # Excited should increase pitch
        assert modified[0].pitch_scale > 1.0
    
    def test_apply_emotion_neutral(self):
        tokens = [TokenEvent(text="Hello")]
        modified = apply_emotion(tokens, "neutral")
        
        # Neutral should not change prosody
        assert modified[0].pitch_scale == 1.0


class TestCompileRequest:
    """Tests for compile_request."""
    
    def test_basic_compilation(self):
        graph = compile_request("Hello world!")
        
        assert graph.tokens
        assert graph.speaker.type == "voice_id"
        assert graph.global_speed == 1.0
    
    def test_explicit_voice(self):
        graph = compile_request("Hello", voice="bm_george")
        
        assert graph.speaker.value == "bm_george"
    
    def test_preset_voice(self):
        graph = compile_request("Hello", preset="narrator")
        
        # Narrator preset uses bm_george
        assert graph.speaker.value == PRESETS["narrator"].voice
    
    def test_preset_speed(self):
        graph = compile_request("Hello", preset="narrator")
        
        assert graph.global_speed == PRESETS["narrator"].speed
    
    def test_explicit_speed_overrides_preset(self):
        graph = compile_request("Hello", preset="narrator", speed=1.5)
        
        assert graph.global_speed == 1.5
    
    def test_emotion_affects_prosody(self):
        graph_excited = compile_request("Hello", emotion="excited")
        graph_neutral = compile_request("Hello", emotion="neutral")
        
        # Excited should have different prosody
        excited_pitch = graph_excited.tokens[0].pitch_scale
        neutral_pitch = graph_neutral.tokens[0].pitch_scale
        
        assert excited_pitch != neutral_pitch
    
    def test_source_text_preserved(self):
        graph = compile_request("Original text here")
        
        assert graph.source_text == "Original text here"


class TestVoiceData:
    """Tests for voice and preset data."""
    
    def test_voices_not_empty(self):
        assert len(VOICES) > 0
    
    def test_presets_not_empty(self):
        assert len(PRESETS) > 0
    
    def test_preset_voices_exist(self):
        for preset_name, config in PRESETS.items():
            assert config.voice in VOICES, f"Preset {preset_name} uses unknown voice {config.voice}"
    
    def test_default_voice_exists(self):
        assert "af_bella" in VOICES
