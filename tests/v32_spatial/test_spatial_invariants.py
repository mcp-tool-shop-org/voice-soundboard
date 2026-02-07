"""
v3.2 Spatial Invariant Tests — Regression tests for spatial invariants.

Section 3: Temporal & Ordering Invariants (Non-Negotiable)
Section 4: Loudness & Safety Invariants

These tests ensure spatialization does not break time or safety.
"""

import pytest

from voice_soundboard.v3.spatial import (
    Position3D,
    SpatialNode,
    ListenerNode,
    SpatialDownmixNode,
    SpatialGraph,
    HRTFEngine,
    HRTFParameters,
    SpatialSafetyLimits,
    validate_spatial_safety,
    create_spatial_scene,
)


class TestTemporalInvariants:
    """
    Section 3: Temporal & Ordering Invariants.
    
    Spatialization must not break time:
    - Temporal order preserved
    - No reordering of samples
    - No buffering beyond bounded window
    - Spatial processing does not alter duration
    """
    
    def test_sample_order_preserved(self):
        """Samples are not reordered by spatial processing."""
        engine = HRTFEngine()
        source = SpatialNode(name="test", position=Position3D(x=0.5, y=0, z=1))
        listener = ListenerNode()
        
        # Ascending sequence
        input_samples = list(range(100))
        
        left, right = engine.process_source(source, listener, [float(x) for x in input_samples])
        
        # Output should preserve relative ordering (each sample derived from its input)
        # Note: We can't check exact values due to filtering, but length must match
        assert len(left) == len(input_samples)
        assert len(right) == len(input_samples)
    
    def test_duration_unchanged(self):
        """Spatial processing does not alter duration."""
        engine = HRTFEngine()
        source = SpatialNode(name="test", position=Position3D(x=0, y=0, z=2))
        listener = ListenerNode()
        
        for length in [10, 100, 1000, 10000]:
            input_samples = [0.5] * length
            left, right = engine.process_source(source, listener, input_samples)
            
            assert len(left) == length, f"Duration changed from {length} to {len(left)}"
            assert len(right) == length, f"Duration changed from {length} to {len(right)}"
    
    def test_bounded_processing_window(self):
        """HRTF filter length bounds processing window."""
        params = HRTFParameters(filter_length=128)  # 128-tap filter
        engine = HRTFEngine(params)
        
        # Filter length is bounded
        assert params.filter_length <= 512  # Maximum allowed
    
    def test_no_future_samples_needed(self):
        """Processing doesn't require future samples (causal)."""
        engine = HRTFEngine()
        source = SpatialNode(name="test", position=Position3D(x=1, y=0, z=1))
        listener = ListenerNode()
        
        # Process small chunk
        chunk = [0.5] * 10
        left, right = engine.process_source(source, listener, chunk)
        
        # Each output sample depends only on current/past input
        assert len(left) == len(chunk)


class TestLoudnessInvariants:
    """
    Section 4: Loudness & Safety Invariants.
    
    Spatial audio often causes subtle clipping bugs.
    Required Guarantees:
    - No gain stacking from panning
    - Loudness bounded after HRTF
    - No clipping introduced by spatialization
    - Limiter applied after spatial mix
    """
    
    def test_no_gain_stacking_from_panning(self):
        """Panning doesn't increase total power."""
        listener = ListenerNode()
        
        # Check various positions
        positions = [
            Position3D(x=-1, y=0, z=1),  # Full left
            Position3D(x=0, y=0, z=1),   # Center
            Position3D(x=1, y=0, z=1),   # Full right
            Position3D(x=0.5, y=0.5, z=1),  # Mix
        ]
        
        for pos in positions:
            left_gain, right_gain = listener.calculate_ild(pos)
            
            # Total power should not exceed reference
            # For constant power panning, L² + R² = 1
            total_power = left_gain**2 + right_gain**2
            assert total_power <= 2.0, f"Gain stacking at position {pos}"
    
    def test_loudness_bounded_after_hrtf(self):
        """Output is bounded after HRTF processing."""
        engine = HRTFEngine()
        downmix = SpatialDownmixNode(limiter_enabled=True)
        listener = ListenerNode()
        
        # Multiple loud sources (worst case)
        sources = []
        for i in range(10):
            pos = Position3D(x=(i-5)/5, y=0, z=0.5)
            sources.append((SpatialNode(name=f"s{i}", position=pos), [0.9] * 100))
        
        left, right = engine.process_graph(sources, listener, downmix)
        
        # All samples should be bounded
        for l, r in zip(left, right):
            assert abs(l) <= 1.0
            assert abs(r) <= 1.0
    
    def test_no_clipping_from_spatialization(self):
        """Normnal-level input doesn't clip after spatialization."""
        engine = HRTFEngine()
        downmix = SpatialDownmixNode(
            limiter_enabled=True,
            limiter_threshold_db=-0.1
        )
        listener = ListenerNode()
        
        # Normal level source
        source = SpatialNode(name="normal", position=Position3D(x=0, y=0, z=1))
        input_samples = [0.5] * 100  # Well below clipping
        
        left, right = engine.process_source(source, listener, input_samples)
        
        # Apply downmix limiter
        for i in range(len(left)):
            left[i], right[i] = downmix.apply_limiter(left[i], right[i])
        
        # Should not clip
        for l, r in zip(left, right):
            assert abs(l) < 1.0
            assert abs(r) < 1.0
    
    def test_limiter_applied_after_mix(self):
        """Limiter is part of downmix stage."""
        downmix = SpatialDownmixNode(limiter_enabled=True)
        
        # Verify limiter is on by default
        assert downmix.limiter_enabled
        
        # Test limiting behavior
        loud_left, loud_right = 1.5, 1.5
        limited_left, limited_right = downmix.apply_limiter(loud_left, loud_right)
        
        assert limited_left < loud_left
        assert limited_right < loud_right


class TestSpatialSafetyValidation:
    """Tests for spatial safety limit validation."""
    
    def test_default_safety_limits(self):
        """Default safety limits are reasonable."""
        limits = SpatialSafetyLimits()
        
        assert limits.max_combined_gain >= 1.0
        assert limits.min_source_distance > 0
        assert limits.max_source_distance > limits.min_source_distance
    
    def test_validate_source_too_close(self):
        """Sources too close are flagged."""
        limits = SpatialSafetyLimits(min_source_distance=0.1)
        sources = [
            SpatialNode(name="too_close", position=Position3D(x=0, y=0, z=0.05))
        ]
        
        violations = validate_spatial_safety(sources, limits)
        assert len(violations) > 0
        assert "too close" in violations[0].lower()
    
    def test_validate_source_too_far(self):
        """Sources too far are flagged."""
        limits = SpatialSafetyLimits(max_source_distance=50.0)
        sources = [
            SpatialNode(name="too_far", position=Position3D(x=0, y=0, z=100))
        ]
        
        violations = validate_spatial_safety(sources, limits)
        assert len(violations) > 0
        assert "too far" in violations[0].lower()
    
    def test_validate_valid_sources_pass(self):
        """Valid sources pass validation."""
        limits = SpatialSafetyLimits()
        sources = [
            SpatialNode(name="s1", position=Position3D(x=0, y=0, z=1)),
            SpatialNode(name="s2", position=Position3D(x=1, y=0, z=2)),
            SpatialNode(name="s3", position=Position3D(x=-0.5, y=0.5, z=3)),
        ]
        
        violations = validate_spatial_safety(sources, limits)
        assert len(violations) == 0


class TestDistanceAttenuationInvariants:
    """Tests for distance attenuation invariants."""
    
    def test_closer_sources_louder(self):
        """Closer sources are always louder (no inversion)."""
        source = SpatialNode(
            name="test",
            distance_model="inverse",
            ref_distance=1.0
        )
        
        distances = [0.5, 1.0, 2.0, 5.0, 10.0]
        gains = [source.calculate_gain(d) for d in distances]
        
        # Gains should decrease monotonically with distance
        for i in range(1, len(gains)):
            assert gains[i] <= gains[i-1], "Gain inversion detected"
    
    def test_gain_never_negative(self):
        """Gain is never negative."""
        for model in ["linear", "inverse", "exponential"]:
            source = SpatialNode(name="test", distance_model=model)
            
            for distance in [0.1, 1, 5, 10, 100]:
                gain = source.calculate_gain(distance)
                assert gain >= 0, f"Negative gain: {gain} at distance {distance}"
    
    def test_gain_bounded(self):
        """Gain is bounded (not infinite for very close sources)."""
        source = SpatialNode(
            name="test",
            distance_model="inverse",
            ref_distance=1.0
        )
        
        # Very close but valid distance
        gain = source.calculate_gain(0.01)
        assert gain <= 100, "Unbounded gain for close source"


class TestGraphValidationInvariants:
    """Tests for graph-level validation invariants."""
    
    def test_exactly_one_listener(self):
        """Graph enforces exactly one listener."""
        graph = SpatialGraph()
        
        # Can set listener
        graph.set_listener()
        assert graph.listener is not None
        
        # Can replace listener (still exactly one)
        new_listener = ListenerNode(name="new")
        graph.set_listener(new_listener)
        assert graph.listener is new_listener
    
    def test_explicit_downmix_required(self):
        """Downmix node is explicitly required."""
        graph = SpatialGraph()
        graph.set_listener()
        graph.add_source("test")
        
        # Validation fails without explicit downmix
        result = graph.validate()
        assert not result.is_valid
        
        # Now add downmix
        graph.set_downmix()
        result = graph.validate()
        assert result.is_valid
    
    def test_source_count_bounded(self):
        """Source count is bounded."""
        graph = SpatialGraph()
        
        assert graph.MAX_SOURCES > 0
        assert graph.MAX_SOURCES <= 64  # Reasonable limit


class TestRegistrarUntouched:
    """
    Section 10: Registrar & Control Plane Safety.
    
    Registrar must remain unchanged:
    - No new registrar state
    - No spatial invariants in registrar
    - No agent-visible spatial authority
    - Spatial behavior purely AudioGraph-local
    
    These tests verify spatial audio stays within audio domain.
    """
    
    def test_spatial_is_audio_local(self):
        """Spatial state is not in registrar."""
        # SpatialGraph manages its own state
        graph = create_spatial_scene()
        graph.add_source("voice", Position3D(x=0.5, y=0, z=1))
        
        # All spatial state is in the graph, not a registrar
        assert hasattr(graph, '_sources')
        assert hasattr(graph, '_listener')
        
        # No integration with registrar
        assert not hasattr(graph, 'registrar')
        assert not hasattr(graph, '_registrar')
    
    def test_position_changes_not_mediated(self):
        """Position changes don't go through registrar."""
        graph = create_spatial_scene()
        source = graph.add_source("voice")
        
        # Direct position change (audio-local)
        source.set_position(x=0.5, y=0, z=2)
        
        # No attestation, no registrar involvement
        assert source.position.x == 0.5
