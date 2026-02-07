"""
Ducking System Tests - Gain envelope processing.

Tests for the ducking system that applies gain envelopes to speech
following events, creating the perception of audio mixing without
violating timeline invariants.
"""

import pytest
import numpy as np

from voice_soundboard.runtime.ducking import (
    DuckingEnvelope,
    DuckingProcessor,
    apply_gain_envelope,
    apply_constant_gain,
    process_timeline_with_ducking,
    DUCKING_SUBTLE,
    DUCKING_STANDARD,
    DUCKING_DRAMATIC,
    DUCKING_PODCAST,
)


class TestDuckingEnvelope:
    """Tests for DuckingEnvelope dataclass."""
    
    def test_default_values(self):
        """Default envelope has sensible values."""
        envelope = DuckingEnvelope()
        
        assert envelope.gain == 0.5
        assert envelope.fade_out_ms == 50
        assert envelope.fade_in_ms == 150
    
    def test_custom_values(self):
        """Custom envelope values."""
        envelope = DuckingEnvelope(gain=0.3, fade_out_ms=100, fade_in_ms=300)
        
        assert envelope.gain == 0.3
        assert envelope.fade_out_ms == 100
        assert envelope.fade_in_ms == 300
    
    def test_gain_validation_low(self):
        """Gain below 0.0 raises error."""
        with pytest.raises(ValueError, match="gain must be 0.0-1.0"):
            DuckingEnvelope(gain=-0.1)
    
    def test_gain_validation_high(self):
        """Gain above 1.0 raises error."""
        with pytest.raises(ValueError, match="gain must be 0.0-1.0"):
            DuckingEnvelope(gain=1.5)
    
    def test_fade_out_validation(self):
        """Negative fade_out_ms raises error."""
        with pytest.raises(ValueError, match="fade_out_ms must be >= 0"):
            DuckingEnvelope(fade_out_ms=-10)
    
    def test_fade_in_validation(self):
        """Negative fade_in_ms raises error."""
        with pytest.raises(ValueError, match="fade_in_ms must be >= 0"):
            DuckingEnvelope(fade_in_ms=-10)
    
    def test_frozen(self):
        """Envelope is immutable."""
        envelope = DuckingEnvelope()
        
        with pytest.raises(Exception):  # FrozenInstanceError
            envelope.gain = 0.7


class TestApplyGainEnvelope:
    """Tests for apply_gain_envelope function."""
    
    def test_full_gain_unchanged(self):
        """Gain=1.0 returns unchanged audio."""
        pcm = np.array([0.5, 0.5, 0.5], dtype=np.float32)
        
        result = apply_gain_envelope(pcm, gain=1.0, fade_in_samples=10)
        
        np.testing.assert_array_equal(result, pcm)
    
    def test_empty_audio(self):
        """Empty audio returns empty."""
        pcm = np.array([], dtype=np.float32)
        
        result = apply_gain_envelope(pcm, gain=0.5, fade_in_samples=10)
        
        assert len(result) == 0
    
    def test_half_gain_with_fade(self):
        """50% gain with fade-in."""
        pcm = np.ones(1000, dtype=np.float32)
        
        result = apply_gain_envelope(pcm, gain=0.5, fade_in_samples=500)
        
        # First sample should be at 50% gain
        assert abs(result[0] - 0.5) < 0.01
        
        # Middle of fade should be ~75%
        assert abs(result[250] - 0.75) < 0.05
        
        # After fade should be ~100%
        assert abs(result[500] - 1.0) < 0.01
        assert abs(result[999] - 1.0) < 0.01
    
    def test_zero_fade_in(self):
        """Zero fade-in applies constant gain."""
        pcm = np.ones(100, dtype=np.float32)
        
        result = apply_gain_envelope(pcm, gain=0.5, fade_in_samples=0)
        
        # All samples at 50%
        np.testing.assert_array_almost_equal(result, np.full(100, 0.5))
    
    def test_fade_longer_than_audio(self):
        """Fade longer than audio still works."""
        pcm = np.ones(100, dtype=np.float32)
        
        result = apply_gain_envelope(pcm, gain=0.5, fade_in_samples=1000)
        
        # Should fade as much as possible
        assert result[0] < result[99]
        assert abs(result[0] - 0.5) < 0.01
    
    def test_preserves_waveform_shape(self):
        """Gain preserves relative waveform shape."""
        # Sine wave
        pcm = np.sin(np.linspace(0, 2 * np.pi, 100)).astype(np.float32)
        
        result = apply_gain_envelope(pcm, gain=0.5, fade_in_samples=50)
        
        # Waveform shape preserved (scaled)
        # At position 0, should be ~half amplitude
        assert abs(result[25]) < abs(pcm[25])


class TestApplyConstantGain:
    """Tests for apply_constant_gain function."""
    
    def test_full_gain(self):
        """Gain=1.0 returns unchanged."""
        pcm = np.array([0.5, 0.5], dtype=np.float32)
        
        result = apply_constant_gain(pcm, gain=1.0)
        
        np.testing.assert_array_equal(result, pcm)
    
    def test_half_gain(self):
        """Gain=0.5 halves amplitude."""
        pcm = np.array([1.0, 0.5, 0.25], dtype=np.float32)
        
        result = apply_constant_gain(pcm, gain=0.5)
        
        np.testing.assert_array_almost_equal(result, [0.5, 0.25, 0.125])
    
    def test_empty_input(self):
        """Empty input returns empty."""
        pcm = np.array([], dtype=np.float32)
        
        result = apply_constant_gain(pcm, gain=0.5)
        
        assert len(result) == 0


class TestDuckingProcessor:
    """Tests for DuckingProcessor class."""
    
    def test_initial_state(self):
        """Processor starts with no ducking."""
        processor = DuckingProcessor()
        
        assert not processor.is_ducking
    
    def test_set_ducking(self):
        """set_ducking enables ducking state."""
        processor = DuckingProcessor()
        envelope = DuckingEnvelope(gain=0.5)
        
        processor.set_ducking(envelope)
        
        assert processor.is_ducking
    
    def test_clear_ducking(self):
        """clear_ducking disables ducking state."""
        processor = DuckingProcessor()
        processor.set_ducking(DuckingEnvelope())
        
        processor.clear_ducking()
        
        assert not processor.is_ducking
    
    def test_process_speech_without_ducking(self):
        """Speech without ducking is unchanged."""
        processor = DuckingProcessor(sample_rate=24000)
        pcm = np.ones(100, dtype=np.float32)
        
        result = processor.process_speech(pcm)
        
        np.testing.assert_array_equal(result, pcm)
    
    def test_process_speech_with_ducking(self):
        """Speech with ducking has gain applied."""
        processor = DuckingProcessor(sample_rate=24000)
        processor.set_ducking(DuckingEnvelope(gain=0.5, fade_in_ms=100))
        pcm = np.ones(2400, dtype=np.float32)  # 100ms at 24kHz
        
        result = processor.process_speech(pcm)
        
        # First sample should be ducked
        assert result[0] < pcm[0]
        assert abs(result[0] - 0.5) < 0.01
    
    def test_ducking_is_single_shot(self):
        """Ducking clears after processing speech."""
        processor = DuckingProcessor(sample_rate=24000)
        processor.set_ducking(DuckingEnvelope(gain=0.5))
        pcm = np.ones(100, dtype=np.float32)
        
        # First speech - ducked
        result1 = processor.process_speech(pcm)
        assert result1[0] < 1.0
        
        # Second speech - not ducked
        result2 = processor.process_speech(pcm)
        np.testing.assert_array_equal(result2, pcm)
    
    def test_reset(self):
        """reset clears all state."""
        processor = DuckingProcessor()
        processor.set_ducking(DuckingEnvelope())
        
        processor.reset()
        
        assert not processor.is_ducking
    
    def test_sample_rate_property(self):
        """Sample rate is accessible."""
        processor = DuckingProcessor(sample_rate=22050)
        
        assert processor.sample_rate == 22050


class TestProcessTimelineWithDucking:
    """Tests for process_timeline_with_ducking function."""
    
    def test_event_sets_ducking(self):
        """Event with ducking affects following speech."""
        event_pcm = np.array([0.5, 0.5], dtype=np.float32)
        speech_pcm = np.ones(2400, dtype=np.float32)  # 100ms
        
        timeline = [
            ("event", event_pcm, DuckingEnvelope(gain=0.5, fade_in_ms=100)),
            ("speech", speech_pcm, None),
        ]
        
        results = list(process_timeline_with_ducking(timeline, sample_rate=24000))
        
        # Event unchanged
        np.testing.assert_array_equal(results[0], event_pcm)
        
        # Speech ducked
        assert results[1][0] < speech_pcm[0]
    
    def test_event_without_ducking(self):
        """Event without ducking doesn't affect speech."""
        event_pcm = np.array([0.5], dtype=np.float32)
        speech_pcm = np.ones(100, dtype=np.float32)
        
        timeline = [
            ("event", event_pcm, None),  # No ducking
            ("speech", speech_pcm, None),
        ]
        
        results = list(process_timeline_with_ducking(timeline))
        
        # Speech unchanged
        np.testing.assert_array_equal(results[1], speech_pcm)
    
    def test_multiple_events_multiple_speech(self):
        """Complex timeline with ducking."""
        e1 = np.array([0.5], dtype=np.float32)
        s1 = np.ones(100, dtype=np.float32)
        e2 = np.array([0.7], dtype=np.float32)
        s2 = np.ones(100, dtype=np.float32)
        
        timeline = [
            ("event", e1, DuckingEnvelope(gain=0.3)),
            ("speech", s1, None),
            ("event", e2, DuckingEnvelope(gain=0.7)),
            ("speech", s2, None),
        ]
        
        results = list(process_timeline_with_ducking(timeline))
        
        # First speech heavily ducked
        assert results[1][0] < 0.5
        
        # Second speech lightly ducked
        assert 0.5 < results[3][0] < 1.0
    
    def test_speech_only_unchanged(self):
        """Speech-only timeline unchanged."""
        s1 = np.ones(100, dtype=np.float32)
        s2 = np.ones(100, dtype=np.float32) * 0.5
        
        timeline = [
            ("speech", s1, None),
            ("speech", s2, None),
        ]
        
        results = list(process_timeline_with_ducking(timeline))
        
        np.testing.assert_array_equal(results[0], s1)
        np.testing.assert_array_equal(results[1], s2)


class TestPresets:
    """Tests for preset ducking envelopes."""
    
    def test_subtle_preset(self):
        """DUCKING_SUBTLE is valid."""
        assert DUCKING_SUBTLE.gain == 0.8
        assert DUCKING_SUBTLE.fade_out_ms == 30
        assert DUCKING_SUBTLE.fade_in_ms == 100
    
    def test_standard_preset(self):
        """DUCKING_STANDARD is valid."""
        assert DUCKING_STANDARD.gain == 0.5
        assert DUCKING_STANDARD.fade_out_ms == 50
        assert DUCKING_STANDARD.fade_in_ms == 150
    
    def test_dramatic_preset(self):
        """DUCKING_DRAMATIC is valid."""
        assert DUCKING_DRAMATIC.gain == 0.3
        assert DUCKING_DRAMATIC.fade_out_ms == 75
        assert DUCKING_DRAMATIC.fade_in_ms == 250
    
    def test_podcast_preset(self):
        """DUCKING_PODCAST is valid."""
        assert DUCKING_PODCAST.gain == 0.6
        assert DUCKING_PODCAST.fade_out_ms == 40
        assert DUCKING_PODCAST.fade_in_ms == 200


class TestDuckingInvariants:
    """Tests verifying ducking preserves timeline invariants."""
    
    def test_duration_unchanged(self):
        """Ducking doesn't change timeline duration."""
        event_pcm = np.ones(100, dtype=np.float32)
        speech_pcm = np.ones(500, dtype=np.float32)
        
        timeline = [
            ("event", event_pcm, DuckingEnvelope(gain=0.5)),
            ("speech", speech_pcm, None),
        ]
        
        results = list(process_timeline_with_ducking(timeline))
        
        # Same lengths
        assert len(results[0]) == len(event_pcm)
        assert len(results[1]) == len(speech_pcm)
    
    def test_no_new_audio_items(self):
        """Ducking doesn't add or remove items."""
        timeline = [
            ("event", np.ones(10, dtype=np.float32), DuckingEnvelope()),
            ("speech", np.ones(20, dtype=np.float32), None),
            ("event", np.ones(15, dtype=np.float32), None),
            ("speech", np.ones(25, dtype=np.float32), None),
        ]
        
        results = list(process_timeline_with_ducking(timeline))
        
        assert len(results) == 4
    
    def test_deterministic(self):
        """Same input produces same output."""
        event_pcm = np.random.randn(100).astype(np.float32)
        speech_pcm = np.random.randn(500).astype(np.float32)
        
        timeline = [
            ("event", event_pcm.copy(), DuckingEnvelope(gain=0.5, fade_in_ms=50)),
            ("speech", speech_pcm.copy(), None),
        ]
        
        results1 = list(process_timeline_with_ducking(timeline))
        
        timeline2 = [
            ("event", event_pcm.copy(), DuckingEnvelope(gain=0.5, fade_in_ms=50)),
            ("speech", speech_pcm.copy(), None),
        ]
        
        results2 = list(process_timeline_with_ducking(timeline2))
        
        np.testing.assert_array_almost_equal(results1[0], results2[0])
        np.testing.assert_array_almost_equal(results1[1], results2[1])
