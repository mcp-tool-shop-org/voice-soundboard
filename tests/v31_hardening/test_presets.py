"""
v3.1 Hardening Tests - DSP Presets & Profiles.

Tests for the preset system ensuring:
- Presets apply correctly
- Presets serialize/deserialize perfectly
- Voice profiles override presets properly
- Scene profiles set correct defaults
"""

import pytest
from pathlib import Path
import json
import tempfile

from voice_soundboard.v3.presets import (
    Preset,
    PresetLibrary,
    VoiceProfile,
    SceneProfile,
    EffectConfig,
    EQ,
    Compressor,
    Limiter,
)


class TestPreset:
    """Tests for Preset class."""
    
    def test_create_preset(self):
        """Basic preset creation."""
        preset = Preset(
            name="test_preset",
            description="A test preset",
            effects=[
                EffectConfig("eq", {"low_cut_hz": 80}),
                EffectConfig("compressor", {"threshold_db": -18}),
            ],
        )
        
        assert preset.name == "test_preset"
        assert len(preset.effects) == 2
        assert preset.effects[0].effect_type == "eq"
    
    def test_preset_to_effect_nodes(self):
        """Converting preset to EffectNodes."""
        preset = Preset(
            name="test",
            effects=[
                EffectConfig("eq", {"gain": 0}),
                EffectConfig("limiter", {"ceiling_db": -1}),
            ],
        )
        
        nodes = preset.to_effect_nodes()
        
        assert len(nodes) == 2
        assert nodes[0].effect_type == "eq"
        assert nodes[1].effect_type == "limiter"
        assert nodes[0].params == {"gain": 0}
    
    def test_preset_serialization(self):
        """Preset should serialize to dict."""
        preset = Preset(
            name="serialization_test",
            version="2.0.0",
            description="Test description",
            effects=[
                EffectConfig("eq", {"low_cut_hz": 100}),
            ],
            metadata={"author": "test"},
        )
        
        data = preset.to_dict()
        
        assert data["name"] == "serialization_test"
        assert data["version"] == "2.0.0"
        assert data["description"] == "Test description"
        assert len(data["effects"]) == 1
        assert data["effects"][0]["type"] == "eq"
        assert data["metadata"]["author"] == "test"
    
    def test_preset_deserialization(self):
        """Preset should deserialize from dict."""
        data = {
            "name": "deserialized",
            "version": "1.5.0",
            "description": "From dict",
            "effects": [
                {"type": "compressor", "params": {"ratio": 4}, "enabled": True},
            ],
            "metadata": {"source": "test"},
        }
        
        preset = Preset.from_dict(data)
        
        assert preset.name == "deserialized"
        assert preset.version == "1.5.0"
        assert len(preset.effects) == 1
        assert preset.effects[0].params["ratio"] == 4
    
    def test_preset_round_trip(self):
        """Preset serialization should round-trip perfectly."""
        original = Preset(
            name="round_trip",
            version="3.0.0",
            effects=[
                EffectConfig("eq", {"low_cut_hz": 80, "high_shelf_db": -2}),
                EffectConfig("compressor", {"threshold_db": -18, "ratio": 3.0}),
                EffectConfig("limiter", {"ceiling_db": -1.0}, enabled=False),
            ],
            metadata={"category": "test", "id": 123},
        )
        
        # Round trip
        data = original.to_dict()
        restored = Preset.from_dict(data)
        
        assert restored.name == original.name
        assert restored.version == original.version
        assert len(restored.effects) == len(original.effects)
        
        for orig_eff, rest_eff in zip(original.effects, restored.effects):
            assert rest_eff.effect_type == orig_eff.effect_type
            assert rest_eff.params == orig_eff.params
            assert rest_eff.enabled == orig_eff.enabled


class TestEffectConfigFactories:
    """Tests for effect config factory functions."""
    
    def test_eq_factory(self):
        """EQ factory should create EffectConfig."""
        eq = EQ(low_cut_hz=100, high_shelf_db=-3)
        
        assert eq.effect_type == "eq"
        assert eq.params["low_cut_hz"] == 100
        assert eq.params["high_shelf_db"] == -3
    
    def test_compressor_factory(self):
        """Compressor factory should work."""
        comp = Compressor(threshold_db=-18, ratio=4.0)
        
        assert comp.effect_type == "compressor"
        assert comp.params["threshold_db"] == -18
        assert comp.params["ratio"] == 4.0
    
    def test_limiter_factory(self):
        """Limiter factory should work."""
        lim = Limiter(ceiling_db=-0.5)
        
        assert lim.effect_type == "limiter"
        assert lim.params["ceiling_db"] == -0.5


class TestVoiceProfile:
    """Tests for VoiceProfile class."""
    
    def test_create_voice_profile(self):
        """Basic voice profile creation."""
        profile = VoiceProfile(
            voice_id="af_bella",
            preset_name="warm_female",
            overrides={"eq": {"bass_boost_db": 2}},
            gain_db=1.5,
        )
        
        assert profile.voice_id == "af_bella"
        assert profile.preset_name == "warm_female"
        assert profile.gain_db == 1.5
    
    def test_apply_overrides(self):
        """Voice profile should apply overrides to preset."""
        base_preset = Preset(
            name="base",
            effects=[
                EffectConfig("eq", {"low_cut_hz": 80, "bass_db": 0}),
                EffectConfig("compressor", {"ratio": 2.0}),
            ],
        )
        
        profile = VoiceProfile(
            voice_id="test_voice",
            preset_name="base",
            overrides={
                "eq": {"bass_db": 3},  # Override bass
            },
        )
        
        customized = profile.apply_overrides(base_preset)
        
        # Should have same structure
        assert len(customized.effects) == 2
        
        # EQ should have override applied
        eq_effect = customized.effects[0]
        assert eq_effect.params["bass_db"] == 3
        assert eq_effect.params["low_cut_hz"] == 80  # Unchanged
        
        # Compressor should be unchanged
        comp_effect = customized.effects[1]
        assert comp_effect.params["ratio"] == 2.0
    
    def test_override_creates_new_preset(self):
        """Overrides should not modify original preset."""
        original = Preset(
            name="original",
            effects=[EffectConfig("eq", {"gain": 0})],
        )
        
        profile = VoiceProfile(
            voice_id="test",
            preset_name="original",
            overrides={"eq": {"gain": 5}},
        )
        
        customized = profile.apply_overrides(original)
        
        # Original should be unchanged
        assert original.effects[0].params["gain"] == 0
        # Customized should have override
        assert customized.effects[0].params["gain"] == 5


class TestSceneProfile:
    """Tests for SceneProfile class."""
    
    def test_create_scene_profile(self):
        """Basic scene profile creation."""
        profile = SceneProfile(
            name="podcast",
            track_defaults={
                "dialogue": "broadcast_clean",
                "music": "background_duck",
            },
            master_preset="broadcast_master",
            duck_dialogue_over_music=True,
            duck_amount=0.8,
            crossfade_ms=150,
        )
        
        assert profile.name == "podcast"
        assert profile.track_defaults["dialogue"] == "broadcast_clean"
        assert profile.duck_amount == 0.8


class TestPresetLibrary:
    """Tests for PresetLibrary class."""
    
    def test_library_has_builtins(self):
        """Library should have built-in presets."""
        library = PresetLibrary()
        
        presets = library.list_presets()
        
        assert len(presets) > 0
        assert "broadcast_clean" in presets
        assert "warm_female" in presets
        assert "broadcast_male" in presets
    
    def test_get_builtin_preset(self):
        """Should get built-in presets."""
        library = PresetLibrary()
        
        preset = library.get("broadcast_clean")
        
        assert preset is not None
        assert preset.name == "broadcast_clean"
        assert len(preset.effects) > 0
    
    def test_register_custom_preset(self):
        """Should register custom presets."""
        library = PresetLibrary()
        custom = Preset(
            name="my_custom",
            effects=[EffectConfig("eq", {"gain": 0})],
        )
        
        library.register(custom)
        
        assert "my_custom" in library.list_presets()
        assert library.get("my_custom") == custom
    
    def test_remove_preset(self):
        """Should remove presets."""
        library = PresetLibrary()
        library.register(Preset(name="to_remove", effects=[]))
        
        assert library.remove("to_remove") is True
        assert "to_remove" not in library.list_presets()
    
    def test_remove_nonexistent_preset(self):
        """Removing non-existent preset returns False."""
        library = PresetLibrary()
        
        assert library.remove("nonexistent") is False
    
    def test_register_voice_profile(self):
        """Should register voice profiles."""
        library = PresetLibrary()
        profile = VoiceProfile(
            voice_id="af_bella",
            preset_name="warm_female",
        )
        
        library.register_voice_profile(profile)
        
        assert library.get_voice_profile("af_bella") == profile
    
    def test_get_preset_for_voice(self):
        """Should return customized preset for voice."""
        library = PresetLibrary()
        profile = VoiceProfile(
            voice_id="test_voice",
            preset_name="broadcast_clean",
            overrides={"eq": {"low_cut_hz": 100}},
        )
        library.register_voice_profile(profile)
        
        preset = library.get_preset_for_voice("test_voice")
        
        assert preset is not None
        assert "test_voice" in preset.name
        # Should have the override
        eq_effect = [e for e in preset.effects if e.effect_type == "eq"][0]
        assert eq_effect.params["low_cut_hz"] == 100
    
    def test_get_preset_for_unknown_voice(self):
        """Should return None for unknown voice."""
        library = PresetLibrary()
        
        preset = library.get_preset_for_voice("unknown_voice")
        
        assert preset is None
    
    def test_register_scene_profile(self):
        """Should register scene profiles."""
        library = PresetLibrary()
        profile = SceneProfile(name="my_scene", track_defaults={})
        
        library.register_scene_profile(profile)
        
        assert library.get_scene_profile("my_scene") == profile


class TestPresetFileOperations:
    """Tests for file-based preset operations."""
    
    def test_load_from_yaml(self, tmp_path):
        """Should load presets from YAML file."""
        yaml_content = """
presets:
  - name: from_yaml
    version: "1.0.0"
    effects:
      - type: eq
        params:
          low_cut_hz: 80
      - type: compressor
        params:
          ratio: 2
"""
        yaml_file = tmp_path / "presets.yaml"
        yaml_file.write_text(yaml_content)
        
        library = PresetLibrary()
        count = library.register_from_file(yaml_file)
        
        assert count == 1
        preset = library.get("from_yaml")
        assert preset is not None
        assert len(preset.effects) == 2
    
    def test_load_from_json(self, tmp_path):
        """Should load presets from JSON file."""
        json_content = {
            "presets": [
                {
                    "name": "from_json",
                    "version": "1.0.0",
                    "effects": [
                        {"type": "limiter", "params": {"ceiling_db": -1}}
                    ]
                }
            ]
        }
        json_file = tmp_path / "presets.json"
        json_file.write_text(json.dumps(json_content))
        
        library = PresetLibrary()
        count = library.register_from_file(json_file)
        
        assert count == 1
        assert library.get("from_json") is not None
    
    def test_load_single_preset(self, tmp_path):
        """Should load a single preset file."""
        json_content = {
            "name": "single_preset",
            "version": "1.0.0",
            "effects": [{"type": "eq", "params": {}}]
        }
        json_file = tmp_path / "single.json"
        json_file.write_text(json.dumps(json_content))
        
        library = PresetLibrary()
        count = library.register_from_file(json_file)
        
        assert count == 1
        assert library.get("single_preset") is not None
    
    def test_save_to_yaml(self, tmp_path):
        """Should save presets to YAML file."""
        library = PresetLibrary()
        library.register(Preset(
            name="save_test",
            effects=[EffectConfig("eq", {"gain": 5})],
        ))
        
        yaml_file = tmp_path / "saved.yaml"
        library.save_to_file(yaml_file)
        
        assert yaml_file.exists()
        content = yaml_file.read_text()
        assert "save_test" in content
    
    def test_save_to_json(self, tmp_path):
        """Should save presets to JSON file."""
        library = PresetLibrary()
        library.register(Preset(
            name="json_save",
            effects=[EffectConfig("compressor", {"ratio": 3})],
        ))
        
        json_file = tmp_path / "saved.json"
        library.save_to_file(json_file)
        
        assert json_file.exists()
        data = json.loads(json_file.read_text())
        assert "presets" in data
    
    def test_unsupported_format_raises(self, tmp_path):
        """Unsupported file format should raise."""
        library = PresetLibrary()
        
        with pytest.raises(ValueError):
            library.register_from_file(tmp_path / "file.txt")
        
        with pytest.raises(ValueError):
            library.save_to_file(tmp_path / "file.txt")


class TestBuiltinPresets:
    """Tests for built-in preset quality."""
    
    def test_broadcast_clean_structure(self):
        """broadcast_clean should have expected effects."""
        library = PresetLibrary()
        preset = library.get("broadcast_clean")
        
        effect_types = [e.effect_type for e in preset.effects]
        
        assert "eq" in effect_types
        assert "compressor" in effect_types
        assert "limiter" in effect_types
    
    def test_all_builtins_have_metadata(self):
        """All built-in presets should have metadata."""
        library = PresetLibrary()
        
        for name in library.list_presets():
            preset = library.get(name)
            assert preset.metadata is not None
            assert "category" in preset.metadata
    
    def test_all_builtins_have_descriptions(self):
        """All built-in presets should have descriptions."""
        library = PresetLibrary()
        
        for name in library.list_presets():
            preset = library.get(name)
            assert preset.description, f"Preset {name} missing description"
    
    def test_preset_application_under_1ms(self):
        """Preset application should be fast (< 1ms)."""
        import time
        
        library = PresetLibrary()
        preset = library.get("broadcast_clean")
        
        start = time.perf_counter()
        for _ in range(1000):
            nodes = preset.to_effect_nodes()
        elapsed = (time.perf_counter() - start) / 1000 * 1000  # ms per call
        
        assert elapsed < 1.0, f"Preset application took {elapsed:.2f}ms"
