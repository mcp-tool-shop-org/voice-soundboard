"""
v3.1 Hardening Tests - AudioGraph Validation.

Tests for graph.validate(), graph.diff(), and graph.visualize().
Ensures early failure with actionable error messages.
"""

import pytest
from unittest.mock import MagicMock, patch

from voice_soundboard.v3.audio_graph import (
    AudioGraph,
    AudioTrack,
    EffectNode,
    TrackType,
    SpatialPosition,
    GraphDiff,
)
from voice_soundboard.v3.validation import (
    ValidationResult,
    ValidationError,
    ValidationSeverity,
    GraphValidationException,
)
from voice_soundboard.graph.types import ControlGraph, SpeakerRef, TokenEvent


class TestGraphValidation:
    """Tests for AudioGraph.validate()."""
    
    def test_empty_graph_is_valid(self):
        """Empty graph should be valid (no tracks is OK)."""
        graph = AudioGraph(name="empty")
        result = graph.validate()
        
        assert result.is_valid
        assert result.error_count == 0
    
    def test_invalid_sample_rate_detected(self):
        """Invalid sample rate should produce an error."""
        graph = AudioGraph(sample_rate=12345)  # Invalid
        result = graph.validate()
        
        assert not result.is_valid
        assert result.error_count == 1
        
        error = result.errors[0]
        assert error.code == "INVALID_SAMPLE_RATE"
        assert "12345" in error.message
        assert error.suggestion is not None  # Has actionable suggestion
    
    def test_valid_sample_rates_accepted(self):
        """Standard sample rates should be accepted."""
        for rate in [22050, 24000, 44100, 48000]:
            graph = AudioGraph(sample_rate=rate)
            result = graph.validate()
            assert result.is_valid, f"Sample rate {rate} should be valid"
    
    def test_empty_track_warning(self):
        """Empty track should produce a warning, not an error."""
        graph = AudioGraph()
        graph.add_track("empty_track", TrackType.DIALOGUE)
        
        result = graph.validate()
        
        assert result.is_valid  # Warnings don't make it invalid
        assert result.has_warnings
        
        warning = result.filter_by_severity(ValidationSeverity.WARNING)[0]
        assert warning.code == "EMPTY_TRACK"
        assert "empty_track" in warning.message
    
    def test_empty_track_strict_mode(self):
        """In strict mode, warnings become errors."""
        graph = AudioGraph()
        graph.add_track("empty_track")
        
        result = graph.validate(strict=True)
        
        assert not result.is_valid
        assert result.error_count == 1
    
    def test_invalid_volume_detected(self):
        """Volume out of range should be an error."""
        graph = AudioGraph()
        track = graph.add_track("test")
        track.volume = 5.0  # Invalid (max 2.0)
        
        result = graph.validate()
        
        assert not result.is_valid
        error = result.filter_by_code("INVALID_PARAMETER")[0]
        assert "volume" in error.message
    
    def test_invalid_pan_detected(self):
        """Pan out of range should be an error."""
        graph = AudioGraph()
        track = graph.add_track("test")
        track.pan = 2.0  # Invalid (must be -1 to 1)
        
        result = graph.validate()
        
        assert not result.is_valid
        error = result.filter_by_code("INVALID_PARAMETER")[0]
        assert "pan" in error.message
    
    def test_effect_chain_too_deep(self):
        """Excessively deep effect chains should be errors."""
        graph = AudioGraph()
        track = graph.add_track("test")
        
        # Add more effects than allowed
        for i in range(20):  # Max is 16
            track.add_effect(EffectNode(
                name=f"effect_{i}",
                effect_type="eq",
                params={"gain": 0},
            ))
        
        result = graph.validate()
        
        assert not result.is_valid
        error = result.filter_by_code("EFFECT_CHAIN_TOO_DEEP")[0]
        assert "20" in error.message
        assert "16" in error.message
    
    def test_invalid_duck_target(self):
        """Ducking for non-existent track should be an error."""
        graph = AudioGraph()
        track = graph.add_track("music", TrackType.MUSIC)
        track.duck_for = ["nonexistent_track"]
        
        result = graph.validate()
        
        assert not result.is_valid
        error = result.filter_by_code("INVALID_DUCK_TARGET")[0]
        assert "nonexistent_track" in error.message
    
    def test_valid_duck_target(self):
        """Ducking for existing track should be OK."""
        graph = AudioGraph()
        graph.add_track("dialogue", TrackType.DIALOGUE)
        music = graph.add_track("music", TrackType.MUSIC)
        music.duck_for = ["dialogue"]
        
        result = graph.validate()
        assert result.filter_by_code("INVALID_DUCK_TARGET") == []
    
    def test_incompatible_sample_rates_warning(self):
        """Mismatched sample rates across tracks should warn."""
        graph = AudioGraph(sample_rate=24000)
        track1 = graph.add_track("track1")
        track1.sample_rate = 24000
        track2 = graph.add_track("track2")
        track2.sample_rate = 44100
        
        result = graph.validate()
        
        assert result.has_warnings
        warning = result.filter_by_code("INCOMPATIBLE_SAMPLE_RATES")[0]
        assert "24000" in str(warning.context) or "44100" in str(warning.context)
    
    def test_invalid_spatial_position(self):
        """Invalid spatial position (z <= 0) should be an error."""
        graph = AudioGraph()
        track = graph.add_track("test")
        # SpatialPosition validates in __post_init__ so we need to bypass
        track.position = SpatialPosition.__new__(SpatialPosition)
        track.position.x = 0
        track.position.y = 0
        track.position.z = -1  # Invalid
        
        result = graph.validate()
        
        assert not result.is_valid
        assert any("z" in e.message.lower() or "distance" in e.message.lower() 
                  for e in result.errors)
    
    def test_plugin_external_state_violation(self):
        """Plugin with external state should be flagged."""
        graph = AudioGraph()
        
        # Mock plugin with external state
        plugin = MagicMock()
        plugin.name = "bad_plugin"
        plugin.has_external_state = True
        
        graph.register_plugin(plugin)
        result = graph.validate()
        
        assert not result.is_valid
        error = result.filter_by_code("PLUGIN_VIOLATION")[0]
        assert "bad_plugin" in error.message
        assert "external state" in error.message.lower()
    
    def test_control_graph_validation_integration(self):
        """ControlGraph issues should be surfaced."""
        graph = AudioGraph()
        track = graph.add_track("dialogue")
        
        # Create ControlGraph with issues
        track.control_graph = ControlGraph(
            tokens=[],  # Empty tokens - should be caught
            speaker=SpeakerRef.from_voice("test"),
            global_speed=-1,  # Invalid
        )
        
        result = graph.validate()
        
        assert not result.is_valid
        # Should catch the ControlGraph issues
        assert result.error_count > 0
    
    def test_raise_if_invalid(self):
        """raise_if_invalid() should raise on errors."""
        graph = AudioGraph(sample_rate=12345)  # Invalid
        result = graph.validate()
        
        with pytest.raises(GraphValidationException) as exc_info:
            result.raise_if_invalid()
        
        assert exc_info.value.result == result


class TestGraphDiff:
    """Tests for AudioGraph.diff()."""
    
    def test_identical_graphs_have_no_diff(self):
        """Identical graphs should produce empty diff."""
        graph1 = AudioGraph(name="test", sample_rate=24000)
        graph1.add_track("track1")
        
        graph2 = AudioGraph(name="test", sample_rate=24000)
        graph2.add_track("track1")
        
        diff = graph1.diff(graph2)
        
        assert not diff.has_changes
        assert len(diff) == 0
    
    def test_name_change_detected(self):
        """Name change should be detected."""
        graph1 = AudioGraph(name="old_name")
        graph2 = AudioGraph(name="new_name")
        
        diff = graph1.diff(graph2)
        
        assert diff.has_changes
        change = diff.modified[0]
        assert change.path == "name"
        assert change.old_value == "old_name"
        assert change.new_value == "new_name"
    
    def test_sample_rate_change_detected(self):
        """Sample rate change should be detected."""
        graph1 = AudioGraph(sample_rate=24000)
        graph2 = AudioGraph(sample_rate=44100)
        
        diff = graph1.diff(graph2)
        
        assert diff.has_changes
        change = diff.modified[0]
        assert change.path == "sample_rate"
    
    def test_added_track_detected(self):
        """Added track should be detected."""
        graph1 = AudioGraph()
        graph2 = AudioGraph()
        graph2.add_track("new_track")
        
        diff = graph1.diff(graph2)
        
        assert diff.has_changes
        assert len(diff.added) == 1
        assert "new_track" in diff.added[0].path
    
    def test_removed_track_detected(self):
        """Removed track should be detected."""
        graph1 = AudioGraph()
        graph1.add_track("old_track")
        graph2 = AudioGraph()
        
        diff = graph1.diff(graph2)
        
        assert diff.has_changes
        assert len(diff.removed) == 1
        assert "old_track" in diff.removed[0].path
    
    def test_track_volume_change_detected(self):
        """Track volume change should be detected."""
        graph1 = AudioGraph()
        track1 = graph1.add_track("track1")
        track1.volume = 0.5
        
        graph2 = AudioGraph()
        track2 = graph2.add_track("track1")
        track2.volume = 0.8
        
        diff = graph1.diff(graph2)
        
        assert diff.has_changes
        change = [c for c in diff.modified if "volume" in c.path][0]
        assert change.old_value == 0.5
        assert change.new_value == 0.8
    
    def test_effect_added_detected(self):
        """Added effect should be detected."""
        graph1 = AudioGraph()
        graph1.add_track("track1")
        
        graph2 = AudioGraph()
        track2 = graph2.add_track("track1")
        track2.add_effect(EffectNode(name="eq1", effect_type="eq"))
        
        diff = graph1.diff(graph2)
        
        assert diff.has_changes
        assert len(diff.added) == 1
    
    def test_effect_params_change_detected(self):
        """Effect parameter change should be detected."""
        graph1 = AudioGraph()
        track1 = graph1.add_track("track1")
        track1.add_effect(EffectNode(name="eq1", effect_type="eq", params={"gain": 0}))
        
        graph2 = AudioGraph()
        track2 = graph2.add_track("track1")
        # Same effect type but different params = different ID
        track2.add_effect(EffectNode(name="eq1", effect_type="eq", params={"gain": 5}))
        
        diff = graph1.diff(graph2)
        
        # Because effect ID is based on type+params, this shows as add/remove
        assert diff.has_changes
    
    def test_diff_string_representation(self):
        """Diff should have useful string representation."""
        graph1 = AudioGraph(name="old")
        graph2 = AudioGraph(name="new")
        
        diff = graph1.diff(graph2)
        
        diff_str = str(diff)
        assert "old" in diff_str or "new" in diff_str


class TestGraphVisualize:
    """Tests for AudioGraph.visualize()."""
    
    def test_mermaid_output(self):
        """Mermaid diagram should be generated correctly."""
        graph = AudioGraph(name="test")
        graph.add_track("dialogue", TrackType.DIALOGUE)
        graph.add_track("music", TrackType.MUSIC)
        
        mermaid = graph.visualize(format="mermaid")
        
        assert "```mermaid" in mermaid
        assert "graph LR" in mermaid
        assert "dialogue" in mermaid
        assert "music" in mermaid
        assert "Master" in mermaid
        assert "Output" in mermaid
    
    def test_mermaid_with_effects(self):
        """Mermaid should show effect chains."""
        graph = AudioGraph()
        track = graph.add_track("voice")
        track.add_effect(EffectNode(name="eq", effect_type="eq"))
        track.add_effect(EffectNode(name="comp", effect_type="compressor"))
        
        mermaid = graph.visualize(format="mermaid")
        
        assert "eq" in mermaid
        assert "compressor" in mermaid
        assert "-->" in mermaid  # Connection arrows
    
    def test_dot_output(self):
        """DOT format should be generated correctly."""
        graph = AudioGraph(name="test")
        graph.add_track("track1")
        
        dot = graph.visualize(format="dot")
        
        assert "digraph" in dot
        assert "track1" in dot
        assert "->" in dot
    
    def test_ascii_output(self):
        """ASCII format should be readable."""
        graph = AudioGraph(name="my_graph")
        graph.add_track("dialogue", TrackType.DIALOGUE)
        track = graph.add_track("music", TrackType.MUSIC)
        track.volume = 0.5
        
        ascii_repr = graph.visualize(format="ascii")
        
        assert "my_graph" in ascii_repr
        assert "dialogue" in ascii_repr
        assert "music" in ascii_repr
    
    def test_invalid_format_raises(self):
        """Invalid format should raise ValueError."""
        graph = AudioGraph()
        
        with pytest.raises(ValueError) as exc_info:
            graph.visualize(format="invalid")
        
        assert "invalid" in str(exc_info.value)
    
    def test_write_to_file(self, tmp_path):
        """visualize() should write to file when path provided."""
        graph = AudioGraph(name="test")
        graph.add_track("track1")
        
        output_file = tmp_path / "graph.mmd"
        result = graph.visualize(output=str(output_file), format="mermaid")
        
        assert output_file.exists()
        content = output_file.read_text()
        assert "```mermaid" in content
        assert result == content


class TestValidationError:
    """Tests for ValidationError factories."""
    
    def test_invalid_sample_rate_factory(self):
        """Factory should create proper error."""
        error = ValidationError.invalid_sample_rate("graph", 12345)
        
        assert error.code == "INVALID_SAMPLE_RATE"
        assert error.severity == ValidationSeverity.ERROR
        assert "12345" in error.message
        assert error.suggestion is not None
        assert error.context["rate"] == 12345
    
    def test_empty_track_factory(self):
        """Factory should create proper warning."""
        error = ValidationError.empty_track("tracks[0]", "dialogue")
        
        assert error.code == "EMPTY_TRACK"
        assert error.severity == ValidationSeverity.WARNING
        assert "dialogue" in error.message
    
    def test_cycle_detected_factory(self):
        """Factory should show cycle path."""
        error = ValidationError.cycle_detected(
            "graph",
            ["track1", "effect1", "track2", "track1"]
        )
        
        assert error.code == "CYCLE_DETECTED"
        assert "track1 -> effect1 -> track2 -> track1" in error.message
    
    def test_error_string_representation(self):
        """Error should have informative string representation."""
        error = ValidationError(
            location="tracks[0].volume",
            message="Invalid volume",
            severity=ValidationSeverity.ERROR,
            suggestion="Use a value between 0 and 2",
            code="INVALID_VOLUME",
        )
        
        error_str = str(error)
        
        assert "ERROR" in error_str
        assert "tracks[0].volume" in error_str
        assert "Invalid volume" in error_str
        assert "Suggestion" in error_str


class TestValidationResult:
    """Tests for ValidationResult aggregation."""
    
    def test_empty_result_is_valid(self):
        """Empty result should be valid."""
        result = ValidationResult()
        
        assert result.is_valid
        assert not result.has_warnings
        assert result.error_count == 0
        assert result.warning_count == 0
    
    def test_add_error_makes_invalid(self):
        """Adding an error should make result invalid."""
        result = ValidationResult()
        result.add(ValidationError(
            location="test",
            message="test error",
            severity=ValidationSeverity.ERROR,
        ))
        
        assert not result.is_valid
        assert result.error_count == 1
    
    def test_add_warning_stays_valid(self):
        """Adding a warning should not make result invalid."""
        result = ValidationResult()
        result.add(ValidationError(
            location="test",
            message="test warning",
            severity=ValidationSeverity.WARNING,
        ))
        
        assert result.is_valid
        assert result.has_warnings
        assert result.warning_count == 1
    
    def test_merge_results(self):
        """Merging should combine errors."""
        result1 = ValidationResult()
        result1.add(ValidationError(location="a", message="error 1"))
        
        result2 = ValidationResult()
        result2.add(ValidationError(location="b", message="error 2"))
        
        result1.merge(result2)
        
        assert len(result1) == 2
        assert result1.error_count == 2
    
    def test_filter_by_severity(self):
        """Filtering by severity should work."""
        result = ValidationResult()
        result.add(ValidationError(location="a", message="error", 
                                   severity=ValidationSeverity.ERROR))
        result.add(ValidationError(location="b", message="warning",
                                   severity=ValidationSeverity.WARNING))
        result.add(ValidationError(location="c", message="info",
                                   severity=ValidationSeverity.INFO))
        
        errors = result.filter_by_severity(ValidationSeverity.ERROR)
        warnings = result.filter_by_severity(ValidationSeverity.WARNING)
        
        assert len(errors) == 1
        assert len(warnings) == 1
    
    def test_filter_by_code(self):
        """Filtering by code should work."""
        result = ValidationResult()
        result.add(ValidationError(location="a", message="", code="TYPE_A"))
        result.add(ValidationError(location="b", message="", code="TYPE_B"))
        result.add(ValidationError(location="c", message="", code="TYPE_A"))
        
        type_a = result.filter_by_code("TYPE_A")
        
        assert len(type_a) == 2
    
    def test_bool_conversion(self):
        """Bool conversion should reflect validity."""
        valid_result = ValidationResult()
        invalid_result = ValidationResult()
        invalid_result.add(ValidationError(location="x", message="error"))
        
        assert bool(valid_result) is True
        assert bool(invalid_result) is False
    
    def test_iteration(self):
        """Should be iterable over errors."""
        result = ValidationResult()
        result.add(ValidationError(location="a", message="1"))
        result.add(ValidationError(location="b", message="2"))
        
        messages = [e.message for e in result]
        
        assert messages == ["1", "2"]
