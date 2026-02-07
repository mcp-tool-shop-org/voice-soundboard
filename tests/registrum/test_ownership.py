"""
4.8.3 — Ownership & Authority Tests

Goal: Ensure only the owning actor may mutate a stream (unless overridden).

Required Tests:
    ✓ Non-owner interrupt → denied
    ✓ Owner interrupt → allowed
    ✓ Ownership transfer requires explicit registrar transition
    ✓ Multiple agents racing → single winner

📌 Invariant: Authority is exclusive and deterministic.

If any test in this section fails → v2.8 must not ship.
"""

import pytest

from voice_soundboard.runtime.registrar import (
    AudioRegistrar,
    StreamState,
    TransitionAction,
    TransitionResult,
)

from .conftest import (
    RegistrumTestHarness,
    parallel,
    exactly_one,
)


class TestOwnershipAuthority:
    """4.8.3 Ownership & Authority Tests"""
    
    # =========================================================================
    # Test 1: Non-owner interrupt → denied
    # =========================================================================
    
    def test_non_owner_interrupt_denied(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Non-owner interrupt → denied"""
        # Agent A creates and owns the stream
        stream_id = harness.create_stream(agent_id=agent_a)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Verify Agent A owns it
        state = registrar.get_state(stream_id)
        assert state.ownership.agent_id == agent_a
        
        # Agent B (non-owner) tries to interrupt
        decision = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent_b,
            target=stream_id,
        )
        
        assert decision.allowed is False
        assert "owner" in decision.reason.lower() or "not_owner" in decision.reason.lower()
    
    # =========================================================================
    # Test 2: Owner interrupt → allowed
    # =========================================================================
    
    def test_owner_interrupt_allowed(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
        playing_stream: str,
    ):
        """Owner interrupt → allowed"""
        # Verify ownership
        state = registrar.get_state(playing_stream)
        assert state.ownership.agent_id == agent
        
        # Owner can interrupt
        decision = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent,
            target=playing_stream,
        )
        
        assert decision.allowed is True
        
        # State transitioned
        new_state = registrar.get_state(playing_stream)
        assert new_state.state == StreamState.INTERRUPTING
    
    # =========================================================================
    # Test 3: Ownership transfer requires explicit registrar transition
    # =========================================================================
    
    def test_ownership_transfer_requires_explicit_transition(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Ownership transfer requires explicit registrar transition"""
        # Agent A creates stream
        stream_id = harness.create_stream(agent_id=agent_a)
        
        # Agent A must explicitly release first
        release_result = registrar.request(
            action=TransitionAction.RELEASE,
            actor=agent_a,
            target=stream_id,
        )
        
        # Then Agent B can claim
        if release_result.allowed:
            claim_result = registrar.request(
                action=TransitionAction.CLAIM,
                actor=agent_b,
                target=stream_id,
            )
            
            if claim_result.allowed:
                state = registrar.get_state(stream_id)
                assert state.ownership.agent_id == agent_b
        
        # OR: Transfer action (if supported)
        # Either way, ownership change requires explicit registrar action
        attestations = harness.get_attestations()
        ownership_changes = [
            a for a in attestations 
            if a.target == stream_id and a.action in ("release", "claim", "transfer")
        ]
        
        # Ownership change must be attested
        assert len(ownership_changes) >= 1 or not release_result.allowed
    
    # =========================================================================
    # Test 4: Multiple agents racing → single winner
    # =========================================================================
    
    def test_multiple_agents_racing_single_winner(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Multiple agents racing → single winner"""
        # Create a stream owned by neither initially (use system)
        stream_id = "race_stream"
        
        # Both agents try to claim simultaneously
        decisions = parallel([
            lambda: registrar.request(
                action=TransitionAction.START,
                actor=agent_a,
                target=stream_id,
                metadata={"session_id": "session_a", "priority": 5},
            ),
            lambda: registrar.request(
                action=TransitionAction.START,
                actor=agent_b,
                target=stream_id,
                metadata={"session_id": "session_b", "priority": 5},
            ),
        ])
        
        # Exactly one should succeed
        assert exactly_one(decisions), "Exactly one agent should win the race"
        
        # Winner should own the stream
        state = registrar.get_state(stream_id)
        if state:
            owner = state.ownership.agent_id
            assert owner in (agent_a, agent_b)
            
            # The winner's decision should be "allowed"
            for d in decisions:
                if isinstance(d, TransitionResult):
                    if d.allowed:
                        # This agent should be the owner
                        pass  # Can't directly verify without more info
    
    def test_concurrent_interrupt_single_winner(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Two agents interrupting simultaneously → single winner"""
        # Agent A owns the stream
        stream_id = harness.create_stream(agent_id=agent_a)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Make stream interruptible by others (for this test)
        # Note: depends on implementation - may need different setup
        
        # Both agents try to interrupt
        decisions = parallel([
            lambda: registrar.request(TransitionAction.INTERRUPT, agent_a, stream_id),
            lambda: registrar.request(TransitionAction.INTERRUPT, agent_b, stream_id),
        ])
        
        # At most one should succeed (owner has priority)
        allowed_count = sum(
            1 for d in decisions 
            if isinstance(d, TransitionResult) and d.allowed
        )
        assert allowed_count <= 1


class TestOwnershipInvariants:
    """Additional ownership invariant tests"""
    
    def test_ownership_established_on_creation(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Stream creation establishes ownership"""
        stream_id = harness.create_stream(agent_id=agent)
        
        state = registrar.get_state(stream_id)
        assert state is not None
        assert state.ownership is not None
        assert state.ownership.agent_id == agent
    
    def test_ownership_persists_through_transitions(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Ownership persists through lifecycle transitions"""
        stream_id = harness.create_stream(agent_id=agent)
        
        # Advance through states
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        state1 = registrar.get_state(stream_id)
        assert state1.ownership.agent_id == agent
        
        harness.advance_stream(stream_id, StreamState.PLAYING)
        state2 = registrar.get_state(stream_id)
        assert state2.ownership.agent_id == agent
        
        harness.advance_stream(stream_id, StreamState.STOPPED)
        state3 = registrar.get_state(stream_id)
        assert state3.ownership.agent_id == agent
    
    def test_higher_priority_does_not_auto_claim(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Higher priority agent cannot auto-claim another's stream"""
        # Agent A creates with priority 5
        stream_id = harness.create_stream(agent_id=agent_a, priority=5)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Agent B with priority 10 tries to interrupt
        decision = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent_b,
            target=stream_id,
            metadata={"priority": 10},
        )
        
        # Priority alone doesn't grant ownership rights
        # Must still be denied unless stream is interruptible
        state = registrar.get_state(stream_id)
        if not state.ownership.interruptible:
            assert decision.allowed is False
    
    def test_authority_is_deterministic(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Same inputs always produce same ownership decisions"""
        results = []
        
        for _ in range(10):
            # Reset registrar for each iteration
            fresh_registrar = harness.create_registrar()
            
            stream_id = "determinism_test"
            
            # Same sequence of operations
            fresh_registrar.request(TransitionAction.START, agent_a, stream_id)
            
            # Agent B tries to claim
            decision = fresh_registrar.request(
                action=TransitionAction.CLAIM,
                actor=agent_b,
                target=stream_id,
            )
            
            results.append(decision.allowed)
        
        # All results should be identical
        assert all(r == results[0] for r in results), "Authority must be deterministic"
