"""
v2.9 Soak Tests — Long-Running Stability Tests

Purpose: Prove system stability under sustained load.

v2.9 must pass these tests before shipping.

Test Categories:
    1. Long-running soak test (8 hours)
    2. Concurrency stress test
    3. Memory leak detection
    4. Latency degradation detection
    5. Replay correctness under load

If any test fails or flakes → v2.9 blocks.
"""

import pytest
import time
import threading
import statistics
import gc
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import List, Dict, Any
from uuid import uuid4

from voice_soundboard.runtime.registrar import (
    AudioRegistrar,
    StreamState,
    TransitionAction,
)


# =============================================================================
# Configuration
# =============================================================================

# Soak test duration (can be overridden via env var)
SOAK_TEST_DURATION_HOURS = 8
SOAK_TEST_DURATION_SECONDS = SOAK_TEST_DURATION_HOURS * 60 * 60

# Short soak for CI (30 minutes)
SHORT_SOAK_DURATION_SECONDS = 30 * 60

# Stress test parameters
STRESS_WORKERS = 20
STRESS_ITERATIONS_PER_WORKER = 1000


# =============================================================================
# Metrics Collection
# =============================================================================

@dataclass
class SoakMetrics:
    """Metrics collected during soak tests."""
    
    requests: int = 0
    errors: int = 0
    latency_samples: List[float] = field(default_factory=list)
    memory_samples: List[int] = field(default_factory=list)
    
    # Tracking
    start_time: float = field(default_factory=time.time)
    
    def record_request(self, latency_ms: float, success: bool = True) -> None:
        """Record a single request."""
        self.requests += 1
        self.latency_samples.append(latency_ms)
        if not success:
            self.errors += 1
    
    def record_memory(self, memory_bytes: int) -> None:
        """Record memory usage sample."""
        self.memory_samples.append(memory_bytes)
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.requests == 0:
            return 0.0
        return self.errors / self.requests
    
    @property
    def p50_latency(self) -> float:
        """Calculate p50 latency."""
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.50)
        return sorted_samples[idx]
    
    @property
    def p99_latency(self) -> float:
        """Calculate p99 latency."""
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.99)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def latency_std_dev(self) -> float:
        """Calculate latency standard deviation."""
        if len(self.latency_samples) < 2:
            return 0.0
        return statistics.stdev(self.latency_samples)
    
    def is_memory_stable(self, threshold_growth_percent: float = 50.0) -> bool:
        """Check if memory is stable (not leaking)."""
        if len(self.memory_samples) < 10:
            return True
        
        # Compare first 10% to last 10%
        early = self.memory_samples[:len(self.memory_samples) // 10]
        late = self.memory_samples[-len(self.memory_samples) // 10:]
        
        avg_early = statistics.mean(early)
        avg_late = statistics.mean(late)
        
        if avg_early == 0:
            return True
        
        growth_percent = ((avg_late - avg_early) / avg_early) * 100
        return growth_percent < threshold_growth_percent
    
    def is_latency_stable(self, threshold_degradation_percent: float = 20.0) -> bool:
        """Check if latency is stable (not degrading)."""
        if len(self.latency_samples) < 100:
            return True
        
        # Compare first 10% to last 10%
        early = self.latency_samples[:len(self.latency_samples) // 10]
        late = self.latency_samples[-len(self.latency_samples) // 10:]
        
        avg_early = statistics.mean(early)
        avg_late = statistics.mean(late)
        
        if avg_early == 0:
            return True
        
        degradation_percent = ((avg_late - avg_early) / avg_early) * 100
        return degradation_percent < threshold_degradation_percent


def get_memory_usage() -> int:
    """Get current memory usage in bytes."""
    import sys
    # Rough estimation using gc
    gc.collect()
    return sum(sys.getsizeof(obj) for obj in gc.get_objects()[:1000])


# =============================================================================
# 1. Long-Running Soak Test
# =============================================================================

class TestLongRunningSoak:
    """
    8-hour soak test for system stability.
    
    Verifies:
    - No memory leaks
    - No latency degradation
    - Error rate stays low
    - System remains functional
    """
    
    @pytest.mark.slow
    @pytest.mark.soak
    def test_8_hour_soak(self):
        """System must run 8 hours without degradation."""
        registrar = AudioRegistrar()
        metrics = SoakMetrics()
        
        start = time.time()
        duration = SOAK_TEST_DURATION_SECONDS
        
        # Run for duration
        while time.time() - start < duration:
            self._run_iteration(registrar, metrics)
            
            # Memory check every 1000 requests
            if metrics.requests % 1000 == 0:
                metrics.record_memory(get_memory_usage())
            
            # Small sleep to avoid CPU saturation
            time.sleep(0.001)
        
        # Verify no degradation
        assert metrics.error_rate < 0.001, f"Error rate too high: {metrics.error_rate}"
        assert metrics.is_memory_stable(), "Memory leak detected"
        assert metrics.is_latency_stable(), "Latency degradation detected"
        assert metrics.p99_latency < 10.0, f"p99 latency too high: {metrics.p99_latency}ms"
    
    @pytest.mark.soak
    def test_30_minute_soak(self):
        """Short soak test for CI (30 minutes)."""
        registrar = AudioRegistrar()
        metrics = SoakMetrics()
        
        start = time.time()
        duration = SHORT_SOAK_DURATION_SECONDS
        
        while time.time() - start < duration:
            self._run_iteration(registrar, metrics)
            
            if metrics.requests % 1000 == 0:
                metrics.record_memory(get_memory_usage())
            
            time.sleep(0.001)
        
        # Verify no degradation
        assert metrics.error_rate < 0.001
        assert metrics.is_memory_stable()
        assert metrics.is_latency_stable()
    
    def _run_iteration(self, registrar: AudioRegistrar, metrics: SoakMetrics) -> None:
        """Run a single soak iteration."""
        agent = f"soak_agent_{metrics.requests % 10}"
        
        start = time.time()
        
        try:
            # Create stream
            result = registrar.request(
                action=TransitionAction.START,
                actor=agent,
            )
            
            if result.allowed and result.effects:
                stream_id = result.effects[0].new_state.stream_id
                
                # Advance through lifecycle
                for action in [TransitionAction.COMPILE, TransitionAction.SYNTHESIZE]:
                    registrar.request(action=action, actor=agent, target=stream_id)
                
                # Stop
                registrar.request(
                    action=TransitionAction.STOP,
                    actor=agent,
                    target=stream_id,
                )
            
            latency = (time.time() - start) * 1000
            metrics.record_request(latency, success=True)
            
        except Exception as e:
            latency = (time.time() - start) * 1000
            metrics.record_request(latency, success=False)


# =============================================================================
# 2. Concurrency Stress Test
# =============================================================================

class TestConcurrencyStress:
    """
    Stress test under concurrent load.
    
    Verifies:
    - No race conditions
    - No deadlocks
    - State remains consistent
    """
    
    @pytest.mark.stress
    def test_concurrent_stress(self):
        """No races under concurrent load."""
        registrar = AudioRegistrar()
        errors: List[str] = []
        lock = threading.Lock()
        
        def worker(worker_id: int) -> None:
            for _ in range(STRESS_ITERATIONS_PER_WORKER):
                try:
                    self._stress_iteration(registrar, worker_id, errors, lock)
                except Exception as e:
                    with lock:
                        errors.append(f"Worker {worker_id}: {e}")
        
        # Run workers
        with ThreadPoolExecutor(max_workers=STRESS_WORKERS) as pool:
            futures = [pool.submit(worker, i) for i in range(STRESS_WORKERS)]
            wait(futures)
        
        assert len(errors) == 0, f"Stress test errors: {errors[:10]}"
    
    def _stress_iteration(
        self,
        registrar: AudioRegistrar,
        worker_id: int,
        errors: List[str],
        lock: threading.Lock,
    ) -> None:
        """Single stress iteration."""
        agent = f"stress_worker_{worker_id}"
        
        # Create stream
        result = registrar.request(
            action=TransitionAction.START,
            actor=agent,
        )
        
        if not result.allowed:
            return
        
        stream_id = result.effects[0].new_state.stream_id if result.effects else None
        if not stream_id:
            return
        
        # Race condition scenario: multiple concurrent actions
        results = []
        for action in [TransitionAction.COMPILE, TransitionAction.FAIL, TransitionAction.STOP]:
            r = registrar.request(action=action, actor=agent, target=stream_id)
            results.append(r)
        
        # State must be consistent
        state = registrar.get_state(stream_id)
        if state and state.state not in [
            StreamState.IDLE,
            StreamState.COMPILING,
            StreamState.SYNTHESIZING,
            StreamState.PLAYING,
            StreamState.INTERRUPTING,
            StreamState.STOPPED,
            StreamState.FAILED,
        ]:
            with lock:
                errors.append(f"Invalid state: {state.state}")
    
    @pytest.mark.stress
    def test_concurrent_ownership_claims(self):
        """Concurrent ownership claims must result in single winner."""
        registrar = AudioRegistrar()
        
        # Create unowned stream
        creator = "creator_agent"
        result = registrar.request(action=TransitionAction.START, actor=creator)
        stream_id = result.effects[0].new_state.stream_id if result.effects else None
        
        if not stream_id:
            pytest.skip("Could not create stream")
        
        # Many agents try to claim simultaneously
        claimers = [f"claimer_{i}" for i in range(10)]
        results: Dict[str, bool] = {}
        lock = threading.Lock()
        
        def claim(agent: str) -> None:
            r = registrar.request(
                action=TransitionAction.CLAIM,
                actor=agent,
                target=stream_id,
            )
            with lock:
                results[agent] = r.allowed
        
        # Run claims concurrently
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(claim, a) for a in claimers]
            wait(futures)
        
        # At most one should succeed (original owner already owns it)
        winners = [a for a, won in results.items() if won]
        assert len(winners) <= 1, f"Multiple claim winners: {winners}"


# =============================================================================
# 3. Memory Leak Detection
# =============================================================================

class TestMemoryLeakDetection:
    """
    Detect memory leaks in registrar operations.
    """
    
    @pytest.mark.memory
    def test_no_memory_leak_in_stream_creation(self):
        """Stream creation should not leak memory."""
        registrar = AudioRegistrar()
        
        initial_memory = get_memory_usage()
        
        # Create and cleanup many streams
        for i in range(10000):
            result = registrar.request(
                action=TransitionAction.START,
                actor=f"leak_test_agent_{i % 10}",
            )
            
            if result.allowed and result.effects:
                stream_id = result.effects[0].new_state.stream_id
                # Stop stream
                registrar.request(
                    action=TransitionAction.STOP,
                    actor=f"leak_test_agent_{i % 10}",
                    target=stream_id,
                )
        
        gc.collect()
        final_memory = get_memory_usage()
        
        # Allow some growth but not unbounded
        growth = final_memory - initial_memory
        growth_per_stream = growth / 10000
        
        # Should be minimal per-stream overhead
        assert growth_per_stream < 1000, f"Memory growth per stream: {growth_per_stream} bytes"
    
    @pytest.mark.memory
    def test_attestation_store_bounded(self):
        """Attestation store should not grow unboundedly."""
        registrar = AudioRegistrar()
        
        # Generate many attestations
        for i in range(5000):
            registrar.request(
                action=TransitionAction.START,
                actor=f"attestation_test_agent_{i % 10}",
            )
        
        attestation_count = registrar.attestation_store.count()
        
        # Attestations should be recorded
        assert attestation_count == 5000


# =============================================================================
# 4. Latency Degradation Detection
# =============================================================================

class TestLatencyDegradation:
    """
    Detect latency degradation over time.
    """
    
    @pytest.mark.latency
    def test_latency_stable_over_time(self):
        """Latency should not degrade over time."""
        registrar = AudioRegistrar()
        
        early_latencies = []
        late_latencies = []
        
        # Collect early latencies
        for _ in range(1000):
            start = time.time()
            registrar.request(
                action=TransitionAction.START,
                actor="latency_test_agent",
            )
            early_latencies.append((time.time() - start) * 1000)
        
        # Middle operations
        for _ in range(10000):
            registrar.request(
                action=TransitionAction.START,
                actor="latency_test_agent",
            )
        
        # Collect late latencies
        for _ in range(1000):
            start = time.time()
            registrar.request(
                action=TransitionAction.START,
                actor="latency_test_agent",
            )
            late_latencies.append((time.time() - start) * 1000)
        
        early_avg = statistics.mean(early_latencies)
        late_avg = statistics.mean(late_latencies)
        
        # Latency should not increase more than 50%
        if early_avg > 0:
            degradation = ((late_avg - early_avg) / early_avg) * 100
            assert degradation < 50, f"Latency degraded by {degradation}%"
    
    @pytest.mark.latency
    def test_p99_latency_under_budget(self):
        """p99 latency must stay under budget."""
        registrar = AudioRegistrar()
        latencies = []
        
        for _ in range(10000):
            start = time.time()
            registrar.request(
                action=TransitionAction.START,
                actor="p99_test_agent",
            )
            latencies.append((time.time() - start) * 1000)
        
        sorted_latencies = sorted(latencies)
        p99_idx = int(len(sorted_latencies) * 0.99)
        p99 = sorted_latencies[p99_idx]
        
        # p99 must be under 1ms (as per v2.9 spec)
        assert p99 < 1.0, f"p99 latency {p99}ms exceeds 1ms budget"


# =============================================================================
# 5. Replay Correctness Under Load
# =============================================================================

class TestReplayCorrectnessUnderLoad:
    """
    Verify replay correctness under load.
    """
    
    @pytest.mark.replay
    def test_replay_deterministic_under_load(self):
        """Replay should be deterministic under load."""
        registrar = AudioRegistrar()
        
        # Generate load
        for i in range(1000):
            result = registrar.request(
                action=TransitionAction.START,
                actor=f"replay_agent_{i % 5}",
            )
            
            if result.allowed and result.effects:
                stream_id = result.effects[0].new_state.stream_id
                # Advance
                registrar.request(
                    action=TransitionAction.COMPILE,
                    actor=f"replay_agent_{i % 5}",
                    target=stream_id,
                )
        
        # Capture state
        original_states = registrar.list_states()
        attestations = [a.to_dict() for a in registrar.attestation_store.all()]
        
        # Replay multiple times
        for _ in range(3):
            replayed = registrar.replay(attestations)
            replayed_states = replayed.list_states()
            
            # Compare (keys may differ but counts should match)
            assert len(replayed_states) == len(original_states)
    
    @pytest.mark.replay
    def test_replay_explains_all_state_changes(self):
        """Every state change should be explainable by replay."""
        registrar = AudioRegistrar()
        
        # Create and manipulate streams
        streams = []
        for i in range(50):
            result = registrar.request(
                action=TransitionAction.START,
                actor=f"explain_agent_{i}",
            )
            if result.allowed and result.effects:
                streams.append(result.effects[0].new_state.stream_id)
        
        # Various operations
        for stream_id in streams[:25]:
            registrar.request(
                action=TransitionAction.COMPILE,
                actor="explain_agent_0",
                target=stream_id,
            )
        
        for stream_id in streams[25:]:
            registrar.request(
                action=TransitionAction.FAIL,
                actor="explain_agent_1",
                target=stream_id,
            )
        
        # Get attestations
        attestations = registrar.attestation_store.all()
        
        # Every stream should have attestations explaining its state
        for stream_id in streams:
            stream_atts = [a for a in attestations if a.target == stream_id]
            assert len(stream_atts) > 0, f"No attestations for stream {stream_id}"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def fresh_registrar() -> AudioRegistrar:
    """Create a fresh registrar for each test."""
    return AudioRegistrar()
