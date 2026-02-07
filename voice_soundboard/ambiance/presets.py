"""
Ambiance Presets - Pre-configured ambiance settings.

Features:
    - Common environment presets
    - Easy preset lookup
    - Custom preset creation
"""

from __future__ import annotations

from voice_soundboard.ambiance.generator import AmbiancePreset, NoiseType


PRESET_LIBRARY: dict[str, AmbiancePreset] = {
    # Nature
    "rain": AmbiancePreset(
        name="rain",
        description="Light rain ambiance",
        noise_type=NoiseType.PINK,
        noise_volume=0.3,
        base_volume=0.2,
        layers=[
            {"type": "noise", "noise_type": "brown", "volume": 0.1},
        ],
    ),
    
    "heavy_rain": AmbiancePreset(
        name="heavy_rain",
        description="Heavy rain with thunder",
        noise_type=NoiseType.PINK,
        noise_volume=0.4,
        base_volume=0.3,
        layers=[
            {"type": "noise", "noise_type": "brown", "volume": 0.15},
            {"type": "pulse", "rate": 0.02, "volume": 0.3},  # Thunder
        ],
    ),
    
    "ocean": AmbiancePreset(
        name="ocean",
        description="Ocean waves",
        noise_type=NoiseType.BROWN,
        noise_volume=0.3,
        base_volume=0.25,
        modulation_rate=0.05,
        modulation_depth=0.3,
    ),
    
    "forest": AmbiancePreset(
        name="forest",
        description="Forest with birds",
        noise_type=NoiseType.PINK,
        noise_volume=0.1,
        base_volume=0.15,
        layers=[
            {"type": "pulse", "rate": 0.3, "volume": 0.15},  # Bird chirps
        ],
    ),
    
    "wind": AmbiancePreset(
        name="wind",
        description="Gentle wind",
        noise_type=NoiseType.BROWN,
        noise_volume=0.25,
        base_volume=0.2,
        modulation_rate=0.1,
        modulation_depth=0.4,
    ),
    
    # Indoor
    "cafe": AmbiancePreset(
        name="cafe",
        description="Coffee shop ambiance",
        noise_type=NoiseType.PINK,
        noise_volume=0.15,
        base_volume=0.2,
        layers=[
            {"type": "pulse", "rate": 0.5, "volume": 0.05},  # Chatter
        ],
    ),
    
    "office": AmbiancePreset(
        name="office",
        description="Office environment",
        noise_type=NoiseType.WHITE,
        noise_volume=0.08,
        base_volume=0.12,
        layers=[
            {"type": "tone", "frequency": 60, "volume": 0.02},  # HVAC hum
        ],
    ),
    
    "library": AmbiancePreset(
        name="library",
        description="Quiet library",
        noise_type=NoiseType.PINK,
        noise_volume=0.05,
        base_volume=0.08,
    ),
    
    "fireplace": AmbiancePreset(
        name="fireplace",
        description="Crackling fire",
        noise_type=NoiseType.PINK,
        noise_volume=0.15,
        base_volume=0.2,
        layers=[
            {"type": "pulse", "rate": 2.0, "volume": 0.15},  # Crackles
        ],
    ),
    
    # Urban
    "city": AmbiancePreset(
        name="city",
        description="City street ambiance",
        noise_type=NoiseType.PINK,
        noise_volume=0.2,
        base_volume=0.25,
        layers=[
            {"type": "pulse", "rate": 0.1, "volume": 0.1},  # Traffic
        ],
    ),
    
    "subway": AmbiancePreset(
        name="subway",
        description="Underground station",
        noise_type=NoiseType.BROWN,
        noise_volume=0.25,
        base_volume=0.3,
        layers=[
            {"type": "tone", "frequency": 50, "volume": 0.05},  # Rumble
        ],
    ),
    
    # Tech
    "server_room": AmbiancePreset(
        name="server_room",
        description="Data center fans",
        noise_type=NoiseType.PINK,
        noise_volume=0.25,
        base_volume=0.25,
        layers=[
            {"type": "tone", "frequency": 120, "volume": 0.03},  # Fan harmonics
        ],
    ),
    
    "spaceship": AmbiancePreset(
        name="spaceship",
        description="Spaceship interior",
        noise_type=NoiseType.BROWN,
        noise_volume=0.15,
        base_volume=0.2,
        layers=[
            {"type": "tone", "frequency": 80, "volume": 0.04},  # Engine
            {"type": "pulse", "rate": 0.5, "volume": 0.02},  # Beeps
        ],
    ),
    
    # Atmosphere
    "meditation": AmbiancePreset(
        name="meditation",
        description="Calming meditation background",
        noise_type=NoiseType.PINK,
        noise_volume=0.1,
        base_volume=0.1,
        modulation_rate=0.02,
        modulation_depth=0.2,
    ),
    
    "white_noise": AmbiancePreset(
        name="white_noise",
        description="Pure white noise",
        noise_type=NoiseType.WHITE,
        noise_volume=0.5,
        base_volume=0.3,
    ),
    
    "pink_noise": AmbiancePreset(
        name="pink_noise",
        description="Pure pink noise",
        noise_type=NoiseType.PINK,
        noise_volume=0.5,
        base_volume=0.3,
    ),
    
    "brown_noise": AmbiancePreset(
        name="brown_noise",
        description="Pure brown noise",
        noise_type=NoiseType.BROWN,
        noise_volume=0.5,
        base_volume=0.3,
    ),
    
    # Silence
    "silence": AmbiancePreset(
        name="silence",
        description="Digital silence",
        noise_type=NoiseType.PINK,
        noise_volume=0.0,
        base_volume=0.0,
    ),
}


def get_preset(name: str) -> AmbiancePreset:
    """
    Get an ambiance preset by name.
    
    Args:
        name: Preset name
        
    Returns:
        AmbiancePreset (copy to allow modification)
        
    Raises:
        KeyError: If preset not found
    """
    if name not in PRESET_LIBRARY:
        available = ", ".join(PRESET_LIBRARY.keys())
        raise KeyError(f"Unknown preset '{name}'. Available: {available}")
    
    preset = PRESET_LIBRARY[name]
    
    # Return a copy to allow modification
    return AmbiancePreset(
        name=preset.name,
        description=preset.description,
        noise_type=preset.noise_type,
        noise_volume=preset.noise_volume,
        layers=preset.layers[:],
        base_volume=preset.base_volume,
        modulation_rate=preset.modulation_rate,
        modulation_depth=preset.modulation_depth,
    )


def list_presets() -> list[dict[str, str]]:
    """
    List all available presets.
    
    Returns:
        List of preset info dicts
    """
    return [
        {"name": name, "description": preset.description}
        for name, preset in PRESET_LIBRARY.items()
    ]


def create_preset(
    name: str,
    noise_type: str = "pink",
    noise_volume: float = 0.2,
    base_volume: float = 0.2,
    description: str = "",
) -> AmbiancePreset:
    """
    Create a custom preset.
    
    Args:
        name: Preset name
        noise_type: Type of base noise
        noise_volume: Volume of base noise
        base_volume: Overall volume
        description: Preset description
        
    Returns:
        New AmbiancePreset
    """
    return AmbiancePreset(
        name=name,
        description=description,
        noise_type=NoiseType(noise_type),
        noise_volume=noise_volume,
        base_volume=base_volume,
    )
