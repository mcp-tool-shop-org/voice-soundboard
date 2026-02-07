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
]

__version__ = "3.1.0-alpha"
