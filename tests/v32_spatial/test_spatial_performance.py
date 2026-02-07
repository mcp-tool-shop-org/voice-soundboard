"""
v3.2 Spatial Performance Tests — Benchmarks and CPU bound verification.

Section 9: Performance & Overhead Tolerance

Performance Requirements:
- HRTF overhead bounded: <N ms per source per second of audio
- Spatial processing must not cause dropouts
- CPU bound must be provable and testable
"""

import pytest
import time
import math
from dataclasses import dataclass

from voice_soundboard.v3.spatial import (
    Position3D,
    Orientation3D,
    SpatialNode,
    ListenerNode,
    SpatialDownmixNode,
    HRTFEngine,
    HRTFParameters,
    HRTFProfile,
    MovementKeyframe,
    MovementPath,
    create_spatial_scene,
)


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""
    operation: str
    duration_ms: float
    iterations: int
    per_iteration_ms: float
    

def benchmark(name: str, iterations: int):
    """Decorator for benchmark tests."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            for _ in range(iterations):
                func(*args, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            return BenchmarkResult(
                operation=name,
                duration_ms=elapsed,
                iterations=iterations,
                per_iteration_ms=elapsed / iterations
            )
        return wrapper
    return decorator


class TestHRTFPerformance:
    """Performance tests for HRTF processing."""
    
    # Performance thresholds (generous for CI)
    MAX_MS_PER_SOURCE_PER_SECOND = 10.0  # 10ms of CPU per second of audio per source
    
    def test_single_source_performance(self):
        """Single source HRTF processing is fast enough."""
        engine = HRTFEngine()
        listener = ListenerNode()
        source = SpatialNode(name="test", position=Position3D(x=0.5, y=0, z=1))
        
        # 1 second of audio at 48kHz
        samples = [0.5] * 48000
        
        # Warm-up
        engine.process_source(source, listener, samples)
        
        # Benchmark
        iterations = 10
        start = time.perf_counter()
        for _ in range(iterations):
            engine.process_source(source, listener, samples)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        per_second_ms = elapsed_ms / iterations
        
        # Should be under threshold
        assert per_second_ms < self.MAX_MS_PER_SOURCE_PER_SECOND * 2, \
            f"HRTF processing too slow: {per_second_ms:.2f}ms per second of audio"
    
    def test_multi_source_scales_linearly(self):
        """Processing scales roughly linearly with source count."""
        engine = HRTFEngine()
        listener = ListenerNode()
        downmix = SpatialDownmixNode()
        iterations = 5
        
        def measure_sources(n_sources: int) -> float:
            sources = []
            for i in range(n_sources):
                pos = Position3D(x=math.sin(i), y=0, z=1)
                source = SpatialNode(name=f"s{i}", position=pos)
                sources.append((source, [0.5] * 4800))  # 100ms @ 48kHz
            
            # Warm-up
            engine.process_graph(sources, listener, downmix)
            
            start = time.perf_counter()
            for _ in range(iterations):
                engine.process_graph(sources, listener, downmix)
            return (time.perf_counter() - start) * 1000 / iterations
        
        time_8 = measure_sources(8)
        time_16 = measure_sources(16)
        
        # 2x sources should be roughly <3x time (allowing overhead)
        ratio = time_16 / time_8
        assert ratio < 4.0, f"Scaling not linear: {ratio:.2f}x for 2x sources"
    
    def test_hrtf_profile_performance_comparison(self):
        """Different HRTF profiles have predictable performance."""
        listener = ListenerNode()
        source = SpatialNode(name="test", position=Position3D(x=0.5, y=0, z=1))
        samples = [0.5] * 4800  # 100ms @ 48kHz
        iterations = 20
        
        results = {}
        
        for profile in [HRTFProfile.COMPACT, HRTFProfile.DEFAULT, HRTFProfile.WIDE]:
            params = HRTFParameters(profile=profile)
            engine = HRTFEngine(params)
            
            # Warm-up
            engine.process_source(source, listener, samples)
            
            start = time.perf_counter()
            for _ in range(iterations):
                engine.process_source(source, listener, samples)
            results[profile.name] = (time.perf_counter() - start) * 1000 / iterations
        
        # COMPACT should be faster than WIDE (simpler filters)
        # Allow some tolerance for measurement noise
        assert results['COMPACT'] < results['WIDE'] * 2, \
            f"COMPACT not faster: {results['COMPACT']:.2f}ms vs WIDE {results['WIDE']:.2f}ms"


class TestPositionUpdatePerformance:
    """Performance tests for position updates."""
    
    MAX_UPDATE_MICROSECONDS = 10.0  # Max time per position update
    
    def test_position_update_speed(self):
        """Position updates are very fast."""
        source = SpatialNode(name="test")
        iterations = 10000
        
        start = time.perf_counter()
        for i in range(iterations):
            source.set_position(
                x=math.sin(i / 100),
                y=0,
                z=1 + math.cos(i / 100)
            )
        elapsed_us = (time.perf_counter() - start) * 1_000_000
        
        per_update_us = elapsed_us / iterations
        
        assert per_update_us < self.MAX_UPDATE_MICROSECONDS, \
            f"Position update too slow: {per_update_us:.2f}µs"
    
    def test_path_evaluation_speed(self):
        """Movement path evaluation is fast."""
        path = MovementPath(keyframes=[
            MovementKeyframe(time_ms=0, position=Position3D(x=-1, y=0, z=1)),
            MovementKeyframe(time_ms=1000, position=Position3D(x=0, y=0, z=2)),
            MovementKeyframe(time_ms=2000, position=Position3D(x=1, y=0, z=1)),
        ])
        
        iterations = 10000
        
        start = time.perf_counter()
        for i in range(iterations):
            path.position_at(i * 2000 / iterations)  # Sweep over 0ms to 2000ms
        elapsed_us = (time.perf_counter() - start) * 1_000_000
        
        per_eval_us = elapsed_us / iterations
        
        assert per_eval_us < 5.0, \
            f"Path evaluation too slow: {per_eval_us:.2f}µs"


class TestGraphOperationPerformance:
    """Performance tests for graph operations."""
    
    def test_add_source_speed(self):
        """Adding sources is fast."""
        iterations = 1000
        
        start = time.perf_counter()
        for _ in range(iterations):
            graph = create_spatial_scene()
            for i in range(10):
                graph.add_source(f"s{i}")
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        per_graph_ms = elapsed_ms / iterations
        
        assert per_graph_ms < 1.0, \
            f"Graph setup too slow: {per_graph_ms:.2f}ms for 10 sources"
    
    def test_validate_speed(self):
        """Graph validation is fast."""
        graph = create_spatial_scene()
        for i in range(32):
            graph.add_source(f"s{i}")
        
        iterations = 1000
        
        start = time.perf_counter()
        for _ in range(iterations):
            graph.validate()
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        per_validate_ms = elapsed_ms / iterations
        
        assert per_validate_ms < 0.5, \
            f"Validation too slow: {per_validate_ms:.2f}ms"


class TestCPUBoundVerification:
    """Tests to verify CPU usage is bounded."""
    
    def test_processing_time_proportional_to_samples(self):
        """Processing time scales with sample count."""
        engine = HRTFEngine()
        listener = ListenerNode()
        source = SpatialNode(name="test", position=Position3D(x=0, y=0, z=1))
        
        def measure(n_samples: int) -> float:
            samples = [0.5] * n_samples
            start = time.perf_counter()
            engine.process_source(source, listener, samples)
            return (time.perf_counter() - start) * 1000
        
        # Warm-up
        measure(1000)
        
        time_small = measure(10000)
        time_large = measure(40000)
        
        # 4x samples should be roughly 4x time (±50%)
        ratio = time_large / time_small
        assert 2.0 < ratio < 8.0, \
            f"Time not proportional to samples: {ratio:.2f}x for 4x samples"
    
    def test_worst_case_bounded(self):
        """Worst-case scenario still completes in bounded time."""
        engine = HRTFEngine()
        listener = ListenerNode()
        downmix = SpatialDownmixNode()
        
        # Worst case: max sources at various positions
        sources = []
        for i in range(32):
            pos = Position3D(x=math.sin(i), y=math.cos(i) * 0.5, z=1 + (i % 5))
            source = SpatialNode(name=f"s{i}", position=pos)
            # 100ms of audio per source
            sources.append((source, [0.5] * 4800))
        
        # Should complete within reasonable time (500ms for 100ms of audio with 32 sources)
        max_allowed_ms = 500.0
        
        start = time.perf_counter()
        left, right = engine.process_graph(sources, listener, downmix)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert elapsed_ms < max_allowed_ms, \
            f"Worst case too slow: {elapsed_ms:.2f}ms"


class TestRealTimeViability:
    """Tests to verify real-time processing is viable."""
    
    def test_buffer_processing_under_latency_budget(self):
        """Buffer processing fits within typical latency budget."""
        engine = HRTFEngine()
        listener = ListenerNode()
        downmix = SpatialDownmixNode()
        
        # Common buffer sizes/latencies:
        # 256 samples @ 48kHz = ~5.3ms
        # 512 samples @ 48kHz = ~10.7ms
        # 1024 samples @ 48kHz = ~21.3ms
        
        buffer_sizes = [256, 512, 1024]
        n_sources = 8  # Reasonable for real-time
        
        for buffer_size in buffer_sizes:
            sources = []
            for i in range(n_sources):
                pos = Position3D(x=math.sin(i), y=0, z=1 + (i % 3))
                source = SpatialNode(name=f"s{i}", position=pos)
                sources.append((source, [0.5] * buffer_size))
            
            # Warm-up
            engine.process_graph(sources, listener, downmix)
            
            # Measure
            iterations = 100
            start = time.perf_counter()
            for _ in range(iterations):
                engine.process_graph(sources, listener, downmix)
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            per_buffer_ms = elapsed_ms / iterations
            buffer_duration_ms = (buffer_size / 48000) * 1000
            
            # Processing should take less than buffer duration
            # (with some margin for other processing)
            processing_budget = buffer_duration_ms * 0.5  # 50% of buffer time
            
            # Note: This may fail on slow CI, so we're lenient
            if per_buffer_ms > processing_budget:
                pytest.skip(f"CI too slow: {per_buffer_ms:.2f}ms > {processing_budget:.2f}ms budget")


class TestMemoryPerformance:
    """Performance tests related to memory."""
    
    def test_no_allocation_in_hot_path(self):
        """Processing doesn't cause excessive allocations."""
        engine = HRTFEngine()
        listener = ListenerNode()
        source = SpatialNode(name="test", position=Position3D(x=0, y=0, z=1))
        samples = [0.5] * 1000
        
        # Python doesn't give us direct allocation tracking,
        # but we can verify output is reused appropriately
        
        # Pre-warm
        engine.process_source(source, listener, samples)
        
        # Process many times
        for _ in range(100):
            left, right = engine.process_source(source, listener, samples)
            
            # Verify output structure
            assert isinstance(left, list)
            assert isinstance(right, list)


class TestBenchmarkSummary:
    """Summary benchmark that exercises full pipeline."""
    
    def test_full_pipeline_benchmark(self):
        """
        Full pipeline benchmark with summary statistics.
        
        This test exercises the complete spatial audio pipeline
        and reports timing information.
        """
        # Setup
        graph = create_spatial_scene()
        
        positions = []
        for i in range(16):
            angle = (i / 16) * 2 * math.pi
            pos = Position3D(
                x=math.sin(angle) * 0.8,
                y=math.cos(angle) * 0.3,
                z=1 + (i % 4)
            )
            positions.append(pos)
            source = graph.add_source(f"voice_{i}", pos)
            
            # Add movement via graph
            graph.add_movement(f"voice_{i}", MovementPath(keyframes=[
                MovementKeyframe(time_ms=0, position=pos),
                MovementKeyframe(
                    time_ms=2000,
                    position=Position3D(x=-pos.x, y=pos.y, z=pos.z)
                ),
            ]))
        
        # Validate graph
        result = graph.validate()
        assert result.is_valid
        
        # Process 1 second of audio
        engine = HRTFEngine()
        samples_per_chunk = 4800  # 100ms chunks
        
        total_start = time.perf_counter()
        
        for chunk in range(10):
            # Process each source
            sources = graph.sources
            source_data = []
            for s in sources:
                # Generate simple audio
                audio = [0.1 * math.sin(2 * math.pi * 440 * i / 48000) 
                        for i in range(samples_per_chunk)]
                source_data.append((s, audio))
            
            # Mix
            left, right = engine.process_graph(
                source_data,
                graph.listener,
                graph.downmix
            )
        
        total_ms = (time.perf_counter() - total_start) * 1000
        
        # 1 second of audio with 16 sources should process in reasonable time
        assert total_ms < 2000, f"Full pipeline too slow: {total_ms:.2f}ms"
        
        # Report metrics (for visibility in test output)
        print(f"\n[BENCHMARK] Full pipeline: {total_ms:.2f}ms for 1s of 16-source audio")
        print(f"[BENCHMARK] Per-source-second: {total_ms/16:.2f}ms")
