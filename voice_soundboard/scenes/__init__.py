"""
Voice Soundboard v2.4 - Scenes Module

Advanced audio scene composition.

Components:
    Scene          - Multi-layer audio scene
    AudioLayer     - Audio layer with timing
    SceneBuilder   - Fluent scene construction

Usage:
    from voice_soundboard.scenes import Scene, AudioLayer

    scene = Scene(
        speech=AudioLayer(pcm),
        background=AudioLayer(music, volume=0.2),
    )
"""

from voice_soundboard.scenes.scene import (
    Scene,
    SceneConfig,
    AudioLayer,
    LayerType,
)

from voice_soundboard.scenes.builder import (
    SceneBuilder,
    TransitionType,
)

from voice_soundboard.scenes.mixer import (
    SceneMixer,
    MixConfig,
    MixResult,
)

__all__ = [
    # Scene
    "Scene",
    "SceneConfig",
    "AudioLayer",
    "LayerType",
    # Builder
    "SceneBuilder",
    "TransitionType",
    # Mixer
    "SceneMixer",
    "MixConfig",
    "MixResult",
]
