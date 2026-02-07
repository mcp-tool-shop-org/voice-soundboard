"""
v3.2 Spatial Movement Tests — Tests for movement automation system.

Section 6: Movement & Automation Rules

Note: Movement paths use time_ms (milliseconds) for timing.
"""

import pytest
import math

from voice_soundboard.v3.spatial import (
    Position3D,
    SpatialNode,
    InterpolationMode,
    MovementKeyframe,
    MovementPath,
    SpatialGraph,
    create_spatial_scene,
)


class TestInterpolationModes:
    """Tests for interpolation mode enum."""
    
    def test_interpolation_modes_exist(self):
        """All available interpolation modes are defined."""
        assert InterpolationMode.LINEAR is not None
        assert InterpolationMode.SMOOTHSTEP is not None
        assert InterpolationMode.EASE_IN is not None
        assert InterpolationMode.EASE_OUT is not None


class TestMovementKeyframe:
    """Tests for MovementKeyframe dataclass."""
    
    def test_keyframe_construction(self):
        """Keyframes store position and time in milliseconds."""
        kf = MovementKeyframe(
            time_ms=1500.0,  # 1.5 seconds in ms
            position=Position3D(x=0.5, y=0.2, z=2.0)
        )
        
        assert kf.time_ms == 1500.0
        assert kf.position.x == 0.5
        assert kf.position.y == 0.2
        assert kf.position.z == 2.0
    
    def test_keyframe_with_interpolation(self):
        """Keyframes support custom interpolation mode."""
        kf = MovementKeyframe(
            time_ms=0.0,
            position=Position3D(x=0, y=0, z=1),
            interpolation=InterpolationMode.SMOOTHSTEP
        )
        
        assert kf.interpolation == InterpolationMode.SMOOTHSTEP
    
    def test_keyframe_negative_time_fails(self):
        """Negative time is rejected."""
        with pytest.raises(ValueError):
            MovementKeyframe(
                time_ms=-100.0,
                position=Position3D(x=0, y=0, z=1)
            )


class TestMovementPath:
    """Tests for MovementPath class."""
    
    def test_path_construction(self):
        """Paths are constructed from keyframes."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0.0, position=Position3D(x=-1, y=0, z=1)),
            MovementKeyframe(time_ms=2000.0, position=Position3D(x=1, y=0, z=1)),
        ])
        
        assert len(path.keyframes) == 2
    
    def test_path_add_keyframe(self):
        """Keyframes can be added with chaining."""
        path = MovementPath()
        path.add_keyframe(0.0, Position3D(x=-1, y=0, z=1)) \
            .add_keyframe(1000.0, Position3D(x=1, y=0, z=1))
        
        assert len(path.keyframes) == 2
    
    def test_path_linear_interpolation(self):
        """Linear interpolation produces midpoint at t=500ms."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0.0, position=Position3D(x=-1, y=0, z=1)),
            MovementKeyframe(time_ms=1000.0, position=Position3D(x=1, y=0, z=1)),
        ])
        
        mid = path.position_at(500.0)  # time_ms
        
        assert mid.x == pytest.approx(0.0, abs=0.01)
        assert mid.y == pytest.approx(0.0, abs=0.01)
        assert mid.z == pytest.approx(1.0, abs=0.01)
    
    def test_path_smoothstep_interpolation(self):
        """Smoothstep interpolation produces smoother curve."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0.0, position=Position3D(x=-1, y=0, z=1)),
            MovementKeyframe(time_ms=1000.0, position=Position3D(x=1, y=0, z=1), 
                           interpolation=InterpolationMode.SMOOTHSTEP),
        ])
        
        # At t=500ms, smoothstep gives 0.0 (same as linear at midpoint)
        pos = path.position_at(500.0)
        assert pos.x == pytest.approx(0.0, abs=0.1)
    
    def test_path_before_first_keyframe(self):
        """Position before first keyframe returns first position."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=1000.0, position=Position3D(x=0, y=0, z=1)),
        ])
        
        pos = path.position_at(0.0)
        assert pos.x == 0.0
    
    def test_path_after_last_keyframe(self):
        """Position after last keyframe returns last position."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0.0, position=Position3D(x=-1, y=0, z=1)),
            MovementKeyframe(time_ms=1000.0, position=Position3D(x=1, y=0, z=1)),
        ])
        
        pos = path.position_at(5000.0)
        assert pos.x == 1.0  # Held at end
    
    def test_multi_segment_path(self):
        """Path with multiple segments interpolates correctly."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0.0, position=Position3D(x=-1, y=0, z=1)),
            MovementKeyframe(time_ms=1000.0, position=Position3D(x=0, y=0, z=1)),
            MovementKeyframe(time_ms=2000.0, position=Position3D(x=1, y=0, z=1)),
        ])
        
        # First segment
        assert path.position_at(500.0).x == pytest.approx(-0.5, abs=0.01)
        
        # Second segment
        assert path.position_at(1500.0).x == pytest.approx(0.5, abs=0.01)
    
    def test_empty_path_returns_default(self):
        """Empty path returns default position."""
        path = MovementPath()
        pos = path.position_at(500.0)
        
        assert pos.z == 1.0  # Default z


class TestMovementValidation:
    """
    Section 6.3: Movement validation.
    
    Teleportation and excessive speeds are detected via validate().
    """
    
    def test_validate_valid_path(self):
        """Valid path passes validation."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0.0, position=Position3D(x=-1, y=0, z=1)),
            MovementKeyframe(time_ms=2000.0, position=Position3D(x=1, y=0, z=1)),
        ])
        
        errors = path.validate()
        assert len(errors) == 0
    
    def test_validate_excessive_speed(self):
        """Excessive speed is flagged."""
        path = MovementPath(
            max_speed=1.0,  # 1 m/s max
            keyframes=[
                MovementKeyframe(time_ms=0.0, position=Position3D(x=0, y=0, z=1)),
                MovementKeyframe(time_ms=100.0, position=Position3D(x=10, y=0, z=1)),  # 100 m/s!
            ]
        )
        
        errors = path.validate()
        assert len(errors) > 0
        assert any("speed" in e.lower() for e in errors)
    
    def test_validate_teleportation(self):
        """Large instant movement (teleportation) is flagged."""
        path = MovementPath(
            teleport_threshold=2.0,  # >2m is teleportation
            crossfade_duration_ms=50.0,
            keyframes=[
                MovementKeyframe(time_ms=0.0, position=Position3D(x=-5, y=0, z=1)),
                MovementKeyframe(time_ms=10.0, position=Position3D(x=5, y=0, z=1)),  # 10m in 10ms
            ]
        )
        
        errors = path.validate()
        assert len(errors) > 0
        assert any("teleport" in e.lower() for e in errors)
    
    def test_smooth_movement_passes(self):
        """Smooth movement passes validation."""
        path = MovementPath(
            max_speed=10.0,
            keyframes=[
                MovementKeyframe(time_ms=0.0, position=Position3D(x=-1, y=0, z=1)),
                MovementKeyframe(time_ms=2000.0, position=Position3D(x=1, y=0, z=1)),  # 1 m/s
            ]
        )
        
        errors = path.validate()
        assert len(errors) == 0


class TestGraphMovement:
    """Tests for SpatialGraph movement management."""
    
    def test_add_movement_to_source(self):
        """Movement paths are added via graph."""
        graph = create_spatial_scene()
        source = graph.add_source("moving")
        
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0.0, position=Position3D(x=-1, y=0, z=1)),
            MovementKeyframe(time_ms=2000.0, position=Position3D(x=1, y=0, z=1)),
        ])
        
        graph.add_movement("moving", path)
        
        assert graph.get_movement("moving") is not None
    
    def test_add_movement_invalid_source(self):
        """Adding movement to nonexistent source fails."""
        graph = create_spatial_scene()
        
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0.0, position=Position3D(x=0, y=0, z=1)),
        ])
        
        with pytest.raises(ValueError):
            graph.add_movement("nonexistent", path)
    
    def test_movement_included_in_validation(self):
        """Graph validation includes movement path validation."""
        graph = create_spatial_scene()
        graph.add_source("mover")
        
        # Add invalid movement (too fast)
        bad_path = MovementPath(
            max_speed=1.0,
            keyframes=[
                MovementKeyframe(time_ms=0.0, position=Position3D(x=0, y=0, z=1)),
                MovementKeyframe(time_ms=10.0, position=Position3D(x=100, y=0, z=1)),
            ]
        )
        graph.add_movement("mover", bad_path)
        
        result = graph.validate()
        assert not result.is_valid


class TestCircularMovement:
    """Tests for circular movement patterns."""
    
    def test_orbit_path(self):
        """Movement can describe orbital motion."""
        # Create circular path with 8 keyframes
        keyframes = []
        for i in range(9):  # 0 to 2π
            t = i / 8.0
            angle = t * 2 * math.pi
            keyframes.append(MovementKeyframe(
                time_ms=t * 4000.0,  # 4 second orbit in ms
                position=Position3D(
                    x=math.cos(angle),
                    y=0,
                    z=1 + abs(math.sin(angle))  # Keep z positive
                )
            ))
        
        path = MovementPath(keyframes=keyframes)
        
        # At t=0, x=1
        assert path.position_at(0.0).x == pytest.approx(1.0, abs=0.01)
        
        # At t=2000ms, x≈-1 (opposite side)
        assert path.position_at(2000.0).x == pytest.approx(-1.0, abs=0.1)


class TestZCoordinateMovement:
    """Tests for z-coordinate (distance) movement."""
    
    def test_approach_movement(self):
        """Source can approach listener."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0.0, position=Position3D(x=0, y=0, z=5)),
            MovementKeyframe(time_ms=2000.0, position=Position3D(x=0, y=0, z=1)),
        ])
        
        # Gets closer over time
        assert path.position_at(0.0).z == 5.0
        assert path.position_at(1000.0).z == pytest.approx(3.0, abs=0.01)
        assert path.position_at(2000.0).z == 1.0
    
    def test_retreat_movement(self):
        """Source can retreat from listener."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0.0, position=Position3D(x=0, y=0, z=1)),
            MovementKeyframe(time_ms=2000.0, position=Position3D(x=0, y=0, z=10)),
        ])
        
        # Gets further over time
        assert path.position_at(2000.0).z == 10.0
    
    def test_z_stays_positive(self):
        """Z coordinate stays positive during movement."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0.0, position=Position3D(x=0, y=0, z=1)),
            MovementKeyframe(time_ms=1000.0, position=Position3D(x=0, y=0, z=0.1)),  # Very close
        ])
        
        # Even interpolated values should stay positive
        for t in [0.0, 250.0, 500.0, 750.0, 1000.0]:
            assert path.position_at(t).z > 0


class TestMovementPathChaining:
    """Tests for fluent API chaining."""
    
    def test_add_keyframe_returns_self(self):
        """add_keyframe returns self for chaining."""
        path = MovementPath()
        result = path.add_keyframe(0.0, Position3D(x=0, y=0, z=1))
        
        assert result is path
    
    def test_full_chain(self):
        """Full path can be built with chaining."""
        path = (MovementPath()
            .add_keyframe(0.0, Position3D(x=-1, y=0, z=1))
            .add_keyframe(500.0, Position3D(x=0, y=0, z=2))
            .add_keyframe(1000.0, Position3D(x=1, y=0, z=1)))
        
        assert len(path.keyframes) == 3
        assert path.position_at(500.0).x == pytest.approx(0.0, abs=0.1)
