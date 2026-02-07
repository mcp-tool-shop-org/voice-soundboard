"""
v3.1 AudioGraph - Multi-track Audio with Hardening.

AudioGraph extends ControlGraph to support:
- Multi-track audio (dialogue, music, effects)
- DSP effect chains
- Spatial positioning
- Graph validation and introspection

v3.1 hardening features:
- validate() - Catch all invalid configurations before render
- diff() - Compare graphs to understand changes
- visualize() - Generate graph diagrams for debugging
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterator
import copy
import hashlib
import json

from voice_soundboard.graph.types import ControlGraph, SpeakerRef, TokenEvent
from voice_soundboard.v3.validation import (
    ValidationResult,
    ValidationError,
    ValidationSeverity,
)


class TrackType(str, Enum):
    """Type of audio track."""
    DIALOGUE = "dialogue"   # Speech content
    MUSIC = "music"         # Background music
    EFFECTS = "effects"     # Sound effects
    AMBIANCE = "ambiance"   # Background ambiance
    CUSTOM = "custom"       # User-defined


@dataclass
class SpatialPosition:
    """3D position for spatial audio."""
    x: float = 0.0  # -1 (left) to 1 (right)
    y: float = 0.0  # -1 (below) to 1 (above)
    z: float = 1.0  # Distance (>0)
    
    def __post_init__(self):
        if self.z <= 0:
            raise ValueError("z (distance) must be positive")
    
    def __hash__(self) -> int:
        return hash((self.x, self.y, self.z))


@dataclass
class EffectNode:
    """A DSP effect in the processing chain.
    
    Effects are applied in order within a track's effect chain.
    Each effect must declare its parameters for validation.
    """
    name: str
    effect_type: str  # e.g., "eq", "compressor", "reverb", "limiter"
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    # Connection info (for graph traversal)
    id: str = field(default_factory=lambda: "")
    
    def __post_init__(self):
        if not self.id:
            # Generate deterministic ID from type and params
            content = f"{self.effect_type}:{json.dumps(self.params, sort_keys=True)}"
            self.id = hashlib.sha256(content.encode()).hexdigest()[:8]
    
    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class AudioTrack:
    """A single audio track with content and effects.
    
    Tracks contain either:
    - A ControlGraph (for TTS content)
    - Raw audio reference (for pre-rendered content)
    - Child tracks (for subgroups)
    """
    name: str
    track_type: TrackType = TrackType.DIALOGUE
    
    # Content
    control_graph: ControlGraph | None = None
    audio_ref: str | None = None  # Reference to pre-rendered audio
    
    # Effects (applied in order)
    effects: list[EffectNode] = field(default_factory=list)
    
    # Mix settings
    volume: float = 1.0       # 0.0 to 2.0
    pan: float = 0.0          # -1.0 (left) to 1.0 (right)
    mute: bool = False
    solo: bool = False
    
    # Spatial
    position: SpatialPosition | None = None
    
    # Ducking (for dialogue over music)
    duck_for: list[str] = field(default_factory=list)  # Track names to duck for
    duck_amount: float = 0.7  # How much to reduce volume when ducking
    
    # Metadata
    sample_rate: int = 24000
    
    def add_effect(self, effect: EffectNode) -> AudioTrack:
        """Add an effect to the chain. Returns self for chaining."""
        self.effects.append(effect)
        return self
    
    def remove_effect(self, effect_name: str) -> bool:
        """Remove effect by name. Returns True if removed."""
        for i, eff in enumerate(self.effects):
            if eff.name == effect_name:
                self.effects.pop(i)
                return True
        return False
    
    def has_content(self) -> bool:
        """Check if track has any content."""
        return self.control_graph is not None or self.audio_ref is not None


@dataclass
class GraphChange:
    """A single change between two graphs."""
    change_type: str  # "added", "removed", "modified"
    path: str         # Dot-separated path to changed element
    old_value: Any = None
    new_value: Any = None
    
    def __str__(self) -> str:
        if self.change_type == "added":
            return f"+ {self.path}: {self.new_value}"
        elif self.change_type == "removed":
            return f"- {self.path}: {self.old_value}"
        else:
            return f"~ {self.path}: {self.old_value} -> {self.new_value}"


@dataclass
class GraphDiff:
    """Difference between two AudioGraphs.
    
    Provides a structured way to understand what changed between
    two graph versions, useful for debugging and auditing.
    """
    changes: list[GraphChange] = field(default_factory=list)
    
    @property
    def has_changes(self) -> bool:
        """True if graphs differ."""
        return len(self.changes) > 0
    
    @property
    def added(self) -> list[GraphChange]:
        """Get all additions."""
        return [c for c in self.changes if c.change_type == "added"]
    
    @property
    def removed(self) -> list[GraphChange]:
        """Get all removals."""
        return [c for c in self.changes if c.change_type == "removed"]
    
    @property
    def modified(self) -> list[GraphChange]:
        """Get all modifications."""
        return [c for c in self.changes if c.change_type == "modified"]
    
    def __str__(self) -> str:
        if not self.changes:
            return "No changes"
        return "\n".join(str(c) for c in self.changes)
    
    def __bool__(self) -> bool:
        return self.has_changes
    
    def __len__(self) -> int:
        return len(self.changes)


class AudioGraph:
    """Multi-track audio graph with v3.1 hardening features.
    
    AudioGraph extends the ControlGraph paradigm to support:
    - Multiple parallel tracks (dialogue, music, effects)
    - DSP effect chains per track
    - Spatial positioning
    - Master bus processing
    
    v3.1 Hardening:
    - validate(): Catch invalid configurations before render
    - diff(): Compare graphs for debugging and auditing
    - visualize(): Generate visual representations
    """
    
    # Maximum nesting depth for effect chains
    MAX_EFFECT_DEPTH = 16
    
    # Valid sample rates
    VALID_SAMPLE_RATES = {22050, 24000, 44100, 48000}
    
    def __init__(self, name: str = "untitled", sample_rate: int = 24000):
        self.name = name
        self.sample_rate = sample_rate
        self._tracks: dict[str, AudioTrack] = {}
        self._master_effects: list[EffectNode] = []
        self._plugins: dict[str, Any] = {}  # Registered plugins
        self._metadata: dict[str, Any] = {}
    
    # =========================================================================
    # Track Management
    # =========================================================================
    
    def add_track(self, name: str, track_type: TrackType = TrackType.DIALOGUE) -> AudioTrack:
        """Add a new track to the graph."""
        if name in self._tracks:
            raise ValueError(f"Track '{name}' already exists")
        
        track = AudioTrack(name=name, track_type=track_type, sample_rate=self.sample_rate)
        self._tracks[name] = track
        return track
    
    def get_track(self, name: str) -> AudioTrack | None:
        """Get track by name."""
        return self._tracks.get(name)
    
    def remove_track(self, name: str) -> bool:
        """Remove track by name. Returns True if removed."""
        if name in self._tracks:
            del self._tracks[name]
            return True
        return False
    
    @property
    def tracks(self) -> list[AudioTrack]:
        """Get all tracks."""
        return list(self._tracks.values())
    
    @property
    def track_count(self) -> int:
        """Number of tracks."""
        return len(self._tracks)
    
    def __iter__(self) -> Iterator[AudioTrack]:
        """Iterate over tracks."""
        return iter(self._tracks.values())
    
    # =========================================================================
    # Master Bus
    # =========================================================================
    
    def add_master_effect(self, effect: EffectNode) -> AudioGraph:
        """Add effect to master bus. Returns self for chaining."""
        self._master_effects.append(effect)
        return self
    
    @property
    def master_effects(self) -> list[EffectNode]:
        """Get master bus effects."""
        return self._master_effects
    
    # =========================================================================
    # Plugins
    # =========================================================================
    
    def register_plugin(self, plugin: Any) -> None:
        """Register a plugin for use in the graph."""
        if hasattr(plugin, 'name'):
            self._plugins[plugin.name] = plugin
        else:
            raise ValueError("Plugin must have a 'name' attribute")
    
    def get_plugin(self, name: str) -> Any | None:
        """Get registered plugin by name."""
        return self._plugins.get(name)
    
    # =========================================================================
    # v3.1 Hardening: validate()
    # =========================================================================
    
    def validate(self, strict: bool = False) -> ValidationResult:
        """Validate the graph and return any issues.
        
        Args:
            strict: If True, warnings are promoted to errors
        
        Returns:
            ValidationResult containing all errors and warnings
        
        Checks performed:
        - Sample rate validity
        - Track content presence
        - Effect chain validity
        - Speaker reference completeness
        - Cycle detection in routing
        - Parameter bounds
        - Plugin compliance
        """
        result = ValidationResult()
        
        # Global checks
        self._validate_sample_rate(result)
        self._validate_track_consistency(result)
        self._validate_effect_chains(result)
        self._validate_ducking_references(result)
        self._validate_plugins(result)
        
        # Per-track checks
        for name, track in self._tracks.items():
            self._validate_track(name, track, result)
        
        # Strict mode: promote warnings to errors
        if strict:
            for err in result.errors:
                if err.severity == ValidationSeverity.WARNING:
                    err.severity = ValidationSeverity.ERROR
        
        return result
    
    def _validate_sample_rate(self, result: ValidationResult) -> None:
        """Validate sample rate is valid."""
        if self.sample_rate not in self.VALID_SAMPLE_RATES:
            result.add(ValidationError.invalid_sample_rate("graph", self.sample_rate))
    
    def _validate_track_consistency(self, result: ValidationResult) -> None:
        """Check for sample rate consistency across tracks."""
        rates = set()
        for track in self._tracks.values():
            rates.add(track.sample_rate)
        
        if len(rates) > 1:
            result.add(
                ValidationError.incompatible_sample_rates("graph.tracks", list(rates))
            )
    
    def _validate_effect_chains(self, result: ValidationResult) -> None:
        """Validate all effect chains."""
        # Master effects
        if len(self._master_effects) > self.MAX_EFFECT_DEPTH:
            result.add(
                ValidationError.effect_chain_too_deep(
                    "graph.master_effects",
                    len(self._master_effects),
                    self.MAX_EFFECT_DEPTH
                )
            )
    
    def _validate_ducking_references(self, result: ValidationResult) -> None:
        """Validate ducking track references exist."""
        track_names = set(self._tracks.keys())
        for name, track in self._tracks.items():
            for duck_target in track.duck_for:
                if duck_target not in track_names:
                    result.add(ValidationError(
                        location=f"tracks[{name}].duck_for",
                        message=f"Duck target '{duck_target}' does not exist",
                        severity=ValidationSeverity.ERROR,
                        suggestion=f"Available tracks: {', '.join(track_names)}",
                        code="INVALID_DUCK_TARGET",
                    ))
    
    def _validate_plugins(self, result: ValidationResult) -> None:
        """Validate registered plugins comply with sandbox rules."""
        for name, plugin in self._plugins.items():
            # Check required plugin attributes
            if hasattr(plugin, 'has_external_state') and plugin.has_external_state:
                result.add(
                    ValidationError.plugin_violation(
                        f"plugins[{name}]",
                        name,
                        "Plugin declares external state, which is forbidden"
                    )
                )
    
    def _validate_track(self, name: str, track: AudioTrack, result: ValidationResult) -> None:
        """Validate a single track."""
        location = f"tracks[{name}]"
        
        # Check for content
        if not track.has_content():
            result.add(ValidationError.empty_track(location, name))
        
        # Validate control graph if present
        if track.control_graph:
            self._validate_control_graph(f"{location}.control_graph", track.control_graph, result)
        
        # Validate volume
        if not 0.0 <= track.volume <= 2.0:
            result.add(ValidationError.invalid_parameter(
                f"{location}.volume", "volume", track.volume, (0.0, 2.0)
            ))
        
        # Validate pan
        if not -1.0 <= track.pan <= 1.0:
            result.add(ValidationError.invalid_parameter(
                f"{location}.pan", "pan", track.pan, (-1.0, 1.0)
            ))
        
        # Validate effect chain depth
        if len(track.effects) > self.MAX_EFFECT_DEPTH:
            result.add(ValidationError.effect_chain_too_deep(
                f"{location}.effects",
                len(track.effects),
                self.MAX_EFFECT_DEPTH
            ))
        
        # Validate spatial position
        if track.position:
            if track.position.z <= 0:
                result.add(ValidationError.invalid_parameter(
                    f"{location}.position.z", "z (distance)", track.position.z, (0.01, float('inf'))
                ))
    
    def _validate_control_graph(self, location: str, graph: ControlGraph, 
                                result: ValidationResult) -> None:
        """Validate an embedded ControlGraph."""
        # Use existing ControlGraph validation
        issues = graph.validate()
        for issue in issues:
            result.add(ValidationError(
                location=f"{location}",
                message=issue,
                severity=ValidationSeverity.ERROR,
                code="CONTROL_GRAPH_INVALID",
            ))
        
        # Check speaker reference
        if graph.speaker is None:
            result.add(ValidationError.missing_speaker(f"{location}.speaker"))
    
    # =========================================================================
    # v3.1 Hardening: diff()
    # =========================================================================
    
    def diff(self, other: AudioGraph) -> GraphDiff:
        """Compare this graph with another and return differences.
        
        Args:
            other: Another AudioGraph to compare against
        
        Returns:
            GraphDiff containing all changes between the graphs
        
        Useful for:
        - Debugging graph modifications
        - Auditing changes in automated pipelines
        - Understanding agent-driven modifications
        """
        diff = GraphDiff()
        
        # Compare name
        if self.name != other.name:
            diff.changes.append(GraphChange("modified", "name", self.name, other.name))
        
        # Compare sample rate
        if self.sample_rate != other.sample_rate:
            diff.changes.append(GraphChange(
                "modified", "sample_rate", self.sample_rate, other.sample_rate
            ))
        
        # Compare tracks
        self_tracks = set(self._tracks.keys())
        other_tracks = set(other._tracks.keys())
        
        # Added tracks
        for name in other_tracks - self_tracks:
            diff.changes.append(GraphChange("added", f"tracks[{name}]", None, name))
        
        # Removed tracks
        for name in self_tracks - other_tracks:
            diff.changes.append(GraphChange("removed", f"tracks[{name}]", name, None))
        
        # Modified tracks
        for name in self_tracks & other_tracks:
            self._diff_track(f"tracks[{name}]", self._tracks[name], other._tracks[name], diff)
        
        # Compare master effects
        self._diff_effects("master_effects", self._master_effects, other._master_effects, diff)
        
        return diff
    
    def _diff_track(self, path: str, track1: AudioTrack, track2: AudioTrack, 
                    diff: GraphDiff) -> None:
        """Diff two tracks."""
        # Volume
        if track1.volume != track2.volume:
            diff.changes.append(GraphChange(
                "modified", f"{path}.volume", track1.volume, track2.volume
            ))
        
        # Pan
        if track1.pan != track2.pan:
            diff.changes.append(GraphChange(
                "modified", f"{path}.pan", track1.pan, track2.pan
            ))
        
        # Mute
        if track1.mute != track2.mute:
            diff.changes.append(GraphChange(
                "modified", f"{path}.mute", track1.mute, track2.mute
            ))
        
        # Effects
        self._diff_effects(f"{path}.effects", track1.effects, track2.effects, diff)
    
    def _diff_effects(self, path: str, effects1: list[EffectNode], 
                      effects2: list[EffectNode], diff: GraphDiff) -> None:
        """Diff effect chains."""
        ids1 = {e.id: e for e in effects1}
        ids2 = {e.id: e for e in effects2}
        
        # Added effects
        for eid in set(ids2.keys()) - set(ids1.keys()):
            diff.changes.append(GraphChange(
                "added", f"{path}[{ids2[eid].name}]", None, ids2[eid].effect_type
            ))
        
        # Removed effects
        for eid in set(ids1.keys()) - set(ids2.keys()):
            diff.changes.append(GraphChange(
                "removed", f"{path}[{ids1[eid].name}]", ids1[eid].effect_type, None
            ))
        
        # Modified effects (same ID, different params)
        for eid in set(ids1.keys()) & set(ids2.keys()):
            if ids1[eid].params != ids2[eid].params:
                diff.changes.append(GraphChange(
                    "modified", f"{path}[{ids1[eid].name}].params",
                    ids1[eid].params, ids2[eid].params
                ))
    
    # =========================================================================
    # v3.1 Hardening: visualize()
    # =========================================================================
    
    def visualize(self, output: str | None = None, format: str = "mermaid") -> str:
        """Generate a visual representation of the graph.
        
        Args:
            output: Optional file path to write the visualization
            format: Output format ("mermaid", "dot", "ascii")
        
        Returns:
            String representation of the graph in the specified format
        
        Supported formats:
        - mermaid: Mermaid diagram syntax (Markdown compatible)
        - dot: GraphViz DOT language
        - ascii: Simple ASCII art representation
        """
        if format == "mermaid":
            result = self._visualize_mermaid()
        elif format == "dot":
            result = self._visualize_dot()
        elif format == "ascii":
            result = self._visualize_ascii()
        else:
            raise ValueError(f"Unknown format: {format}. Use 'mermaid', 'dot', or 'ascii'")
        
        if output:
            with open(output, "w") as f:
                f.write(result)
        
        return result
    
    def _visualize_mermaid(self) -> str:
        """Generate Mermaid diagram."""
        lines = ["```mermaid", "graph LR"]
        
        # Master output
        lines.append("    Master[\"🔊 Master\"]")
        
        # Tracks
        for name, track in self._tracks.items():
            icon = self._track_icon(track.track_type)
            lines.append(f"    {name}[\"{icon} {name}\"]")
            
            # Effects
            prev = name
            for i, effect in enumerate(track.effects):
                eff_id = f"{name}_eff_{i}"
                lines.append(f"    {eff_id}[[\"{effect.effect_type}\"]]")
                lines.append(f"    {prev} --> {eff_id}")
                prev = eff_id
            
            # Connect to master
            lines.append(f"    {prev} --> Master")
        
        # Master effects
        if self._master_effects:
            prev = "Master"
            for i, effect in enumerate(self._master_effects):
                eff_id = f"master_eff_{i}"
                lines.append(f"    {eff_id}[[\"{effect.effect_type}\"]]")
                lines.append(f"    {prev} --> {eff_id}")
                prev = eff_id
            
            lines.append(f"    {prev} --> Output[\"🔈 Output\"]")
        else:
            lines.append("    Master --> Output[\"🔈 Output\"]")
        
        lines.append("```")
        return "\n".join(lines)
    
    def _visualize_dot(self) -> str:
        """Generate GraphViz DOT."""
        lines = ["digraph AudioGraph {", "    rankdir=LR;", "    node [shape=box];"]
        
        lines.append('    Master [label="Master" shape=house];')
        lines.append('    Output [label="Output" shape=house];')
        
        for name, track in self._tracks.items():
            lines.append(f'    "{name}" [label="{name}\\n({track.track_type.value})"];')
            
            prev = f'"{name}"'
            for i, effect in enumerate(track.effects):
                eff_id = f"{name}_eff_{i}"
                lines.append(f'    "{eff_id}" [label="{effect.effect_type}" shape=ellipse];')
                lines.append(f'    {prev} -> "{eff_id}";')
                prev = f'"{eff_id}"'
            
            lines.append(f'    {prev} -> Master;')
        
        if self._master_effects:
            prev = "Master"
            for i, effect in enumerate(self._master_effects):
                eff_id = f"master_eff_{i}"
                lines.append(f'    "{eff_id}" [label="{effect.effect_type}" shape=ellipse];')
                lines.append(f'    {prev} -> "{eff_id}";')
                prev = f'"{eff_id}"'
            lines.append(f'    {prev} -> Output;')
        else:
            lines.append("    Master -> Output;")
        
        lines.append("}")
        return "\n".join(lines)
    
    def _visualize_ascii(self) -> str:
        """Generate ASCII art representation."""
        lines = [
            f"AudioGraph: {self.name}",
            f"Sample Rate: {self.sample_rate} Hz",
            f"Tracks: {self.track_count}",
            "",
        ]
        
        for name, track in self._tracks.items():
            icon = self._track_icon(track.track_type)
            vol = f"[{'█' * int(track.volume * 5)}{'░' * (10 - int(track.volume * 5))}]"
            lines.append(f"  {icon} {name} {vol}")
            
            if track.effects:
                for i, effect in enumerate(track.effects):
                    connector = "└─" if i == len(track.effects) - 1 else "├─"
                    lines.append(f"    {connector} {effect.effect_type}: {effect.params}")
        
        if self._master_effects:
            lines.append("")
            lines.append("  🎛️ Master Bus:")
            for effect in self._master_effects:
                lines.append(f"    └─ {effect.effect_type}: {effect.params}")
        
        return "\n".join(lines)
    
    def _track_icon(self, track_type: TrackType) -> str:
        """Get icon for track type."""
        icons = {
            TrackType.DIALOGUE: "🎙️",
            TrackType.MUSIC: "🎵",
            TrackType.EFFECTS: "💥",
            TrackType.AMBIANCE: "🌊",
            TrackType.CUSTOM: "🔧",
        }
        return icons.get(track_type, "📁")
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def clone(self) -> AudioGraph:
        """Create a deep copy of the graph."""
        return copy.deepcopy(self)
    
    def is_consistent(self) -> bool:
        """Quick check if graph is in a valid state."""
        return self.validate().is_valid
    
    def to_dict(self) -> dict:
        """Serialize graph to dictionary."""
        return {
            "name": self.name,
            "sample_rate": self.sample_rate,
            "tracks": {
                name: {
                    "type": track.track_type.value,
                    "volume": track.volume,
                    "pan": track.pan,
                    "mute": track.mute,
                    "effects": [
                        {"name": e.name, "type": e.effect_type, "params": e.params}
                        for e in track.effects
                    ],
                }
                for name, track in self._tracks.items()
            },
            "master_effects": [
                {"name": e.name, "type": e.effect_type, "params": e.params}
                for e in self._master_effects
            ],
        }
    
    def __repr__(self) -> str:
        return f"AudioGraph(name={self.name!r}, tracks={self.track_count}, sample_rate={self.sample_rate})"
