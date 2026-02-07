"""
Tests for v2.3 formats module.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile

from voice_soundboard.formats import (
    convert_sample_rate,
    SampleRateConverter,
    ResamplingQuality,
    normalize_loudness,
    measure_loudness,
    LoudnessNormalizer,
    LoudnessStats,
    AudioFormat,
    FormatConverter,
    convert_format,
    detect_format,
    FormatCapabilities,
    FormatNegotiator,
    negotiate_format,
)
from voice_soundboard.formats.negotiation import NegotiationStrategy, CAPABILITIES_MINIMAL, CAPABILITIES_FULL


class TestSampleRateConversion:
    """Tests for sample rate conversion."""
    
    def test_convert_no_change(self):
        audio = np.arange(1000, dtype=np.int16)
        result = convert_sample_rate(audio, 22050, 22050)
        
        assert len(result) == len(audio)
        np.testing.assert_array_equal(result, audio)
        
    def test_upsample(self):
        audio = np.arange(100, dtype=np.int16)
        result = convert_sample_rate(audio, 22050, 44100)
        
        # Should be ~2x length
        assert len(result) == pytest.approx(200, rel=0.1)
        
    def test_downsample(self):
        audio = np.arange(1000, dtype=np.int16)
        result = convert_sample_rate(audio, 44100, 22050)
        
        # Should be ~0.5x length
        assert len(result) == pytest.approx(500, rel=0.1)
        
    def test_quality_levels(self):
        audio = np.sin(np.linspace(0, 10, 1000)) * 32767
        audio = audio.astype(np.int16)
        
        # All quality levels should produce output
        for quality in ResamplingQuality:
            result = convert_sample_rate(audio, 22050, 44100, quality=quality)
            assert len(result) > 0
            
    def test_empty_audio(self):
        result = convert_sample_rate(np.array([], dtype=np.int16), 22050, 44100)
        assert len(result) == 0


class TestLoudnessNormalization:
    """Tests for loudness normalization."""
    
    def test_measure_loudness_basic(self):
        # Generate known signal
        sample_rate = 22050
        audio = np.sin(np.linspace(0, 100, sample_rate)) * 0.5
        audio = (audio * 32767).astype(np.int16)
        
        stats = measure_loudness(audio, sample_rate)
        
        assert isinstance(stats, LoudnessStats)
        assert stats.integrated < 0  # Should be negative LUFS
        assert stats.peak < 0  # Should be below 0 dBFS
        
    def test_measure_loudness_empty(self):
        stats = measure_loudness(np.array([], dtype=np.int16))
        
        assert stats.integrated == -70.0
        assert stats.peak == -70.0
        
    def test_normalize_loudness(self):
        sample_rate = 22050
        audio = np.sin(np.linspace(0, 100, sample_rate)) * 0.1  # Quiet signal
        audio = (audio * 32767).astype(np.int16)
        
        # Normalize to -16 LUFS
        normalized = normalize_loudness(audio, target_lufs=-16.0, sample_rate=sample_rate)
        
        # Normalized should be louder
        assert np.max(np.abs(normalized)) >= np.max(np.abs(audio))
        
    def test_loudness_normalizer_peak_limiting(self):
        normalizer = LoudnessNormalizer(target_lufs=-10.0, true_peak_limit=-1.0)
        
        sample_rate = 22050
        audio = np.sin(np.linspace(0, 100, sample_rate)) * 0.5
        audio = (audio * 32767).astype(np.int16)
        
        normalized = normalizer.normalize(audio, sample_rate)
        
        # Peak should be limited
        normalized_float = normalized.astype(np.float64) / 32768.0
        peak_db = 20 * np.log10(np.max(np.abs(normalized_float)) + 1e-10)
        assert peak_db <= -0.9  # Allow small margin


class TestFormatConversion:
    """Tests for format conversion."""
    
    def test_detect_wav_format(self):
        # WAV header
        wav_header = b"RIFF\x00\x00\x00\x00WAVEfmt "
        
        format = detect_format(wav_header)
        assert format == AudioFormat.WAV
        
    def test_detect_mp3_format(self):
        # ID3 tag
        mp3_header = b"ID3\x04\x00\x00"
        
        format = detect_format(mp3_header)
        assert format == AudioFormat.MP3
        
    def test_convert_to_wav(self):
        audio = np.sin(np.linspace(0, 10, 1000)) * 32767
        audio = audio.astype(np.int16)
        
        wav_bytes = convert_format(audio, AudioFormat.WAV, sample_rate=22050)
        
        # Should start with RIFF
        assert wav_bytes[:4] == b"RIFF"
        assert b"WAVE" in wav_bytes[:12]
        
    def test_convert_to_pcm(self):
        audio = np.array([100, 200, 300, 400], dtype=np.int16)
        
        pcm_bytes = convert_format(audio, AudioFormat.PCM)
        
        # Should be raw bytes
        assert len(pcm_bytes) == len(audio) * 2  # 2 bytes per int16
        
    def test_wav_roundtrip(self):
        converter = FormatConverter()
        
        original = np.array([1000, 2000, 3000, -1000, -2000], dtype=np.int16)
        
        # Encode to WAV
        wav_bytes = converter.convert(original, AudioFormat.PCM, AudioFormat.WAV, 22050)
        
        # Decode back
        decoded, metadata = converter.decode(wav_bytes)
        
        np.testing.assert_array_equal(decoded, original)
        assert metadata.sample_rate == 22050


class TestFormatNegotiation:
    """Tests for format negotiation."""
    
    def test_negotiate_common_format(self):
        producer = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.MP3},
            sample_rates={22050, 44100},
        )
        consumer = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.OGG},
            sample_rates={44100, 48000},
        )
        
        result = negotiate_format(producer, consumer)
        
        assert result is not None
        assert result.format == AudioFormat.WAV  # Common format
        assert result.sample_rate == 44100  # Common rate
        
    def test_negotiate_no_common_rate(self):
        producer = FormatCapabilities(
            supported_formats={AudioFormat.WAV},
            sample_rates={22050},
        )
        consumer = FormatCapabilities(
            supported_formats={AudioFormat.WAV},
            sample_rates={48000},
        )
        
        result = negotiate_format(producer, consumer)
        
        assert result is not None
        assert result.conversion_needed
        assert "Sample rate conversion" in result.notes[0]
        
    def test_negotiate_prefer_quality(self):
        producer = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.FLAC},
            sample_rates={44100, 96000},
        )
        consumer = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.FLAC},
            sample_rates={44100, 96000},
        )
        
        result = negotiate_format(
            producer,
            consumer,
            strategy=NegotiationStrategy.PREFER_QUALITY,
        )
        
        assert result.format == AudioFormat.FLAC  # Higher quality
        assert result.sample_rate == 96000  # Higher rate
        
    def test_negotiate_prefer_speed(self):
        producer = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.PCM},
            sample_rates={22050, 48000},
        )
        consumer = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.PCM},
            sample_rates={22050, 48000},
        )
        
        result = negotiate_format(
            producer,
            consumer,
            strategy=NegotiationStrategy.PREFER_SPEED,
        )
        
        assert result.format == AudioFormat.PCM  # Fastest
        assert result.sample_rate == 22050  # Lower rate = faster
        
    def test_capabilities_presets(self):
        # Minimal should be subset of full
        for fmt in CAPABILITIES_MINIMAL.supported_formats:
            assert fmt in CAPABILITIES_FULL.supported_formats
            
        for rate in CAPABILITIES_MINIMAL.sample_rates:
            assert rate in CAPABILITIES_FULL.sample_rates


class TestFormatCapabilities:
    """Tests for FormatCapabilities."""
    
    def test_supports(self):
        caps = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.MP3},
        )
        
        assert caps.supports(AudioFormat.WAV)
        assert caps.supports(AudioFormat.MP3)
        assert not caps.supports(AudioFormat.FLAC)
        
    def test_common_with(self):
        caps1 = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.MP3, AudioFormat.OGG},
            sample_rates={22050, 44100},
        )
        caps2 = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.FLAC, AudioFormat.OGG},
            sample_rates={44100, 48000},
        )
        
        common_formats = caps1.common_formats(caps2)
        common_rates = caps1.common_sample_rates(caps2)
        
        assert common_formats == {AudioFormat.WAV, AudioFormat.OGG}
        assert common_rates == {44100}
        
    def test_to_dict_from_dict(self):
        caps = FormatCapabilities(
            supported_formats={AudioFormat.WAV, AudioFormat.MP3},
            sample_rates={22050, 44100},
            preferred_format=AudioFormat.WAV,
        )
        
        data = caps.to_dict()
        restored = FormatCapabilities.from_dict(data)
        
        assert restored.supported_formats == caps.supported_formats
        assert restored.sample_rates == caps.sample_rates
        assert restored.preferred_format == caps.preferred_format
