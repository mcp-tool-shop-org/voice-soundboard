"""
v3.1 DSP Presets - Reusable Effect Configurations.

Provides named DSP chains, parameter snapshots, and profiles for:
- Consistent audio processing across projects
- No copy-paste pipelines
- Version-controlled audio settings
- Per-voice and per-scene defaults
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import json
import yaml


@dataclass
class EffectConfig:
    """Configuration for a single effect in a preset."""
    effect_type: str  # e.g., "eq", "compressor", "reverb"
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    def to_effect_node(self, name: str | None = None):
        """Convert to EffectNode for use in AudioGraph."""
        from voice_soundboard.v3.audio_graph import EffectNode
        return EffectNode(
            name=name or self.effect_type,
            effect_type=self.effect_type,
            params=self.params,
            enabled=self.enabled,
        )


@dataclass
class Preset:
    """A named, reusable DSP configuration.
    
    Presets package effect chains for common use cases like:
    - Broadcast audio (podcast, radio)
    - Theatrical dialogue
    - Narration
    - Background music ducking
    
    Example:
        broadcast_clean = Preset(
            name="broadcast_clean",
            effects=[
                EffectConfig("eq", {"low_cut_hz": 80, "high_shelf_db": -2}),
                EffectConfig("compressor", {"threshold_db": -18, "ratio": 3}),
                EffectConfig("limiter", {"ceiling_db": -1}),
            ],
            metadata={"use_case": "podcast", "author": "audio_team"},
        )
    """
    name: str
    effects: list[EffectConfig] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Optional description
    description: str = ""
    
    # Version for preset evolution
    version: str = "1.0.0"
    
    def to_effect_nodes(self) -> list:
        """Convert all effects to EffectNodes."""
        return [
            effect.to_effect_node(f"{self.name}_{i}")
            for i, effect in enumerate(self.effects)
        ]
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "effects": [
                {
                    "type": e.effect_type,
                    "params": e.params,
                    "enabled": e.enabled,
                }
                for e in self.effects
            ],
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Preset:
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            effects=[
                EffectConfig(
                    effect_type=e["type"],
                    params=e.get("params", {}),
                    enabled=e.get("enabled", True),
                )
                for e in data.get("effects", [])
            ],
            metadata=data.get("metadata", {}),
        )


@dataclass
class VoiceProfile:
    """Voice-specific audio settings.
    
    Associates a preset with a voice ID for automatic application.
    
    Example:
        female_warm = VoiceProfile(
            voice_id="af_bella",
            preset_name="warm_female",
            overrides={"eq": {"bass_boost_db": 2}},
        )
    """
    voice_id: str
    preset_name: str
    
    # Override specific effect parameters
    overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    # Voice-specific gain adjustment
    gain_db: float = 0.0
    
    def apply_overrides(self, preset: Preset) -> Preset:
        """Apply voice-specific overrides to a preset."""
        # Deep copy the preset effects
        new_effects = []
        for effect in preset.effects:
            params = effect.params.copy()
            
            # Apply overrides if they exist for this effect type
            if effect.effect_type in self.overrides:
                params.update(self.overrides[effect.effect_type])
            
            new_effects.append(EffectConfig(
                effect_type=effect.effect_type,
                params=params,
                enabled=effect.enabled,
            ))
        
        return Preset(
            name=f"{preset.name}_for_{self.voice_id}",
            effects=new_effects,
            metadata={**preset.metadata, "voice_id": self.voice_id},
            description=f"{preset.description} (customized for {self.voice_id})",
            version=preset.version,
        )


@dataclass
class SceneProfile:
    """Scene-level mixing defaults.
    
    Associates presets with track types for automatic application.
    
    Example:
        podcast_scene = SceneProfile(
            name="podcast",
            track_defaults={
                TrackType.DIALOGUE: "broadcast_clean",
                TrackType.MUSIC: "background_duck",
                TrackType.EFFECTS: "subtle_sfx",
            },
        )
    """
    name: str
    track_defaults: dict[str, str] = field(default_factory=dict)  # TrackType -> preset_name
    
    # Scene-level master bus preset
    master_preset: str | None = None
    
    # Default ducking configuration
    duck_dialogue_over_music: bool = True
    duck_amount: float = 0.7
    
    # Default crossfade duration for turn transitions
    crossfade_ms: int = 100


class PresetLibrary:
    """Central registry for DSP presets.
    
    Manages presets, voice profiles, and scene profiles with:
    - File-based persistence (YAML/JSON)
    - Built-in presets for common use cases
    - Validation of preset integrity
    
    Example:
        library = PresetLibrary()
        library.register(broadcast_clean)
        library.register_from_file("presets/custom.yaml")
        
        preset = library.get("broadcast_clean")
        engine.apply_preset(track, preset)
    """
    
    def __init__(self):
        self._presets: dict[str, Preset] = {}
        self._voice_profiles: dict[str, VoiceProfile] = {}
        self._scene_profiles: dict[str, SceneProfile] = {}
        
        # Load built-in presets
        self._load_builtins()
    
    # =========================================================================
    # Preset Management
    # =========================================================================
    
    def register(self, preset: Preset) -> None:
        """Register a preset."""
        self._presets[preset.name] = preset
    
    def get(self, name: str) -> Preset | None:
        """Get preset by name."""
        return self._presets.get(name)
    
    def list_presets(self) -> list[str]:
        """List all registered preset names."""
        return list(self._presets.keys())
    
    def remove(self, name: str) -> bool:
        """Remove preset by name. Returns True if removed."""
        if name in self._presets:
            del self._presets[name]
            return True
        return False
    
    # =========================================================================
    # Voice Profile Management
    # =========================================================================
    
    def register_voice_profile(self, profile: VoiceProfile) -> None:
        """Register a voice profile."""
        self._voice_profiles[profile.voice_id] = profile
    
    def get_voice_profile(self, voice_id: str) -> VoiceProfile | None:
        """Get profile for a voice."""
        return self._voice_profiles.get(voice_id)
    
    def get_preset_for_voice(self, voice_id: str) -> Preset | None:
        """Get the effective preset for a voice (with overrides applied)."""
        profile = self._voice_profiles.get(voice_id)
        if not profile:
            return None
        
        preset = self._presets.get(profile.preset_name)
        if not preset:
            return None
        
        return profile.apply_overrides(preset)
    
    # =========================================================================
    # Scene Profile Management
    # =========================================================================
    
    def register_scene_profile(self, profile: SceneProfile) -> None:
        """Register a scene profile."""
        self._scene_profiles[profile.name] = profile
    
    def get_scene_profile(self, name: str) -> SceneProfile | None:
        """Get scene profile by name."""
        return self._scene_profiles.get(name)
    
    # =========================================================================
    # File Operations
    # =========================================================================
    
    def register_from_file(self, path: str | Path) -> int:
        """Load presets from a YAML or JSON file.
        
        Returns number of presets loaded.
        """
        path = Path(path)
        
        if path.suffix in (".yaml", ".yml"):
            with open(path) as f:
                data = yaml.safe_load(f)
        elif path.suffix == ".json":
            with open(path) as f:
                data = json.load(f)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        count = 0
        if isinstance(data, dict):
            if "presets" in data:
                for preset_data in data["presets"]:
                    self.register(Preset.from_dict(preset_data))
                    count += 1
            elif "name" in data:
                # Single preset
                self.register(Preset.from_dict(data))
                count += 1
        elif isinstance(data, list):
            for preset_data in data:
                self.register(Preset.from_dict(preset_data))
                count += 1
        
        return count
    
    def save_to_file(self, path: str | Path) -> None:
        """Save all presets to a file."""
        path = Path(path)
        
        data = {
            "presets": [p.to_dict() for p in self._presets.values()],
        }
        
        if path.suffix in (".yaml", ".yml"):
            with open(path, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
        elif path.suffix == ".json":
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
    
    # =========================================================================
    # Built-in Presets
    # =========================================================================
    
    def _load_builtins(self) -> None:
        """Load built-in presets for common use cases."""
        
        # Broadcast Clean - Podcast/radio quality
        self.register(Preset(
            name="broadcast_clean",
            description="Clean, broadcast-ready audio for podcasts and radio",
            effects=[
                EffectConfig("eq", {
                    "low_cut_hz": 80,
                    "low_shelf_hz": 200, "low_shelf_db": -1,
                    "high_shelf_hz": 8000, "high_shelf_db": -2,
                }),
                EffectConfig("compressor", {
                    "threshold_db": -18,
                    "ratio": 3.0,
                    "attack_ms": 10,
                    "release_ms": 100,
                    "makeup_db": 2,
                }),
                EffectConfig("limiter", {
                    "ceiling_db": -1.0,
                    "release_ms": 50,
                }),
            ],
            metadata={"category": "broadcast", "target_lufs": -16},
        ))
        
        # Warm Female - Optimized for female voices
        self.register(Preset(
            name="warm_female",
            description="Warm, rich tone optimized for female voices",
            effects=[
                EffectConfig("eq", {
                    "low_cut_hz": 100,
                    "low_shelf_hz": 250, "low_shelf_db": 2,
                    "mid_hz": 2500, "mid_db": 1, "mid_q": 1.0,
                    "high_shelf_hz": 10000, "high_shelf_db": 1,
                }),
                EffectConfig("compressor", {
                    "threshold_db": -20,
                    "ratio": 2.5,
                    "attack_ms": 15,
                    "release_ms": 150,
                    "makeup_db": 3,
                }),
            ],
            metadata={"category": "voice", "gender": "female"},
        ))
        
        # Broadcast Male - Optimized for male voices
        self.register(Preset(
            name="broadcast_male",
            description="Clean broadcast tone for male voices",
            effects=[
                EffectConfig("eq", {
                    "low_cut_hz": 60,
                    "low_shelf_hz": 150, "low_shelf_db": 1,
                    "mid_hz": 3000, "mid_db": 1.5, "mid_q": 0.8,
                    "high_shelf_hz": 8000, "high_shelf_db": -1,
                }),
                EffectConfig("compressor", {
                    "threshold_db": -16,
                    "ratio": 3.0,
                    "attack_ms": 8,
                    "release_ms": 120,
                    "makeup_db": 2,
                }),
                EffectConfig("limiter", {
                    "ceiling_db": -1.0,
                }),
            ],
            metadata={"category": "voice", "gender": "male"},
        ))
        
        # Background Duck - For music behind dialogue
        self.register(Preset(
            name="background_duck",
            description="Music preset with automatic ducking for dialogue",
            effects=[
                EffectConfig("eq", {
                    "low_cut_hz": 40,
                    "high_cut_hz": 15000,
                }),
                EffectConfig("compressor", {
                    "threshold_db": -24,
                    "ratio": 2.0,
                    "attack_ms": 30,
                    "release_ms": 200,
                }),
            ],
            metadata={"category": "music", "duck_enabled": True},
        ))
        
        # Subtle SFX - Sound effects processing
        self.register(Preset(
            name="subtle_sfx",
            description="Subtle processing for sound effects",
            effects=[
                EffectConfig("eq", {
                    "low_cut_hz": 60,
                }),
                EffectConfig("compressor", {
                    "threshold_db": -12,
                    "ratio": 2.0,
                    "attack_ms": 5,
                    "release_ms": 50,
                }),
            ],
            metadata={"category": "sfx"},
        ))
        
        # Room Ambiance - For ambiance tracks
        self.register(Preset(
            name="room_ambiance",
            description="Processing for ambient background audio",
            effects=[
                EffectConfig("eq", {
                    "low_cut_hz": 80,
                    "high_shelf_hz": 6000, "high_shelf_db": -3,
                }),
            ],
            metadata={"category": "ambiance"},
        ))
        
        # Narration - Audiobook style
        self.register(Preset(
            name="narration",
            description="Clear, intimate narration for audiobooks",
            effects=[
                EffectConfig("eq", {
                    "low_cut_hz": 70,
                    "low_shelf_hz": 200, "low_shelf_db": 1,
                    "mid_hz": 3500, "mid_db": 2, "mid_q": 1.5,
                    "high_shelf_hz": 10000, "high_shelf_db": 2,
                }),
                EffectConfig("compressor", {
                    "threshold_db": -22,
                    "ratio": 2.0,
                    "attack_ms": 20,
                    "release_ms": 200,
                    "makeup_db": 4,
                }),
                EffectConfig("limiter", {
                    "ceiling_db": -3.0,
                }),
            ],
            metadata={"category": "narration"},
        ))
        
        # Theatrical - Dramatic dialogue
        self.register(Preset(
            name="theatrical",
            description="Dynamic range preserved for theatrical dialogue",
            effects=[
                EffectConfig("eq", {
                    "low_cut_hz": 60,
                    "mid_hz": 2000, "mid_db": 1, "mid_q": 2.0,
                }),
                EffectConfig("compressor", {
                    "threshold_db": -24,
                    "ratio": 1.5,  # Gentle ratio preserves dynamics
                    "attack_ms": 30,
                    "release_ms": 300,
                }),
            ],
            metadata={"category": "theatrical"},
        ))
        
        # Loud and Clear - Maximum intelligibility
        self.register(Preset(
            name="loud_clear",
            description="Maximum intelligibility for announcements",
            effects=[
                EffectConfig("eq", {
                    "low_cut_hz": 100,
                    "mid_hz": 3000, "mid_db": 3, "mid_q": 1.0,
                    "high_shelf_hz": 6000, "high_shelf_db": -2,
                }),
                EffectConfig("compressor", {
                    "threshold_db": -15,
                    "ratio": 4.0,
                    "attack_ms": 5,
                    "release_ms": 80,
                    "makeup_db": 5,
                }),
                EffectConfig("limiter", {
                    "ceiling_db": -0.5,
                }),
            ],
            metadata={"category": "announcement"},
        ))
        
        # Transparent - Minimal processing
        self.register(Preset(
            name="transparent",
            description="Minimal processing, just safety limiting",
            effects=[
                EffectConfig("limiter", {
                    "ceiling_db": -1.0,
                }),
            ],
            metadata={"category": "general"},
        ))


# Convenience factory functions
def EQ(**params) -> EffectConfig:
    """Create an EQ effect config."""
    return EffectConfig("eq", params)


def Compressor(**params) -> EffectConfig:
    """Create a Compressor effect config."""
    return EffectConfig("compressor", params)


def Limiter(**params) -> EffectConfig:
    """Create a Limiter effect config."""
    return EffectConfig("limiter", params)


def Reverb(**params) -> EffectConfig:
    """Create a Reverb effect config."""
    return EffectConfig("reverb", params)


def DeEsser(**params) -> EffectConfig:
    """Create a De-esser effect config."""
    return EffectConfig("de_esser", params)


def NoiseGate(**params) -> EffectConfig:
    """Create a Noise Gate effect config."""
    return EffectConfig("noise_gate", params)
