"""
Audio Formats Module for Voice Soundboard v2.3.

Provides audio format handling and conversion:
- Sample rate conversion
- Loudness normalization (LUFS)
- Format negotiation and conversion
- Multi-format output support

Example:
    from voice_soundboard.formats import convert_sample_rate, normalize_loudness
    
    audio_48k = convert_sample_rate(audio, 22050, 48000)
    normalized = normalize_loudness(audio, target_lufs=-16.0)
"""

from voice_soundboard.formats.sample_rate import (
    convert_sample_rate,
    SampleRateConverter,
    ResamplingQuality,
)
from voice_soundboard.formats.loudness import (
    normalize_loudness,
    measure_loudness,
    LoudnessNormalizer,
    LoudnessStats,
)
from voice_soundboard.formats.converter import (
    AudioFormat,
    FormatConverter,
    convert_format,
    detect_format,
)
from voice_soundboard.formats.negotiation import (
    FormatCapabilities,
    FormatNegotiator,
    negotiate_format,
)

__all__ = [
    # Sample Rate
    "convert_sample_rate",
    "SampleRateConverter",
    "ResamplingQuality",
    # Loudness
    "normalize_loudness",
    "measure_loudness",
    "LoudnessNormalizer",
    "LoudnessStats",
    # Format Conversion
    "AudioFormat",
    "FormatConverter",
    "convert_format",
    "detect_format",
    # Negotiation
    "FormatCapabilities",
    "FormatNegotiator",
    "negotiate_format",
]
