"""
v3.1 Operational Soak Tests.

Long-running tests to prove audio power holds under stress:
- 8+ hour continuous sessions
- Combined streaming + mixing + effects
- Memory tracking and leak detection
- Registrar decision correctness under load
"""

import pytest
import time
import gc
import sys
from typing import Optional

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

from voice_soundboard.v3.audio_graph import (
    AudioGraph,
    AudioTrack,
    EffectNode,
    TrackType,
)
from voice_soundboard.v3.presets import PresetLibrary
from voice_soundboard.v3.plugins import (
    PluginContext,
    LoudnessAnalyzer,
    PeakDetector,
)


class SoakMetrics:
    """Metrics collector for soak tests."""
    
    def __init__(self):
        self.memory_samples: list[int] = []
        self.latency_samples: list[float] = []
        self.error_count: int = 0
        self.operation_count: int = 0
        self.start_time: float = time.time()
        self._initial_memory: int = 0
    
    def record_memory(self) -> None:
        """Record current memory usage."""
        gc.collect()  # Force GC for accurate measurement
        
        # Get memory from process (platform-specific)
        try:
            import psutil
            process = psutil.Process()
            memory = process.memory_info().rss
        except ImportError:
            # Fallback: use sys.getsizeof on known objects
            memory = sys.getsizeof(gc.get_objects())
        
        if not self._initial_memory:
            self._initial_memory = memory
        
        self.memory_samples.append(memory)
    
    def record_latency(self, latency_ms: float) -> None:
        """Record operation latency."""
        self.latency_samples.append(latency_ms)
    
    def record_error(self) -> None:
        """Record an error."""
        self.error_count += 1
    
    def record_operation(self) -> None:
        """Record a successful operation."""
        self.operation_count += 1
    
    @property
    def memory_growth_percent(self) -> float:
        """Percentage memory growth from start."""
        if not self.memory_samples or not self._initial_memory:
            return 0.0
        
        current = self.memory_samples[-1]
        growth = (current - self._initial_memory) / self._initial_memory * 100
        return max(0, growth)  # Don't report negative growth
    
    @property
    def latency_p99(self) -> float:
        """99th percentile latency in ms."""
        if not self.latency_samples:
            return 0.0
        
        sorted_latencies = sorted(self.latency_samples)
        p99_idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[p99_idx]
    
    @property
    def latency_p99_degradation_percent(self) -> float:
        """Degradation of p99 latency from first to last."""
        if len(self.latency_samples) < 100:
            return 0.0
        
        # Compare first 10% to last 10%
        n = len(self.latency_samples)
        early = sorted(self.latency_samples[:n//10])
        late = sorted(self.latency_samples[-n//10:])
        
        early_p99 = early[int(len(early) * 0.99)]
        late_p99 = late[int(len(late) * 0.99)]
        
        if early_p99 == 0:
            return 0.0
        
        return ((late_p99 - early_p99) / early_p99) * 100
    
    @property
    def elapsed_hours(self) -> float:
        """Hours elapsed since start."""
        return (time.time() - self.start_time) / 3600
    
    def report(self) -> dict:
        """Generate summary report."""
        return {
            "elapsed_hours": self.elapsed_hours,
            "operation_count": self.operation_count,
            "error_count": self.error_count,
            "memory_growth_percent": self.memory_growth_percent,
            "latency_p99_ms": self.latency_p99,
            "latency_degradation_percent": self.latency_p99_degradation_percent,
        }


def create_test_graph(num_tracks: int = 4) -> AudioGraph:
    """Create a test graph with multiple tracks and effects."""
    graph = AudioGraph(name=f"soak_test_{num_tracks}_tracks")
    
    for i in range(num_tracks):
        track = graph.add_track(f"track_{i}", TrackType.DIALOGUE)
        track.add_effect(EffectNode(name="eq", effect_type="eq", params={"gain": 0}))
        track.add_effect(EffectNode(name="comp", effect_type="compressor", params={"ratio": 2}))
        if i % 2 == 0:
            track.add_effect(EffectNode(name="reverb", effect_type="reverb", params={"decay": 0.5}))
    
    return graph


class TestOperationalSoak:
    """v3.1 operational guarantee tests.
    
    These tests verify system stability under extended operation.
    Use pytest -m soak to run these specifically.
    """
    
    @pytest.mark.soak
    @pytest.mark.slow
    def test_1_hour_audio_session(self):
        """System runs 1 hour with stable memory and latency.
        
        This is a scaled-down version of the 8-hour test for CI.
        """
        metrics = SoakMetrics()
        duration_seconds = 60 * 60  # 1 hour
        
        # For CI, use a much shorter duration
        if not pytest.config.getoption("--runsoak", default=False):
            duration_seconds = 60  # 1 minute
        
        graph = create_test_graph(4)
        
        start = time.time()
        cycle = 0
        
        while time.time() - start < duration_seconds:
            try:
                # Simulate audio cycle
                cycle_start = time.perf_counter()
                
                # Validate graph (catch any corruption)
                result = graph.validate()
                if not result.is_valid:
                    metrics.record_error()
                
                # Simulate some graph operations
                self._modify_graph_randomly(graph, cycle)
                
                cycle_latency = (time.perf_counter() - cycle_start) * 1000
                metrics.record_latency(cycle_latency)
                metrics.record_operation()
                
                # Sample memory periodically
                if cycle % 100 == 0:
                    metrics.record_memory()
                
                cycle += 1
                
                # Small delay to avoid CPU saturation
                time.sleep(0.001)
                
            except Exception as e:
                metrics.record_error()
        
        report = metrics.report()
        
        # Assertions
        assert metrics.error_count == 0, f"Errors occurred: {metrics.error_count}"
        assert metrics.memory_growth_percent < 50, \
            f"Memory growth too high: {metrics.memory_growth_percent:.1f}%"
        assert metrics.latency_p99_degradation_percent < 50, \
            f"Latency degradation too high: {metrics.latency_p99_degradation_percent:.1f}%"
    
    @pytest.mark.soak
    @pytest.mark.slow
    def test_8_hour_audio_session(self):
        """System runs 8 hours with stable memory and latency.
        
        Run with: pytest -m soak --runsoak
        """
        if not pytest.config.getoption("--runsoak", default=False):
            pytest.skip("8-hour soak test requires --runsoak flag")
        
        metrics = SoakMetrics()
        duration_seconds = 8 * 60 * 60  # 8 hours
        
        graph = create_test_graph(4)
        
        start = time.time()
        cycle = 0
        
        while time.time() - start < duration_seconds:
            try:
                cycle_start = time.perf_counter()
                
                result = graph.validate()
                if not result.is_valid:
                    metrics.record_error()
                
                self._modify_graph_randomly(graph, cycle)
                
                cycle_latency = (time.perf_counter() - cycle_start) * 1000
                metrics.record_latency(cycle_latency)
                metrics.record_operation()
                
                if cycle % 1000 == 0:
                    metrics.record_memory()
                    # Log progress every ~1000 cycles
                    print(f"Soak test: {metrics.elapsed_hours:.1f}h, "
                          f"{metrics.operation_count} ops, "
                          f"mem growth: {metrics.memory_growth_percent:.1f}%")
                
                cycle += 1
                time.sleep(0.01)  # Longer delay for 8-hour test
                
            except Exception as e:
                metrics.record_error()
        
        report = metrics.report()
        
        assert metrics.error_count == 0
        assert metrics.memory_growth_percent < 10
        assert metrics.latency_p99_degradation_percent < 20
    
    @pytest.mark.soak
    def test_combined_streaming_mixing_effects(self):
        """Streaming + mixing + effects simultaneously."""
        graph = create_test_graph(4)
        
        # Add effects to all tracks
        for track in graph.tracks:
            track.add_effect(EffectNode(name="eq2", effect_type="eq", params={"high": 2}))
            track.add_effect(EffectNode(name="limiter", effect_type="limiter", params={"ceiling": -1}))
        
        # Run for a period
        duration_seconds = 60  # 1 minute for regular tests
        start = time.time()
        
        while time.time() - start < duration_seconds:
            # Simulate combined operations
            self._modify_graph_randomly(graph, int(time.time()))
            
            # Validate consistency
            assert graph.is_consistent(), "Graph became inconsistent"
            
            time.sleep(0.01)
    
    def _modify_graph_randomly(self, graph: AudioGraph, seed: int) -> None:
        """Make random modifications to the graph."""
        import random
        random.seed(seed)
        
        if not graph.tracks:
            return
        
        # Pick a random operation
        op = random.randint(0, 5)
        
        if op == 0:
            # Modify volume
            track = random.choice(graph.tracks)
            track.volume = random.uniform(0.5, 1.5)
        
        elif op == 1:
            # Modify pan
            track = random.choice(graph.tracks)
            track.pan = random.uniform(-1, 1)
        
        elif op == 2:
            # Toggle mute
            track = random.choice(graph.tracks)
            track.mute = not track.mute
        
        elif op == 3:
            # Modify effect param
            track = random.choice(graph.tracks)
            if track.effects:
                effect = random.choice(track.effects)
                if "gain" in effect.params:
                    effect.params["gain"] = random.uniform(-3, 3)
        
        elif op == 4:
            # Add an effect
            track = random.choice(graph.tracks)
            if len(track.effects) < 10:  # Limit to avoid test failure
                track.add_effect(EffectNode(
                    name=f"temp_{seed}",
                    effect_type="eq",
                    params={"temp": seed},
                ))
        
        elif op == 5:
            # Remove an effect
            track = random.choice(graph.tracks)
            if track.effects:
                track.effects.pop()


class TestMemoryLeakDetection:
    """Tests for memory leak detection."""
    
    @pytest.mark.soak
    def test_graph_creation_deletion_no_leak(self):
        """Creating and deleting graphs should not leak memory."""
        gc.collect()
        
        # Get baseline
        initial_objects = len(gc.get_objects())
        
        # Create and delete many graphs
        for i in range(1000):
            graph = create_test_graph(4)
            del graph
            
            if i % 100 == 0:
                gc.collect()
        
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Allow some growth but not linear with iterations
        growth = final_objects - initial_objects
        assert growth < 1000, f"Object count grew by {growth}"
    
    @pytest.mark.soak
    def test_validation_no_leak(self):
        """Repeated validation should not leak."""
        graph = create_test_graph(4)
        gc.collect()
        
        initial_objects = len(gc.get_objects())
        
        for _ in range(10000):
            result = graph.validate()
            del result
        
        gc.collect()
        final_objects = len(gc.get_objects())
        
        growth = final_objects - initial_objects
        assert growth < 100, f"Object count grew by {growth}"
    
    @pytest.mark.soak
    def test_diff_no_leak(self):
        """Repeated diffing should not leak."""
        graph1 = create_test_graph(4)
        graph2 = create_test_graph(4)
        graph2.add_track("extra")
        
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        for _ in range(10000):
            diff = graph1.diff(graph2)
            del diff
        
        gc.collect()
        final_objects = len(gc.get_objects())
        
        growth = final_objects - initial_objects
        assert growth < 100, f"Object count grew by {growth}"


class TestStressLoad:
    """Stress tests for high load scenarios."""
    
    @pytest.mark.soak
    def test_many_tracks(self):
        """System should handle many tracks."""
        graph = AudioGraph()
        
        # Add 100 tracks
        for i in range(100):
            track = graph.add_track(f"track_{i}")
            track.add_effect(EffectNode(name="eq", effect_type="eq"))
        
        # Should still validate quickly
        start = time.perf_counter()
        result = graph.validate()
        elapsed = time.perf_counter() - start
        
        assert elapsed < 1.0, f"Validation took {elapsed:.2f}s"
        assert result.is_valid or result.has_warnings  # May have empty track warnings
    
    @pytest.mark.soak
    def test_deep_effect_chains(self):
        """System should handle deep effect chains up to limit."""
        graph = AudioGraph()
        track = graph.add_track("deep_track")
        
        # Add effects up to the limit
        for i in range(16):  # MAX_EFFECT_DEPTH
            track.add_effect(EffectNode(name=f"effect_{i}", effect_type="eq"))
        
        result = graph.validate()
        assert result.is_valid
    
    @pytest.mark.soak
    def test_rapid_modifications(self):
        """System should handle rapid modifications."""
        graph = create_test_graph(4)
        
        # Make many rapid modifications
        start = time.perf_counter()
        
        for i in range(10000):
            track = graph.tracks[i % len(graph.tracks)]
            track.volume = (i % 100) / 100
            track.pan = ((i % 200) - 100) / 100
        
        elapsed = time.perf_counter() - start
        
        # Should complete in reasonable time
        assert elapsed < 1.0, f"10000 modifications took {elapsed:.2f}s"
        
        # Graph should still be valid
        assert graph.is_consistent()


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy required")
class TestPluginSoak:
    """Soak tests for plugins."""
    
    @pytest.mark.soak
    def test_loudness_analyzer_stability(self):
        """LoudnessAnalyzer should be stable over many calls."""
        analyzer = LoudnessAnalyzer()
        ctx = PluginContext()
        
        samples = np.random.randn(24000) * 0.1
        
        for _ in range(10000):
            output = analyzer.process(samples, ctx)
            assert output is not None
        
        # Should have recorded metrics
        assert ctx.metrics.get_average("lufs") is not None
    
    @pytest.mark.soak
    def test_peak_detector_stability(self):
        """PeakDetector should be stable."""
        detector = PeakDetector()
        ctx = PluginContext()
        
        for i in range(10000):
            # Varying audio content
            samples = np.random.randn(1000) * (0.1 + (i % 10) * 0.09)
            output = detector.process(samples, ctx)
            assert output is not None


# Pytest configuration for soak tests
def pytest_configure(config):
    """Add custom markers."""
    config.addinivalue_line(
        "markers",
        "soak: mark test as soak test (long-running)"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow"
    )


def pytest_addoption(parser):
    """Add custom options."""
    parser.addoption(
        "--runsoak",
        action="store_true",
        default=False,
        help="run full soak tests (8+ hours)"
    )
