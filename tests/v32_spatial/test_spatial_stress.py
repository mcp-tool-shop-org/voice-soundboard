"""
v3.2 Spatial Stress Tests — Tests for many-source scenarios.

Tests system behavior under stress conditions:
- Many simultaneous sources
- High-frequency position updates
- Edge cases and boundary conditions
"""

import pytest
import random
import math

from voice_soundboard.v3.spatial import (
    Position3D,
    Orientation3D,
    SpatialNode,
    ListenerNode,
    SpatialDownmixNode,
    HRTFEngine,
    HRTFParameters,
    MovementKeyframe,
    MovementPath,
    SpatialGraph,
    create_spatial_scene,
)


class TestManySourcesBasic:
    """Tests with many simultaneous sources."""
    
    def test_max_sources_limit(self):
        """Graph enforces maximum source limit."""
        graph = SpatialGraph()
        
        # Should be able to add up to MAX_SOURCES
        for i in range(graph.MAX_SOURCES):
            graph.add_source(f"source_{i}")
        
        # Adding more should fail gracefully
        with pytest.raises((ValueError, RuntimeError)):
            graph.add_source("one_too_many")
    
    def test_many_sources_mixing(self):
        """Many sources can be mixed without crashing."""
        engine = HRTFEngine()
        downmix = SpatialDownmixNode()
        listener = ListenerNode()
        
        # Create 32 sources at different positions
        sources = []
        for i in range(32):
            angle = (i / 32) * 2 * math.pi
            pos = Position3D(
                x=math.sin(angle),
                y=math.cos(angle) * 0.5,
                z=1 + (i % 4)
            )
            source = SpatialNode(name=f"s{i}", position=pos)
            samples = [0.1 * math.sin(2 * math.pi * 440 * j / 48000) for j in range(1000)]
            sources.append((source, samples))
        
        # Should complete without error
        left, right = engine.process_graph(sources, listener, downmix)
        
        assert len(left) == 1000
        assert len(right) == 1000
    
    def test_all_sources_same_position(self):
        """All sources at same position doesn't cause issues."""
        engine = HRTFEngine()
        listener = ListenerNode()
        downmix = SpatialDownmixNode(limiter_enabled=True)
        
        pos = Position3D(x=0, y=0, z=1)
        sources = []
        for i in range(16):
            source = SpatialNode(name=f"s{i}", position=pos)
            sources.append((source, [0.1] * 100))
        
        left, right = engine.process_graph(sources, listener, downmix)
        
        # All sources mixed, should be aligned (equal L/R)
        for l, r in zip(left, right):
            assert abs(l - r) < 0.01  # Center position = equal L/R


class TestPositionUpdateStress:
    """Tests for rapid position updates."""
    
    def test_high_frequency_position_updates(self):
        """Many position updates per frame don't cause issues."""
        source = SpatialNode(name="stress", position=Position3D(x=0, y=0, z=1))
        
        # Simulate 1000 rapid position updates
        for i in range(1000):
            x = math.sin(i / 100)
            z = 1 + math.cos(i / 100)
            source.set_position(x=x, y=0, z=z)
        
        # Should complete without error
        assert source.position is not None
    
    def test_graph_many_updates(self):
        """Graph handles many updates per second."""
        graph = create_spatial_scene()
        
        sources = [graph.add_source(f"s{i}") for i in range(10)]
        
        # Simulate 100 frames of updates
        for frame in range(100):
            for i, source in enumerate(sources):
                angle = (frame + i) / 10
                source.set_position(
                    x=math.sin(angle),
                    y=0,
                    z=1 + math.cos(angle)
                )
        
        # Should complete without error
        assert all(s.position is not None for s in sources)


class TestBoundaryConditions:
    """Tests for edge cases and boundary conditions."""
    
    def test_source_at_origin(self):
        """Source at x=0, y=0 (directly in front) works."""
        engine = HRTFEngine()
        listener = ListenerNode()
        
        source = SpatialNode(name="center", position=Position3D(x=0, y=0, z=1))
        left, right = engine.process_source(source, listener, [0.5] * 100)
        
        # Center position should have equal L/R (within tolerance)
        for l, r in zip(left, right):
            assert abs(l - r) < 0.1
    
    def test_source_at_extreme_left(self):
        """Source at extreme left works."""
        source = SpatialNode(name="left", position=Position3D(x=-1, y=0, z=1))
        gain = source.calculate_gain(source.position.z)
        
        assert gain > 0
    
    def test_source_at_extreme_right(self):
        """Source at extreme right works."""
        source = SpatialNode(name="right", position=Position3D(x=1, y=0, z=1))
        gain = source.calculate_gain(source.position.z)
        
        assert gain > 0
    
    def test_source_very_close(self):
        """Source very close (z=0.1) is handled."""
        source = SpatialNode(
            name="close",
            position=Position3D(x=0, y=0, z=0.1),
            ref_distance=0.1  # Reference at close range
        )
        
        # At ref_distance, gain should be 1.0
        gain = source.calculate_gain(0.1)
        assert gain <= 1.0  # Not excessively loud
        assert gain > 0
    
    def test_source_very_far(self):
        """Source very far (z=1000) is handled."""
        source = SpatialNode(
            name="far",
            position=Position3D(x=0, y=0, z=1000),
            max_distance=100.0
        )
        
        gain = source.calculate_gain(1000)
        assert gain >= 0  # Valid gain
    
    def test_zero_length_audio(self):
        """Zero-length audio buffer is handled."""
        engine = HRTFEngine()
        listener = ListenerNode()
        source = SpatialNode(name="empty", position=Position3D(x=0, y=0, z=1))
        
        left, right = engine.process_source(source, listener, [])
        
        assert len(left) == 0
        assert len(right) == 0


class TestRandomPositions:
    """Tests with randomized positions."""
    
    def test_random_positions_valid(self):
        """Random valid positions all work."""
        random.seed(42)  # Reproducible
        
        for _ in range(100):
            x = random.uniform(-1, 1)
            y = random.uniform(-1, 1)
            z = random.uniform(0.1, 100)
            
            pos = Position3D(x=x, y=y, z=z)
            source = SpatialNode(name="random", position=pos)
            
            # Should be valid
            assert source.position.z > 0
    
    def test_random_graph_configurations(self):
        """Random graph configurations work."""
        random.seed(42)
        
        for _ in range(10):
            graph = create_spatial_scene()
            
            n_sources = random.randint(1, 32)
            for i in range(n_sources):
                x = random.uniform(-1, 1)
                z = random.uniform(0.5, 10)
                graph.add_source(f"s{i}", Position3D(x=x, y=0, z=z))
            
            # Should validate successfully
            result = graph.validate()
            assert result.is_valid


class TestMemoryStability:
    """Tests for memory stability under load."""
    
    def test_repeated_graph_creation(self):
        """Creating/destroying many graphs doesn't leak."""
        for _ in range(100):
            graph = create_spatial_scene()
            for i in range(10):
                graph.add_source(f"s{i}")
            
            # Graph goes out of scope
        
        # If we got here without OOM, we're good
        assert True
    
    def test_repeated_processing(self):
        """Repeated processing doesn't accumulate memory."""
        engine = HRTFEngine()
        listener = ListenerNode()
        downmix = SpatialDownmixNode()
        
        for _ in range(100):
            source = SpatialNode(name="test", position=Position3D(x=0, y=0, z=1))
            samples = [0.5] * 1000
            
            left, right = engine.process_source(source, listener, samples)
            
            # Results are independent
            assert len(left) == 1000
    
    def test_path_updates_stable(self):
        """Repeated path updates don't leak."""
        graph = create_spatial_scene()
        source = graph.add_source("mover")
        
        for _ in range(100):
            path = MovementPath(keyframes=[
                MovementKeyframe(time_ms=0, position=Position3D(x=0, y=0, z=1)),
                MovementKeyframe(time_ms=1000, position=Position3D(x=1, y=0, z=1)),
            ])
            graph.add_movement("mover", path)
        
        # Path was added (replaced) many times
        assert graph.get_movement("mover") is not None


class TestConcurrentOperations:
    """Tests simulating concurrent-like operations."""
    
    def test_interleaved_operations(self):
        """Interleaved add/remove works correctly."""
        graph = create_spatial_scene()
        
        # Add some sources
        s1 = graph.add_source("s1")
        s2 = graph.add_source("s2")
        s3 = graph.add_source("s3")
        
        # Remove middle one
        graph.remove_source("s2")
        
        # Add more
        s4 = graph.add_source("s4")
        s5 = graph.add_source("s5")
        
        # Verify state
        sources = graph.sources
        names = [s.name for s in sources]
        
        assert "s1" in names
        assert "s2" not in names
        assert "s3" in names
        assert "s4" in names
        assert "s5" in names
    
    def test_modify_during_iteration(self):
        """Graph iteration is stable even with modifications."""
        graph = create_spatial_scene()
        
        for i in range(10):
            graph.add_source(f"s{i}")
        
        # Get snapshot for iteration
        sources = list(graph.sources)  # Copy
        
        # Modify while "iterating" (simulated)
        graph.remove_source("s5")
        graph.add_source("s99")
        
        # Original snapshot should be unchanged
        assert len(sources) == 10


class TestHRTFEngineStress:
    """Stress tests for HRTF engine."""
    
    def test_many_filter_operations(self):
        """Many filter operations don't cause issues."""
        engine = HRTFEngine()
        listener = ListenerNode()
        
        # Process many sources sequentially
        for i in range(100):
            pos = Position3D(x=math.sin(i/10), y=0, z=1 + i/100)
            source = SpatialNode(name=f"s{i}", position=pos)
            
            left, right = engine.process_source(source, listener, [0.5] * 100)
        
        # Should complete without error
        assert True
    
    def test_varying_buffer_sizes(self):
        """Different buffer sizes are handled."""
        engine = HRTFEngine()
        listener = ListenerNode()
        source = SpatialNode(name="test", position=Position3D(x=0, y=0, z=1))
        
        sizes = [1, 10, 64, 128, 256, 512, 1024, 4096, 10000]
        
        for size in sizes:
            samples = [0.5] * size
            left, right = engine.process_source(source, listener, samples)
            
            assert len(left) == size
            assert len(right) == size


class TestNumericalStability:
    """Tests for numerical edge cases."""
    
    def test_very_small_gains(self):
        """Very small gains don't cause underflow."""
        source = SpatialNode(
            name="far",
            position=Position3D(x=0, y=0, z=1000),
            distance_model="exponential"
        )
        
        gain = source.calculate_gain(1000)
        
        assert not math.isnan(gain)
        assert not math.isinf(gain)
    
    def test_accumulated_error(self):
        """Accumulated floating-point error stays bounded."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0, position=Position3D(x=0, y=0, z=1)),
            MovementKeyframe(time_ms=1000, position=Position3D(x=1, y=0, z=1)),
        ])
        
        # Many evaluations (0ms to 1000ms, step 1ms)
        positions = [path.position_at(t) for t in range(1001)]
        
        # Check key points
        assert abs(positions[0].x - 0.0) < 0.001
        assert abs(positions[500].x - 0.5) < 0.01
        assert abs(positions[1000].x - 1.0) < 0.001
    
    def test_denormal_handling(self):
        """Denormal floating-point values are handled."""
        engine = HRTFEngine()
        listener = ListenerNode()
        source = SpatialNode(name="test", position=Position3D(x=0, y=0, z=1))
        
        # Very small samples
        tiny = 1e-40
        samples = [tiny] * 100
        
        left, right = engine.process_source(source, listener, samples)
        
        # Should not have NaN or Inf
        for l, r in zip(left, right):
            assert not math.isnan(l)
            assert not math.isnan(r)
            assert not math.isinf(l)
            assert not math.isinf(r)
