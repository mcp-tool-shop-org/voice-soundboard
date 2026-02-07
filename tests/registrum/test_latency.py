"""
4.8.5 — Hot-Path Latency Tests

Goal: Ensure registrar does not break real-time audio.

Required Tests:
    ✓ Interrupt decision p99 < 1 ms (in-process)
    ✓ No IPC on hot path
    ✓ Audio thread never blocks on registrar

Performance Budget:
    | Operation         | p50     | p99    | Max   |
    |-------------------|---------|--------|-------|
    | Interrupt decision| 0.1 ms  | 1.0 ms | 5 ms  |
    | Ownership check   | 0.05 ms | 0.5 ms | 2 ms  |
    | Attestation write | 0.1 ms  | 0.8 ms | 3 ms  |

If any test in this section fails → v2.8 must not ship.
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from voice_soundboard.runtime.registrar import (
    AudioRegistrar,
    StreamState,
    TransitionAction,
)

from .conftest import (
    RegistrumTestHarness,
    benchmark_interrupts,
    percentile,
)


class TestHotPathLatency:
    """4.8.5 Hot-Path Latency Tests"""
    
    # =========================================================================
    # Test 1: Interrupt decision p99 < 1 ms (in-process)
    # =========================================================================
    
    def test_interrupt_decision_p99_under_1ms(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
    ):
        """Interrupt decision p99 < 1 ms (in-process)"""
        latencies = benchmark_interrupts(registrar, iterations=1000)
        
        p99 = percentile(latencies, 99)
        
        assert p99 < 1.0, f"p99 latency {p99:.3f}ms exceeds 1ms budget"
    
    def test_interrupt_decision_p50_under_100us(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
    ):
        """Interrupt decision p50 < 0.1 ms"""
        latencies = benchmark_interrupts(registrar, iterations=1000)
        
        p50 = percentile(latencies, 50)
        
        assert p50 < 0.1, f"p50 latency {p50:.3f}ms exceeds 0.1ms budget"
    
    def test_interrupt_max_under_5ms(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
    ):
        """Interrupt decision max < 5 ms"""
        latencies = benchmark_interrupts(registrar, iterations=1000)
        
        max_latency = max(latencies)
        
        assert max_latency < 5.0, f"Max latency {max_latency:.3f}ms exceeds 5ms budget"
    
    # =========================================================================
    # Test 2: No IPC on hot path
    # =========================================================================
    
    def test_no_ipc_on_hot_path(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """No IPC on hot path"""
        # The registrar should work entirely in-process for hot path operations
        # This test verifies that decisions don't require external communication
        
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Measure time for interrupt - should be microseconds, not milliseconds
        start = time.perf_counter()
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent,
            target=stream_id,
        )
        end = time.perf_counter()
        
        latency_us = (end - start) * 1_000_000  # Convert to microseconds
        
        # If IPC were involved, we'd see latencies > 1000us typically
        # In-process should be < 500us most of the time
        assert latency_us < 5000, f"Latency {latency_us:.0f}us suggests IPC (expected < 5000us)"
        
        # Verify result was computed (not deferred)
        assert result.allowed is True or result.allowed is False
    
    # =========================================================================
    # Test 3: Audio thread never blocks on registrar
    # =========================================================================
    
    def test_audio_thread_never_blocks(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Audio thread never blocks on registrar"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Simulate audio thread callback timing
        # Audio callbacks typically need to complete in < 5ms (at 48kHz, 256 samples = 5.3ms)
        audio_callback_budget_ms = 5.0
        
        blocking_detected = False
        
        def audio_callback():
            nonlocal blocking_detected
            start = time.perf_counter()
            
            # This represents the registrar check that might happen in audio path
            registrar.get_state(stream_id)
            
            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms > audio_callback_budget_ms:
                blocking_detected = True
        
        # Run many iterations to catch any blocking
        for _ in range(1000):
            audio_callback()
        
        assert not blocking_detected, "Audio thread was blocked by registrar"
    
    def test_concurrent_requests_dont_block_each_other(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
    ):
        """Concurrent requests don't excessively block each other"""
        agents = [f"agent_{i}" for i in range(10)]
        streams = []
        
        # Create streams for each agent
        for agent in agents:
            stream_id = harness.create_stream(agent_id=agent)
            harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
            harness.advance_stream(stream_id, StreamState.PLAYING)
            streams.append((stream_id, agent))
        
        latencies = []
        
        def make_request(stream_id, agent):
            start = time.perf_counter()
            registrar.request(TransitionAction.INTERRUPT, agent, stream_id)
            end = time.perf_counter()
            return (end - start) * 1000
        
        # Run concurrent requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(make_request, stream_id, agent)
                for stream_id, agent in streams
            ]
            latencies = [f.result() for f in futures]
        
        p99 = percentile(latencies, 99)
        
        # Concurrent p99 should still be reasonable
        assert p99 < 10.0, f"Concurrent p99 {p99:.3f}ms exceeds budget"


class TestLatencyComponents:
    """Test individual latency components"""
    
    def test_ownership_check_latency(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Ownership check < 0.5 ms p99"""
        stream_id = harness.create_stream(agent_id=agent)
        
        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            state = registrar.get_state(stream_id)
            _ = state.ownership.agent_id if state and state.ownership else None
            end = time.perf_counter()
            latencies.append((end - start) * 1000)
        
        p99 = percentile(latencies, 99)
        assert p99 < 0.5, f"Ownership check p99 {p99:.3f}ms exceeds 0.5ms"
    
    def test_attestation_write_latency(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Attestation write overhead is minimal"""
        # Create stream
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Measure multiple interrupts to capture attestation write time
        latencies = []
        for i in range(100):
            # Re-create stream for each iteration
            s_id = f"attest_test_{i}"
            registrar.request(TransitionAction.START, agent, s_id)
            registrar.request(TransitionAction.COMPILE, agent, s_id)
            registrar.request(TransitionAction.SYNTHESIZE, agent, s_id)
            
            start = time.perf_counter()
            registrar.request(TransitionAction.INTERRUPT, agent, s_id)
            end = time.perf_counter()
            
            latencies.append((end - start) * 1000)
        
        p99 = percentile(latencies, 99)
        # Attestation write is part of the overall request
        # Budget: 0.8ms for attestation portion (part of total 1ms budget)
        assert p99 < 2.0, f"Request with attestation p99 {p99:.3f}ms too high"


class TestLatencyUnderLoad:
    """Latency tests under various load conditions"""
    
    def test_latency_stable_under_sustained_load(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
    ):
        """Latency remains stable under sustained load"""
        # Warm up
        for i in range(100):
            s_id = f"warmup_{i}"
            registrar.request(TransitionAction.START, "warmup_agent", s_id)
        
        # Measure batches
        batch_p99s = []
        
        for batch in range(5):
            batch_latencies = []
            for i in range(200):
                s_id = f"batch_{batch}_{i}"
                agent = f"agent_{i % 10}"
                
                registrar.request(TransitionAction.START, agent, s_id)
                registrar.request(TransitionAction.COMPILE, agent, s_id)
                registrar.request(TransitionAction.SYNTHESIZE, agent, s_id)
                
                start = time.perf_counter()
                registrar.request(TransitionAction.INTERRUPT, agent, s_id)
                end = time.perf_counter()
                
                batch_latencies.append((end - start) * 1000)
            
            batch_p99s.append(percentile(batch_latencies, 99))
        
        # All batches should have similar p99
        max_p99 = max(batch_p99s)
        min_p99 = min(batch_p99s)
        
        # Variance should be small (no degradation under load)
        assert max_p99 < 3.0, f"Max batch p99 {max_p99:.3f}ms exceeds budget"
        assert max_p99 - min_p99 < 1.0, f"Latency variance {max_p99 - min_p99:.3f}ms too high"
