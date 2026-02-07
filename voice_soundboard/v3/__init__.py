"""
Voice Soundboard v3 - Audio Power.

v3 introduces multi-track audio, DSP pipelines, and spatial audio primitives.
The AudioGraph extends ControlGraph to support complex audio workflows.

v3.1 adds operational hardening:
- graph.validate() with actionable errors
- graph.diff() for graph comparison
- graph.visualize() for introspection
- DSP presets and profiles
- Plugin interface

v3.2 adds spatial audio:
- Listener-centric spatialization
- Binaural HRTF rendering
- Explicit spatial → stereo downmix
- Movement/automation system
- Spatial safety invariants
"""

from voice_soundboard.v3.audio_graph import (
    AudioGraph,
    AudioTrack,
    EffectNode,
    TrackType,
)
from voice_soundboard.v3.validation import (
    ValidationError,
    ValidationSeverity,
    ValidationResult,
)
from voice_soundboard.v3.presets import (
    Preset,
    PresetLibrary,
    VoiceProfile,
)
from voice_soundboard.v3.plugins import (
    AudioPlugin,
    PluginContext,
    PluginCategory,
)
from voice_soundboard.v3.spatial import (
    # Coordinates
    Position3D,
    Orientation3D,
    # Nodes
    SpatialNode,
    SpatialNodeType,
    ListenerNode,
    SpatialDownmixNode,
    # HRTF
    HRTFProfile,
    HRTFParameters,
    HRTFEngine,
    # Movement
    InterpolationMode,
    MovementKeyframe,
    MovementPath,
    # Graph
    SpatialGraph,
    SpatialGraphValidation,
    create_spatial_scene,
    # Safety
    SpatialSafetyLimits,
    validate_spatial_safety,
)

__all__ = [
    # AudioGraph
    "AudioGraph",
    "AudioTrack",
    "EffectNode",
    "TrackType",
    # Validation
    "ValidationError",
    "ValidationSeverity",
    "ValidationResult",
    # Presets
    "Preset",
    "PresetLibrary",
    "VoiceProfile",
    # Plugins
    "AudioPlugin",
    "PluginContext",
    "PluginCategory",
    # Spatial (v3.2)
    "Position3D",
    "Orientation3D",
    "SpatialNode",
    "SpatialNodeType",
    "ListenerNode",
    "SpatialDownmixNode",
    "HRTFProfile",
    "HRTFParameters",
    "HRTFEngine",
    "InterpolationMode",
    "MovementKeyframe",
    "MovementPath",
    "SpatialGraph",
    "SpatialGraphValidation",
    "create_spatial_scene",
    "SpatialSafetyLimits",
    "validate_spatial_safety",
]

__version__ = "3.2.0-alpha"
