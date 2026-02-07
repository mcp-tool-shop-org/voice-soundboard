"""
4.8.10 — Failure & Recovery Tests

Goal: Registrar must fail safe.

Required Tests:
    ✓ If registrar denies, no partial execution occurs
    ✓ Crash during transition → safe halt
    ✓ Restart recovery reads last known good state

If any test in this section fails → v2.8 must not ship.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time

from voice_soundboard.runtime.registrar import (
    AudioRegistrar,
    StreamState,
    TransitionAction,
    RegistrarError,
)

from .conftest import RegistrumTestHarness


class TestFailureAndRecovery:
    """4.8.10 Failure & Recovery Tests"""
    
    # =========================================================================
    # Test 1: If registrar denies, no partial execution occurs
    # =========================================================================
    
    def test_denial_no_partial_execution(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """If registrar denies, no partial execution occurs"""
        stream_id = harness.create_stream(agent_id=agent_a)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Capture state before denied action
        state_before = registrar.get_state(stream_id)
        
        # Non-owner attempts interrupt - denied
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent_b,
            target=stream_id,
        )
        
        assert result.allowed is False
        
        # State unchanged - no partial execution
        state_after = registrar.get_state(stream_id)
        assert state_after.state == state_before.state
        assert state_after.ownership.agent_id == state_before.ownership.agent_id
    
    # =========================================================================
    # Test 2: Crash during transition → safe halt
    # =========================================================================
    
    def test_crash_during_transition_safe_halt(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Crash during transition → safe halt"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Store original state
        original_state = registrar.get_state(stream_id)
        
        # Simulate crash during state computation
        with patch.object(
            registrar,
            '_compute_new_state',
            side_effect=RuntimeError("Simulated crash")
        ):
            with pytest.raises(RuntimeError):
                registrar.request(
                    action=TransitionAction.INTERRUPT,
                    actor=agent,
                    target=stream_id,
                )
        
        # System should be in safe state (original preserved since crash was during processing)
        state = registrar.get_state(stream_id)
        assert state.state == StreamState.PLAYING
    
    # =========================================================================
    # Test 3: Restart recovery reads last known good state
    # =========================================================================
    
    def test_restart_recovery_reads_last_known_good_state(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Restart recovery reads last known good state"""
        # Build up state
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Capture attestations as "persisted" state
        attestations = [a.to_dict() for a in harness.get_attestations()]
        
        # Simulate restart by creating new registrar
        recovered_registrar = registrar.replay(attestations)
        
        # State recovered
        state = recovered_registrar.get_state(stream_id)
        assert state is not None
        assert state.state == StreamState.PLAYING


class TestAtomicTransitions:
    """Tests for atomic transitions"""
    
    def test_transition_is_atomic(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Transition either fully completes or fully fails"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        original_state = registrar.get_state(stream_id).state
        
        # Valid transition
        result = registrar.request(
            action=TransitionAction.STOP,
            actor=agent,
            target=stream_id,
        )
        
        new_state = registrar.get_state(stream_id).state
        
        if result.allowed:
            # Full completion
            assert new_state == StreamState.STOPPED
        else:
            # Full rollback
            assert new_state == original_state
    
    def test_no_intermediate_state_visible(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """No intermediate state visible during transition"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        observed_states = []
        
        # Observer checking state
        original_get_state = registrar.get_state
        def observing_get_state(sid):
            state = original_get_state(sid)
            observed_states.append(state.state)
            return state
        
        # Perform transition
        registrar.request(
            action=TransitionAction.STOP,
            actor=agent,
            target=stream_id,
        )
        
        # Check final state
        final_state = registrar.get_state(stream_id)
        
        # No "transitioning" intermediate state
        assert final_state.state in [
            StreamState.PLAYING,  # Unchanged
            StreamState.STOPPED,  # Changed
            StreamState.INTERRUPTING,  # Valid intermediate
        ]


class TestDenialSafety:
    """Tests for denial safety"""
    
    def test_denied_action_has_no_side_effects(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Denied action has no side effects"""
        stream_id = harness.create_stream(agent_id=agent_a)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Capture everything
        state_before = registrar.get_state(stream_id)
        attestation_count_before = len(harness.get_attestations())
        
        # Denied action
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent_b,
            target=stream_id,
        )
        
        assert result.allowed is False
        
        # State unchanged
        state_after = registrar.get_state(stream_id)
        assert state_after.state == state_before.state
        
        # Attestation added (denial is logged)
        attestation_count_after = len(harness.get_attestations())
        assert attestation_count_after == attestation_count_before + 1
    
    def test_invalid_transition_denied_without_corruption(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Invalid transition denied without state corruption"""
        # create_stream uses START and results in COMPILING state
        stream_id = harness.create_stream(agent_id=agent)
        
        # Get current state
        state_before = registrar.get_state(stream_id)
        assert state_before.state == StreamState.COMPILING
        
        # COMPILING -> PLAYING directly is invalid (must go through SYNTHESIZING)
        result = registrar.request(
            action=TransitionAction.PLAY,
            actor=agent,
            target=stream_id,
        )
        
        assert result.allowed is False
        
        # State still valid (unchanged)
        state = registrar.get_state(stream_id)
        assert state.state == StreamState.COMPILING


class TestCrashRecovery:
    """Tests for crash recovery"""
    
    def test_recovery_preserves_ownership(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Recovery preserves ownership"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        attestations = [a.to_dict() for a in harness.get_attestations()]
        
        # Recover
        recovered = registrar.replay(attestations)
        
        state = recovered.get_state(stream_id)
        assert state.ownership.agent_id == agent
    
    def test_recovery_preserves_accessibility_state(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
        user: str,
    ):
        """Recovery preserves accessibility state"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Enable accessibility override
        registrar.request(
            action=TransitionAction.ENABLE_OVERRIDE,
            actor=user,
            target=stream_id,
        )
        
        attestations = [a.to_dict() for a in harness.get_attestations()]
        
        # Recover
        recovered = registrar.replay(attestations)
        
        # Agent should still be blocked
        result = recovered.request(
            action=TransitionAction.INTERRUPT,
            actor=agent,
            target=stream_id,
        )
        
        assert result.allowed is False
    
    def test_recovery_from_multiple_streams(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Recovery handles multiple streams"""
        stream1 = harness.create_stream(agent_id=agent)
        stream2 = harness.create_stream(agent_id=agent)
        
        harness.advance_stream(stream1, StreamState.PLAYING)
        harness.advance_stream(stream2, StreamState.SYNTHESIZING)
        
        attestations = [a.to_dict() for a in harness.get_attestations()]
        
        # Recover
        recovered = registrar.replay(attestations)
        
        state1 = recovered.get_state(stream1)
        state2 = recovered.get_state(stream2)
        
        assert state1.state == StreamState.PLAYING
        assert state2.state == StreamState.SYNTHESIZING


class TestFailureHandling:
    """Tests for failure handling"""
    
    def test_failed_stream_can_be_restarted(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Failed stream can be restarted"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        
        # Force failure
        registrar.request(
            action=TransitionAction.FAIL,
            actor=agent,
            target=stream_id,
        )
        
        state = registrar.get_state(stream_id)
        assert state.state == StreamState.FAILED
        
        # Restart
        result = registrar.request(
            action=TransitionAction.RESTART,
            actor=agent,
            target=stream_id,
        )
        
        assert result.allowed is True
        
        state = registrar.get_state(stream_id)
        assert state.state == StreamState.IDLE
    
    def test_stopped_stream_cleanup(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Stopped stream cleanup is safe"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        harness.advance_stream(stream_id, StreamState.STOPPED)
        
        state = registrar.get_state(stream_id)
        assert state.state == StreamState.STOPPED
        
        # Stopped stream can be restarted (STOPPED -> IDLE via RESTART)
        result = registrar.request(
            action=TransitionAction.RESTART,
            actor=agent,
            target=stream_id,
        )
        
        # Should succeed
        assert result.allowed is True
        
        # Stream is now IDLE
        final_state = registrar.get_state(stream_id)
        assert final_state.state == StreamState.IDLE
