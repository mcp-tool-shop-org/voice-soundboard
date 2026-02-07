"""
Registrum Test Fixtures — Shared infrastructure for all 4.8 tests.

Provides:
    - Isolated registrar instances
    - Mock runtime for bypass detection
    - Attestation capture utilities
    - Concurrency helpers
    - Latency benchmarking tools
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

import pytest

from voice_soundboard.runtime.registrar import (
    AudioRegistrar,
    Attestation,
    AttestationStore,
    StreamState,
    StreamOwnership,
    AudioState,
    TransitionAction,
    TransitionRequest,
    TransitionResult,
)
from voice_soundboard.runtime.registrar.transitions import DecisionKind
from voice_soundboard.runtime.registrar.bridge import RegistrumBridge, RegistrumConfig
from voice_soundboard.runtime.registrar.errors import (
    AccessibilityBypassError,
    InvariantViolationError,
    OwnershipError,
    RegistrarError,
)


# =============================================================================
# Custom Errors for Tests
# =============================================================================

class RegistrarRequiredError(RegistrarError):
    """
    Raised when a state mutation is attempted without registrar mediation.
    
    This error is caught by tests in 4.8.1 to verify that all state
    changes go through the registrar.
    """
    
    def __init__(self, action: str, stream_id: str | None = None):
        super().__init__(
            f"Action '{action}' requires registrar mediation",
            details={"action": action, "stream_id": stream_id},
        )
        self.action = action
        self.stream_id = stream_id


# =============================================================================
# Test Harness
# =============================================================================

@dataclass
class RegistrumTestHarness:
    """
    Test harness for Registrum integration tests.
    
    Provides:
    - Isolated registrar instances
    - Attestation capture
    - State snapshot/restore
    - Deterministic time (optional)
    """
    
    capture_attestations: bool = True
    deterministic_time: bool = False
    
    # Internal state
    _registrar: AudioRegistrar | None = field(default=None, init=False)
    _streams: dict[str, dict[str, Any]] = field(default_factory=dict, init=False)
    _captured_attestations: list[Attestation] = field(default_factory=list, init=False)
    _time_offset: float = field(default=0.0, init=False)
    
    def create_registrar(self, **kwargs) -> AudioRegistrar:
        """Create an isolated registrar instance."""
        config = RegistrumConfig(**kwargs)
        self._registrar = AudioRegistrar(config=config)
        return self._registrar
    
    @property
    def registrar(self) -> AudioRegistrar:
        """Get current registrar (create if needed)."""
        if self._registrar is None:
            self._registrar = AudioRegistrar()
        return self._registrar
    
    def create_stream(
        self,
        agent_id: str = "test_agent",
        session_id: str = "test_session",
        priority: int = 5,
    ) -> str:
        """Create a new stream via registrar and return its ID."""
        stream_id = str(uuid4())
        
        result = self.registrar.request(
            action=TransitionAction.START,
            actor=agent_id,
            target=stream_id,
            metadata={
                "session_id": session_id,
                "priority": priority,
            },
        )
        
        if result.allowed:
            self._streams[stream_id] = {
                "agent_id": agent_id,
                "session_id": session_id,
                "state": StreamState.COMPILING,
            }
        
        return stream_id
    
    def advance_stream(self, stream_id: str, to_state: StreamState) -> TransitionResult:
        """Advance a stream to a specific state through valid transitions."""
        current = self.registrar.get_state(stream_id)
        if not current:
            raise ValueError(f"Stream {stream_id} not found")
        
        agent_id = current.ownership.agent_id if current.ownership else "test_agent"
        
        # Define the valid state progression path
        state_order = [
            StreamState.IDLE,
            StreamState.COMPILING,
            StreamState.SYNTHESIZING,
            StreamState.PLAYING,
        ]
        
        # Map each state to the action needed to reach it
        state_actions = {
            StreamState.COMPILING: TransitionAction.START,
            StreamState.SYNTHESIZING: TransitionAction.COMPILE,
            StreamState.PLAYING: TransitionAction.SYNTHESIZE,
            StreamState.INTERRUPTING: TransitionAction.INTERRUPT,
            StreamState.STOPPED: TransitionAction.STOP,
            StreamState.FAILED: TransitionAction.FAIL,
            StreamState.IDLE: TransitionAction.RESTART,
        }
        
        # Special case: restarting from STOPPED or FAILED to IDLE
        if to_state == StreamState.IDLE and current.state in {StreamState.STOPPED, StreamState.FAILED}:
            return self.registrar.request(
                action=TransitionAction.RESTART,
                actor=agent_id,
                target=stream_id,
            )
        
        # For main path states, advance through intermediate states
        if to_state in state_order and current.state in state_order:
            current_idx = state_order.index(current.state)
            target_idx = state_order.index(to_state)
            
            # Walk through intermediate states
            result = None
            for idx in range(current_idx + 1, target_idx + 1):
                next_state = state_order[idx]
                action = state_actions.get(next_state)
                if not action:
                    raise ValueError(f"Cannot transition to {next_state}")
                
                result = self.registrar.request(
                    action=action,
                    actor=agent_id,
                    target=stream_id,
                )
                if not result.allowed:
                    return result  # Stop on failure
            
            if result is None:
                raise ValueError(f"Already at state {to_state}")
            return result
        
        # For non-path states (interrupt, stop, fail), use direct action
        action = state_actions.get(to_state)
        if not action:
            raise ValueError(f"Cannot transition to {to_state}")
        
        return self.registrar.request(
            action=action,
            actor=agent_id,
            target=stream_id,
        )
    
    def get_attestations(self) -> list[Attestation]:
        """Get all captured attestations."""
        return self.registrar.attestation_store.all()
    
    def clear_attestations(self) -> None:
        """Clear captured attestations."""
        self._captured_attestations.clear()
    
    def create_agent(self, agent_id: str | None = None) -> str:
        """Create a test agent ID."""
        return agent_id or f"agent_{uuid4().hex[:8]}"
    
    def create_user(self, user_id: str | None = None) -> str:
        """Create a test user ID."""
        return user_id or f"user_{uuid4().hex[:8]}"


# =============================================================================
# Mock Runtime (for bypass detection)
# =============================================================================

class MockRuntime:
    """
    Mock runtime that enforces registrar mediation.
    
    Any attempt to mutate state without going through the registrar
    raises RegistrarRequiredError.
    """
    
    def __init__(self, registrar: AudioRegistrar):
        self._registrar = registrar
        self._streams: dict[str, dict[str, Any]] = {}
        self._bypass_enabled = False  # For testing bypass detection
    
    def enable_bypass(self) -> None:
        """Enable bypass mode (for testing that tests catch bypasses)."""
        self._bypass_enabled = True
    
    def disable_bypass(self) -> None:
        """Disable bypass mode."""
        self._bypass_enabled = False
    
    def start(self, stream_id: str, agent_id: str) -> TransitionResult:
        """Start a stream (must go through registrar)."""
        if self._bypass_enabled:
            # Direct mutation (WRONG - should be caught by tests)
            self._streams[stream_id] = {"state": StreamState.COMPILING}
            return TransitionResult(
                kind=DecisionKind.ACCEPTED,
                request=TransitionRequest(
                    action=TransitionAction.START,
                    actor=agent_id,
                    target=stream_id,
                ),
            )
        
        return self._registrar.request(
            action=TransitionAction.START,
            actor=agent_id,
            target=stream_id,
        )
    
    def interrupt(self, stream_id: str, agent_id: str | None = None) -> TransitionResult:
        """Interrupt a stream (must go through registrar)."""
        if self._bypass_enabled:
            # Direct mutation (WRONG)
            if stream_id in self._streams:
                self._streams[stream_id]["state"] = StreamState.INTERRUPTING
            return TransitionResult(
                kind=DecisionKind.ACCEPTED,
                request=TransitionRequest(
                    action=TransitionAction.INTERRUPT,
                    actor=agent_id or "bypass",
                    target=stream_id,
                ),
            )
        
        # Must have agent_id to request through registrar
        if agent_id is None:
            raise RegistrarRequiredError("interrupt", stream_id)
        
        return self._registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent_id,
            target=stream_id,
        )
    
    def stop(self, stream_id: str, agent_id: str | None = None) -> TransitionResult:
        """Stop a stream (must go through registrar)."""
        if self._bypass_enabled:
            if stream_id in self._streams:
                self._streams[stream_id]["state"] = StreamState.STOPPED
            return TransitionResult(
                kind=DecisionKind.ACCEPTED,
                request=TransitionRequest(
                    action=TransitionAction.STOP,
                    actor=agent_id or "bypass",
                    target=stream_id,
                ),
            )
        
        if agent_id is None:
            raise RegistrarRequiredError("stop", stream_id)
        
        return self._registrar.request(
            action=TransitionAction.STOP,
            actor=agent_id,
            target=stream_id,
        )
    
    # These _direct methods simulate bypassing the registrar, which should fail
    def stop_audio_direct(self, stream_id: str, requester: str | None = None) -> None:
        """Direct stop (WRONG - must go through registrar)."""
        raise RegistrarRequiredError("stop_audio_direct", stream_id)
    
    def interrupt_audio_direct(self, stream_id: str, requester: str | None = None) -> None:
        """Direct interrupt (WRONG - must go through registrar)."""
        raise RegistrarRequiredError("interrupt_audio_direct", stream_id)
    
    def play_audio_direct(self, stream_id: str, requester: str | None = None) -> None:
        """Direct play (WRONG - must go through registrar)."""
        raise RegistrarRequiredError("play_audio_direct", stream_id)
    
    def set_stream_state(self, stream_id: str, state: StreamState, requester: str | None = None) -> None:
        """Direct state mutation (WRONG - must go through registrar)."""
        raise RegistrarRequiredError("set_stream_state", stream_id)


# =============================================================================
# Concurrency Helpers
# =============================================================================

def parallel(
    operations: list[Callable[[], Any]],
    max_workers: int = 4,
) -> list[Any]:
    """
    Execute operations in parallel and collect results.
    
    Returns results in the same order as operations.
    """
    results = [None] * len(operations)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(op): i
            for i, op in enumerate(operations)
        }
        
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = e
    
    return results


def exactly_one(results: list[TransitionResult]) -> bool:
    """Check that exactly one result was allowed."""
    allowed_count = sum(1 for r in results if isinstance(r, TransitionResult) and r.allowed)
    return allowed_count == 1


# =============================================================================
# Latency Benchmarking
# =============================================================================

def benchmark_interrupts(
    registrar: AudioRegistrar,
    iterations: int = 1000,
) -> list[float]:
    """
    Benchmark interrupt decision latency.
    
    Returns list of latencies in milliseconds.
    """
    latencies = []
    
    for i in range(iterations):
        # Create a stream in PLAYING state
        stream_id = str(uuid4())
        agent_id = f"agent_{i}"
        
        # Start -> Compile -> Synthesize -> Play
        registrar.request(TransitionAction.START, agent_id, stream_id)
        registrar.request(TransitionAction.COMPILE, agent_id, stream_id)
        registrar.request(TransitionAction.SYNTHESIZE, agent_id, stream_id)
        
        # Benchmark the interrupt
        start = time.perf_counter()
        registrar.request(TransitionAction.INTERRUPT, agent_id, stream_id)
        end = time.perf_counter()
        
        latencies.append((end - start) * 1000)  # Convert to ms
    
    return latencies


def percentile(values: list[float], p: float) -> float:
    """Calculate the p-th percentile of values."""
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (p / 100)
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_values) else f
    
    if f == c:
        return sorted_values[f]
    
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def harness() -> RegistrumTestHarness:
    """Create an isolated test harness."""
    return RegistrumTestHarness(capture_attestations=True)


@pytest.fixture
def registrar(harness: RegistrumTestHarness) -> AudioRegistrar:
    """Create an isolated registrar instance."""
    return harness.create_registrar()


@pytest.fixture
def runtime(registrar: AudioRegistrar) -> MockRuntime:
    """Create a mock runtime with registrar enforcement."""
    return MockRuntime(registrar)


@pytest.fixture
def agent(harness: RegistrumTestHarness) -> str:
    """Create a test agent ID."""
    return harness.create_agent()


@pytest.fixture
def agent_a(harness: RegistrumTestHarness) -> str:
    """Create test agent A."""
    return harness.create_agent("agent_a")


@pytest.fixture
def agent_b(harness: RegistrumTestHarness) -> str:
    """Create test agent B."""
    return harness.create_agent("agent_b")


@pytest.fixture
def user(harness: RegistrumTestHarness) -> str:
    """Create a test user ID."""
    return harness.create_user()


@pytest.fixture
def stream(harness: RegistrumTestHarness, agent: str) -> str:
    """Create a test stream owned by agent."""
    return harness.create_stream(agent_id=agent)


@pytest.fixture
def playing_stream(harness: RegistrumTestHarness, agent: str) -> str:
    """Create a stream in PLAYING state."""
    stream_id = harness.create_stream(agent_id=agent)
    harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
    harness.advance_stream(stream_id, StreamState.PLAYING)
    return stream_id


@pytest.fixture
def stopped_stream(harness: RegistrumTestHarness, agent: str) -> str:
    """Create a stream in STOPPED state."""
    stream_id = harness.create_stream(agent_id=agent)
    harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
    harness.advance_stream(stream_id, StreamState.PLAYING)
    harness.advance_stream(stream_id, StreamState.STOPPED)
    return stream_id
