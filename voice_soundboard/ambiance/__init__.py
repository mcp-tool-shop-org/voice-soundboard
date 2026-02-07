"""
Voice Soundboard v2.4 - Ambiance Module

Background audio and atmospheric effects.

Components:
    AmbianceGenerator  - Generate ambient backgrounds
    AmbiancePreset     - Preset ambiance configurations
    AmbianceLayer      - Individual ambiance layer

Usage:
    from voice_soundboard.ambiance import AmbianceGenerator

    ambiance = AmbianceGenerator()
    rain = ambiance.generate("rain", duration=60.0)
"""

from voice_soundboard.ambiance.generator import (
    AmbianceGenerator,
    AmbianceConfig,
    AmbiancePreset,
)

from voice_soundboard.ambiance.presets import (
    PRESET_LIBRARY,
    get_preset,
    list_presets,
)

__all__ = [
    # Generator
    "AmbianceGenerator",
    "AmbianceConfig",
    "AmbiancePreset",
    # Presets
    "PRESET_LIBRARY",
    "get_preset",
    "list_presets",
]
