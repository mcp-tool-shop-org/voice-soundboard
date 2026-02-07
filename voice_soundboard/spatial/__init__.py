"""
Voice Soundboard v2.4 - Spatial Module

3D spatial audio positioning.

Components:
    SpatialPosition  - 3D position coordinates
    SpatialMixer     - Mix audio with spatial positioning
    SpatialScene     - 3D audio scene

Usage:
    from voice_soundboard.spatial import SpatialMixer, SpatialPosition

    mixer = SpatialMixer()
    positioned = mixer.position(
        audio=pcm,
        position=SpatialPosition(x=1.0, y=0.0, z=0.0),  # Right
    )
"""

from voice_soundboard.spatial.position import (
    SpatialPosition,
    ListenerPosition,
    Coordinates,
)

from voice_soundboard.spatial.mixer import (
    SpatialMixer,
    SpatialConfig,
    SpatialSource,
)

from voice_soundboard.spatial.scene import (
    SpatialScene,
    SpatialAudioLayer,
)

__all__ = [
    # Position
    "SpatialPosition",
    "ListenerPosition",
    "Coordinates",
    # Mixer
    "SpatialMixer",
    "SpatialConfig",
    "SpatialSource",
    # Scene
    "SpatialScene",
    "SpatialAudioLayer",
]
