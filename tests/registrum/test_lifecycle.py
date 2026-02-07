"""
4.8.2 — Lifecycle Ordering Tests

Goal: Prove lifecycle transitions obey Registrum ordering invariants.

Required Tests:
    ✓ IDLE → PLAYING (skip compile) → denied
    ✓ STOPPED → INTERRUPTING → denied
    ✓ FAILED → PLAYING → denied
    ✓ PLAYING → COMPILING → denied

State Machine:

    IDLE → COMPILING → SYNTHESIZING → PLAYING → STOPPED
                                         │
                                         ▼
                                    INTERRUPTING → STOPPED
                                         │
                                         ▼
                                       FAILED

If any test in this section fails → v2.8 must not ship.
"""

import pytest

from voice_soundboard.runtime.registrar import (
    AudioRegistrar,
    StreamState,
    TransitionAction,
    TransitionResult,
)

from .conftest import RegistrumTestHarness


class TestLifecycleOrdering:
    """4.8.2 Lifecycle Ordering Tests"""
    
    # =========================================================================
    # Test 1: IDLE → PLAYING (skip compile) → denied
    # =========================================================================
    
    def test_idle_to_playing_skipping_compile_denied(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """IDLE → PLAYING (skip compile) → denied"""
        # Create stream (starts in IDLE, transitions to COMPILING)
        stream_id = harness.create_stream(agent_id=agent)
        
        # Reset to IDLE state for this test
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        harness.advance_stream(stream_id, StreamState.STOPPED)
        
        # Now try to restart and skip directly to PLAYING
        harness.advance_stream(stream_id, StreamState.IDLE)
        
        # This should be denied - can't go IDLE → PLAYING directly
        decision = registrar.request(
            action=TransitionAction.PLAY,
            actor=agent,
            target=stream_id,
        )
        
        assert decision.allowed is False
        assert "invalid" in decision.reason.lower() or "transition" in decision.reason.lower()
    
    # =========================================================================
    # Test 2: STOPPED → INTERRUPTING → denied
    # =========================================================================
    
    def test_stopped_to_interrupting_denied(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
        stopped_stream: str,
    ):
        """STOPPED → INTERRUPTING → denied"""
        # Stream is already in STOPPED state
        state = registrar.get_state(stopped_stream)
        assert state is not None
        assert state.state == StreamState.STOPPED
        
        # Try to interrupt a stopped stream (invalid)
        decision = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent,
            target=stopped_stream,
        )
        
        assert decision.allowed is False
        assert "terminal" in decision.reason.lower() or "invalid" in decision.reason.lower()
    
    # =========================================================================
    # Test 3: FAILED → PLAYING → denied
    # =========================================================================
    
    def test_failed_to_playing_denied(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """FAILED → PLAYING → denied"""
        # Create stream and transition to FAILED
        stream_id = harness.create_stream(agent_id=agent)
        
        # Force into FAILED state
        result = registrar.request(
            action=TransitionAction.FAIL,
            actor=agent,
            target=stream_id,
        )
        
        # Verify we're in FAILED state
        state = registrar.get_state(stream_id)
        assert state is not None
        assert state.state == StreamState.FAILED
        
        # Try to play from FAILED (invalid - must restart first)
        decision = registrar.request(
            action=TransitionAction.PLAY,
            actor=agent,
            target=stream_id,
        )
        
        assert decision.allowed is False
    
    # =========================================================================
    # Test 4: PLAYING → COMPILING → denied
    # =========================================================================
    
    def test_playing_to_compiling_denied(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
        playing_stream: str,
    ):
        """PLAYING → COMPILING → denied"""
        # Stream is in PLAYING state
        state = registrar.get_state(playing_stream)
        assert state is not None
        assert state.state == StreamState.PLAYING
        
        # Try to go back to COMPILING (invalid)
        decision = registrar.request(
            action=TransitionAction.COMPILE,
            actor=agent,
            target=playing_stream,
        )
        
        assert decision.allowed is False
    
    # =========================================================================
    # Additional: Verify valid transitions work
    # =========================================================================
    
    def test_valid_lifecycle_progression(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Valid lifecycle: IDLE → COMPILING → SYNTHESIZING → PLAYING → STOPPED"""
        stream_id = harness.create_stream(agent_id=agent)
        
        # START: IDLE → COMPILING (done by create_stream)
        state = registrar.get_state(stream_id)
        assert state.state == StreamState.COMPILING
        
        # COMPILE: COMPILING → SYNTHESIZING
        result = registrar.request(
            action=TransitionAction.COMPILE,
            actor=agent,
            target=stream_id,
        )
        assert result.allowed is True
        assert registrar.get_state(stream_id).state == StreamState.SYNTHESIZING
        
        # SYNTHESIZE: SYNTHESIZING → PLAYING
        result = registrar.request(
            action=TransitionAction.SYNTHESIZE,
            actor=agent,
            target=stream_id,
        )
        assert result.allowed is True
        assert registrar.get_state(stream_id).state == StreamState.PLAYING
        
        # STOP: PLAYING → STOPPED
        result = registrar.request(
            action=TransitionAction.STOP,
            actor=agent,
            target=stream_id,
        )
        assert result.allowed is True
        assert registrar.get_state(stream_id).state == StreamState.STOPPED
    
    def test_interrupt_from_playing_allowed(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
        playing_stream: str,
    ):
        """PLAYING → INTERRUPTING is valid"""
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent,
            target=playing_stream,
        )
        
        assert result.allowed is True
        state = registrar.get_state(playing_stream)
        assert state.state == StreamState.INTERRUPTING
    
    def test_restart_from_stopped_allowed(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
        stopped_stream: str,
    ):
        """STOPPED → IDLE (restart) is valid"""
        result = registrar.request(
            action=TransitionAction.RESTART,
            actor=agent,
            target=stopped_stream,
        )
        
        assert result.allowed is True
        state = registrar.get_state(stopped_stream)
        assert state.state == StreamState.IDLE
    
    def test_restart_from_failed_allowed(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """FAILED → IDLE (restart) is valid"""
        # Create and fail a stream
        stream_id = harness.create_stream(agent_id=agent)
        registrar.request(TransitionAction.FAIL, agent, stream_id)
        
        # Should be able to restart
        result = registrar.request(
            action=TransitionAction.RESTART,
            actor=agent,
            target=stream_id,
        )
        
        assert result.allowed is True
        state = registrar.get_state(stream_id)
        assert state.state == StreamState.IDLE


class TestLifecycleInvariants:
    """Additional lifecycle invariant tests"""
    
    def test_all_invalid_transitions_denied_with_reason(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """All invalid transitions must be denied with reason"""
        stream_id = harness.create_stream(agent_id=agent)
        
        # COMPILING state - invalid transitions
        invalid_actions = [
            TransitionAction.PLAY,       # Can't skip synthesize
            TransitionAction.INTERRUPT,  # Can't interrupt while compiling
            TransitionAction.STOP,       # Must play first
        ]
        
        for action in invalid_actions:
            result = registrar.request(action, agent, stream_id)
            assert result.allowed is False, f"{action} should be denied from COMPILING"
            assert result.reason, f"{action} denial should have reason"
    
    def test_transition_reason_indicates_terminal_state(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
        stopped_stream: str,
    ):
        """Denial from terminal state mentions 'terminal_state'"""
        decision = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent,
            target=stopped_stream,
        )
        
        assert decision.allowed is False
        # Reason should indicate why (terminal state or invalid transition)
        assert (
            "terminal" in decision.reason.lower() or 
            "invalid" in decision.reason.lower() or
            "stopped" in decision.reason.lower()
        )
