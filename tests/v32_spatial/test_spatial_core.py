"""
v3.2 Spatial Core Tests — Golden spatial audio tests (left/right).

Tests the fundamental spatial positioning and rendering.
Section 8: Required Test Classes.
"""

import math
import pytest

from voice_soundboard.v3.spatial import (
    Position3D,
    Orientation3D,
    SpatialNode,
    ListenerNode,
    SpatialDownmixNode,
    SpatialGraph,
    HRTFEngine,
    HRTFParameters,
    HRTFProfile,
    create_spatial_scene,
)


class TestPosition3D:
    """Tests for 3D position coordinates."""
    
    def test_default_position(self):
        """Default position is center-front."""
        pos = Position3D()
        assert pos.x == 0.0
        assert pos.y == 0.0
        assert pos.z == 1.0
    
    def test_position_creation(self):
        """Positions can be created with explicit values."""
        pos = Position3D(x=0.5, y=-0.2, z=2.0)
        assert pos.x == 0.5
        assert pos.y == -0.2
        assert pos.z == 2.0
    
    def test_position_distance_must_be_positive(self):
        """Distance (z) must be positive."""
        with pytest.raises(ValueError):
            Position3D(x=0, y=0, z=0)
        
        with pytest.raises(ValueError):
            Position3D(x=0, y=0, z=-1)
    
    def test_position_is_frozen(self):
        """Position is immutable (frozen dataclass)."""
        pos = Position3D(x=1, y=0, z=1)
        with pytest.raises(AttributeError):
            pos.x = 2  # Should fail - frozen
    
    def test_spherical_conversion_front(self):
        """Position from front azimuth."""
        pos = Position3D.from_spherical(azimuth=0, elevation=0, distance=2.0)
        assert pos.z == 2.0
        assert abs(pos.x) < 0.01  # Near zero
        assert abs(pos.y) < 0.01  # Near zero
    
    def test_spherical_conversion_right(self):
        """Position from right side (azimuth=90)."""
        pos = Position3D.from_spherical(azimuth=90, elevation=0, distance=1.0)
        assert pos.x > 0.9  # Should be to the right
        assert abs(pos.y) < 0.01  # Near zero
    
    def test_spherical_conversion_left(self):
        """Position from left side (azimuth=-90)."""
        pos = Position3D.from_spherical(azimuth=-90, elevation=0, distance=1.0)
        assert pos.x < -0.9  # Should be to the left
        assert abs(pos.y) < 0.01  # Near zero
    
    def test_spherical_invalid_distance(self):
        """Spherical conversion rejects invalid distance."""
        with pytest.raises(ValueError):
            Position3D.from_spherical(azimuth=0, elevation=0, distance=-1)
    
    def test_distance_calculation(self):
        """Distance between two positions."""
        p1 = Position3D(x=0, y=0, z=1)
        p2 = Position3D(x=1, y=0, z=1)
        
        # Horizontal distance of 1
        assert abs(p1.distance_to(p2) - 1.0) < 0.01
    
    def test_interpolation(self):
        """Linear interpolation between positions."""
        start = Position3D(x=0, y=0, z=1)
        end = Position3D(x=1, y=0, z=2)
        
        # Midpoint
        mid = start.interpolate(end, 0.5)
        assert abs(mid.x - 0.5) < 0.01
        assert abs(mid.z - 1.5) < 0.01
        
        # Start
        at_start = start.interpolate(end, 0.0)
        assert at_start.x == start.x
        
        # End
        at_end = start.interpolate(end, 1.0)
        assert at_end.x == end.x


class TestOrientation3D:
    """Tests for 3D orientation (head tracking)."""
    
    def test_default_orientation(self):
        """Default orientation is facing forward."""
        orient = Orientation3D()
        assert orient.yaw == 0.0
        assert orient.pitch == 0.0
        assert orient.roll == 0.0
    
    def test_facing_direction(self):
        """Create orientation facing a direction."""
        target = Position3D(x=1, y=0, z=1)  # Front-right
        orient = Orientation3D.facing(target)
        assert orient.yaw > 0  # Should be turned right
    
    def test_rotate_position_no_rotation(self):
        """No rotation leaves position unchanged."""
        orient = Orientation3D(yaw=0)
        pos = Position3D(x=0.5, y=0, z=1)
        
        rotated = orient.rotate_position(pos)
        assert abs(rotated.x - pos.x) < 0.01
        assert abs(rotated.z - pos.z) < 0.01
    
    def test_rotate_position_yaw_90(self):
        """Yaw rotation transforms positions."""
        orient = Orientation3D(yaw=90)  # Looking right
        pos = Position3D(x=0, y=0, z=1)  # In front (world)
        
        rotated = orient.rotate_position(pos)
        # Rotation is applied: z maps to x axis
        assert abs(rotated.x) > 0.5  # Significant x component
        assert abs(rotated.z) < 0.5  # Reduced z component


class TestSpatialNode:
    """Tests for spatial audio source nodes."""
    
    def test_create_source(self):
        """Create a spatial source."""
        source = SpatialNode(name="voice")
        assert source.name == "voice"
        assert source.position.z == 1.0  # Default distance
    
    def test_set_position_fluent(self):
        """Fluent API for position setting."""
        source = SpatialNode(name="voice")
        result = source.set_position(x=0.5, y=0, z=2.0)
        
        assert result is source  # Returns self
        assert source.position.x == 0.5
        assert source.position.z == 2.0
    
    def test_distance_attenuation_linear(self):
        """Linear distance model."""
        source = SpatialNode(
            name="test",
            distance_model="linear",
            ref_distance=1.0,
            max_distance=10.0,
        )
        
        # At reference distance, gain = 1.0
        assert source.calculate_gain(1.0) == 1.0
        
        # At max distance, gain = 0.0
        assert source.calculate_gain(10.0) == pytest.approx(0.0, abs=0.01)
        
        # Beyond max, stays at 0
        assert source.calculate_gain(15.0) == 0.0
    
    def test_distance_attenuation_inverse(self):
        """Inverse distance model (default)."""
        source = SpatialNode(
            name="test",
            distance_model="inverse",
            ref_distance=1.0,
        )
        
        # At reference distance
        assert source.calculate_gain(1.0) == 1.0
        
        # At 2x distance, gain is halved: 1.0 / 2.0 = 0.5
        gain_2x = source.calculate_gain(2.0)
        assert gain_2x == pytest.approx(0.5, abs=0.01)
    
    def test_source_has_unique_id(self):
        """Each source has a unique ID."""
        s1 = SpatialNode(name="a", position=Position3D(x=0, y=0, z=1))
        s2 = SpatialNode(name="b", position=Position3D(x=1, y=0, z=1))
        
        assert s1.id != s2.id


class TestListenerNode:
    """Tests for the listener node."""
    
    def test_create_listener(self):
        """Create a listener."""
        listener = ListenerNode()
        assert listener.name == "listener"
        assert listener.orientation.yaw == 0.0
    
    def test_set_orientation_fluent(self):
        """Fluent API for orientation."""
        listener = ListenerNode()
        result = listener.set_orientation(yaw=45)
        
        assert result is listener  # Returns self
        assert listener.orientation.yaw == 45
    
    def test_itd_calculation_center(self):
        """ITD is zero for center source."""
        listener = ListenerNode()
        center = Position3D(x=0, y=0, z=1)  # Directly in front
        
        itd = listener.calculate_itd(center)
        assert abs(itd) < 0.0001  # Near zero
    
    def test_itd_calculation_right(self):
        """ITD is positive for right source."""
        listener = ListenerNode()
        right = Position3D(x=1, y=0, z=1)  # To the right
        
        itd = listener.calculate_itd(right)
        assert itd > 0  # Right ear leads
    
    def test_ild_calculation_center(self):
        """ILD is equal for center source."""
        listener = ListenerNode()
        center = Position3D(x=0, y=0, z=1)  # Directly in front
        
        left_gain, right_gain = listener.calculate_ild(center)
        assert abs(left_gain - right_gain) < 0.1  # Nearly equal


class TestSpatialDownmixNode:
    """Tests for spatial-to-stereo downmix."""
    
    def test_create_downmix(self):
        """Create downmix node."""
        downmix = SpatialDownmixNode()
        assert downmix.limiter_enabled is True
    
    def test_limiter_clips_loud_signal(self):
        """Limiter clips signals above threshold."""
        downmix = SpatialDownmixNode(
            limiter_threshold_db=-1.0,
            limiter_enabled=True
        )
        
        # Loud signal
        loud = 1.5
        left, right = downmix.apply_limiter(loud, loud)
        
        # Should be limited
        assert left < loud
        assert right < loud
    
    def test_limiter_passes_quiet_signal(self):
        """Limiter passes signals below threshold."""
        downmix = SpatialDownmixNode(
            limiter_threshold_db=-1.0,
            output_gain=1.0
        )
        
        quiet = 0.5
        left, right = downmix.apply_limiter(quiet, quiet)
        
        assert left == quiet
        assert right == quiet


class TestSpatialGraph:
    """Tests for the spatial graph container."""
    
    def test_create_graph(self):
        """Create spatial graph."""
        graph = SpatialGraph(name="scene")
        assert graph.name == "scene"
        assert graph.listener is None
        assert graph.source_count == 0
    
    def test_set_listener(self):
        """Set listener node."""
        graph = SpatialGraph()
        listener = graph.set_listener()
        
        assert graph.listener is listener
    
    def test_add_source(self):
        """Add spatial sources."""
        graph = SpatialGraph()
        source = graph.add_source("voice", Position3D(x=0.5, y=0, z=1))
        
        assert graph.source_count == 1
        assert graph.get_source("voice") is source
    
    def test_duplicate_source_name_fails(self):
        """Cannot add duplicate source names."""
        graph = SpatialGraph()
        graph.add_source("voice")
        
        with pytest.raises(ValueError):
            graph.add_source("voice")  # Duplicate
    
    def test_max_sources_enforced(self):
        """Maximum source limit is enforced."""
        graph = SpatialGraph()
        
        # Add MAX_SOURCES
        for i in range(graph.MAX_SOURCES):
            graph.add_source(f"source_{i}")
        
        # One more should fail
        with pytest.raises(ValueError):
            graph.add_source("one_too_many")
    
    def test_set_downmix(self):
        """Set downmix node."""
        graph = SpatialGraph()
        downmix = graph.set_downmix()
        
        assert graph.downmix is downmix
    
    def test_validation_requires_listener(self):
        """Validation fails without listener."""
        graph = SpatialGraph()
        graph.set_downmix()
        
        result = graph.validate()
        assert not result.is_valid
        assert any("listener" in err.lower() for err in result.errors)
    
    def test_validation_requires_downmix(self):
        """Validation fails without downmix."""
        graph = SpatialGraph()
        graph.set_listener()
        
        result = graph.validate()
        assert not result.is_valid
        assert any("downmix" in err.lower() for err in result.errors)
    
    def test_validation_passes_complete_graph(self):
        """Complete graph passes validation."""
        graph = create_spatial_scene()
        graph.add_source("voice", Position3D(x=0, y=0, z=1))
        
        result = graph.validate()
        assert result.is_valid


class TestCreateSpatialScene:
    """Tests for the ergonomic scene creation."""
    
    def test_creates_complete_scene(self):
        """create_spatial_scene creates a valid scene."""
        scene = create_spatial_scene(name="my_scene")
        
        assert scene.name == "my_scene"
        assert scene.listener is not None
        assert scene.downmix is not None
        
        # Should pass validation (empty but complete)
        result = scene.validate()
        assert result.is_valid or (not result.errors)  # Warnings OK
    
    def test_can_add_sources_to_scene(self):
        """Adding sources to created scene."""
        scene = create_spatial_scene()
        
        voice = scene.add_source("voice", Position3D(x=-0.5, y=0, z=1.5))
        music = scene.add_source("music", Position3D(x=0, y=0, z=3))
        
        assert scene.source_count == 2


class TestGoldenSpatialPositioning:
    """Golden tests for left/right positioning (Section 8)."""
    
    def test_left_source_has_louder_left_channel(self):
        """Source on left produces louder left channel."""
        scene = create_spatial_scene()
        source = scene.add_source("test", Position3D(x=-1, y=0, z=1))  # Full left
        
        left_gain, right_gain = scene.listener.calculate_ild(source.position)
        assert left_gain > right_gain
    
    def test_right_source_has_louder_right_channel(self):
        """Source on right produces louder right channel."""
        scene = create_spatial_scene()
        source = scene.add_source("test", Position3D(x=1, y=0, z=1))  # Full right
        
        left_gain, right_gain = scene.listener.calculate_ild(source.position)
        assert right_gain > left_gain
    
    def test_center_source_has_equal_channels(self):
        """Center source produces equal channels."""
        scene = create_spatial_scene()
        source = scene.add_source("test", Position3D(x=0, y=0, z=1))  # Center
        
        left_gain, right_gain = scene.listener.calculate_ild(source.position)
        assert abs(left_gain - right_gain) < 0.1
    
    def test_distant_source_is_quieter(self):
        """Distant source has lower gain."""
        source_near = SpatialNode(name="near", position=Position3D(z=1))
        source_far = SpatialNode(name="far", position=Position3D(z=5))
        
        gain_near = source_near.calculate_gain(source_near.position.z)
        gain_far = source_far.calculate_gain(source_far.position.z)
        
        assert gain_near > gain_far


class TestHRTFEngine:
    """Tests for the HRTF rendering engine."""
    
    def test_create_engine(self):
        """Create HRTF engine."""
        engine = HRTFEngine()
        assert engine.params.profile == HRTFProfile.DEFAULT
    
    def test_invalid_params_rejected(self):
        """Invalid parameters are rejected."""
        params = HRTFParameters(filter_length=100)  # Invalid - must be 64,128,256,512
        
        with pytest.raises(ValueError):
            HRTFEngine(params)
    
    def test_process_single_source(self):
        """Process a single source."""
        engine = HRTFEngine()
        source = SpatialNode(name="test", position=Position3D(x=0.5, y=0, z=1))
        listener = ListenerNode()
        
        # Simple mono input
        input_samples = [0.5] * 100
        
        left, right = engine.process_source(source, listener, input_samples)
        
        # Output same length as input (Section 3: no duration change)
        assert len(left) == len(input_samples)
        assert len(right) == len(input_samples)
    
    def test_process_graph(self):
        """Process multiple sources."""
        engine = HRTFEngine()
        downmix = SpatialDownmixNode()
        listener = ListenerNode()
        
        sources = [
            (SpatialNode(name="s1", position=Position3D(x=-0.5, y=0, z=1)), [0.3] * 50),
            (SpatialNode(name="s2", position=Position3D(x=0.5, y=0, z=1)), [0.3] * 50),
        ]
        
        left, right = engine.process_graph(sources, listener, downmix)
        
        assert len(left) == 50
        assert len(right) == 50
    
    def test_output_not_clipped(self):
        """Output respects limiter (Section 4)."""
        engine = HRTFEngine()
        downmix = SpatialDownmixNode(limiter_enabled=True)
        listener = ListenerNode()
        
        # Loud sources
        sources = [
            (SpatialNode(name="s1", position=Position3D(x=-0.5, y=0, z=0.5)), [0.9] * 50),
            (SpatialNode(name="s2", position=Position3D(x=0.5, y=0, z=0.5)), [0.9] * 50),
        ]
        
        left, right = engine.process_graph(sources, listener, downmix)
        
        # Check limiter is applied
        for l, r in zip(left, right):
            assert abs(l) < 1.0
            assert abs(r) < 1.0
