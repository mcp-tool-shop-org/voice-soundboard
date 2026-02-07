"""
4.8.6 — Attestation Completeness Tests

Goal: Every decision must be explainable.

Required Tests:
    ✓ Every request yields an attestation
    ✓ Attestation includes: actor, action, target, decision, invariant(s) applied
    ✓ Denials are attested
    ✓ Accessibility decisions explicitly marked

If any test in this section fails → v2.8 must not ship.
"""

import pytest

from voice_soundboard.runtime.registrar import (
    AudioRegistrar,
    Attestation,
    StreamState,
    TransitionAction,
)

from .conftest import RegistrumTestHarness


class TestAttestationCompleteness:
    """4.8.6 Attestation Completeness Tests"""
    
    # =========================================================================
    # Test 1: Every request yields an attestation
    # =========================================================================
    
    def test_every_request_yields_attestation(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Every request yields an attestation"""
        initial_count = registrar.attestation_store.count()
        
        # Make several requests
        stream_id = harness.create_stream(agent_id=agent)  # +1
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)  # +1
        harness.advance_stream(stream_id, StreamState.PLAYING)  # +1
        harness.advance_stream(stream_id, StreamState.STOPPED)  # +1
        
        final_count = registrar.attestation_store.count()
        
        # Should have exactly 4 new attestations
        assert final_count == initial_count + 4
    
    # =========================================================================
    # Test 2: Attestation includes required fields
    # =========================================================================
    
    def test_attestation_includes_all_required_fields(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Attestation includes: actor, action, target, decision, invariant(s) applied"""
        stream_id = harness.create_stream(agent_id=agent)
        
        attestations = harness.get_attestations()
        att = next(
            (a for a in attestations if a.target == stream_id and a.action == "start"),
            None
        )
        
        assert att is not None
        
        # Required fields
        assert att.actor == agent, "Attestation must include actor"
        assert att.action == "start", "Attestation must include action"
        assert att.target == stream_id, "Attestation must include target"
        assert att.decision in ("allowed", "denied"), "Attestation must include decision"
        assert isinstance(att.invariants_checked, list), "Attestation must include invariants"
        
        # Additional required fields
        assert att.id is not None, "Attestation must have ID"
        assert att.timestamp is not None, "Attestation must have timestamp"
    
    def test_attestation_has_valid_id(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Attestation IDs are unique and valid"""
        stream1 = harness.create_stream(agent_id=agent)
        stream2 = harness.create_stream(agent_id=agent)
        
        attestations = harness.get_attestations()
        ids = [a.id for a in attestations]
        
        # All IDs unique
        assert len(ids) == len(set(ids)), "Attestation IDs must be unique"
        
        # IDs are non-empty strings
        for att_id in ids:
            assert att_id, "Attestation ID must not be empty"
            assert isinstance(att_id, str), "Attestation ID must be string"
    
    # =========================================================================
    # Test 3: Denials are attested
    # =========================================================================
    
    def test_denials_are_attested(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Denials are attested"""
        # Create stream owned by agent_a
        stream_id = harness.create_stream(agent_id=agent_a)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Agent B tries to interrupt (should be denied)
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent_b,
            target=stream_id,
        )
        
        assert result.allowed is False
        
        # Find the denial attestation
        attestations = harness.get_attestations()
        denial = next(
            (a for a in attestations 
             if a.target == stream_id and a.actor == agent_b and a.decision == "denied"),
            None
        )
        
        assert denial is not None, "Denial must be attested"
        assert denial.action == "interrupt"
        assert denial.reason, "Denial must have reason"
    
    # =========================================================================
    # Test 4: Accessibility decisions explicitly marked
    # =========================================================================
    
    def test_accessibility_decisions_explicitly_marked(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
        user: str,
    ):
        """Accessibility decisions explicitly marked"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Enable accessibility override
        registrar.request(
            action=TransitionAction.ENABLE_OVERRIDE,
            actor=user,
            target=stream_id,
        )
        
        # Agent blocked
        registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent,
            target=stream_id,
        )
        
        # Find accessibility-related attestations
        attestations = harness.get_attestations()
        
        # Enable override attestation
        enable_att = next(
            (a for a in attestations 
             if a.target == stream_id and a.action == "enable_override"),
            None
        )
        assert enable_att is not None
        assert enable_att.accessibility_driven is True
        
        # Agent denial attestation (blocked by accessibility)
        denial_att = next(
            (a for a in attestations 
             if a.target == stream_id and a.actor == agent and a.decision == "denied"),
            None
        )
        assert denial_att is not None
        # The denial reason should mention accessibility


class TestAttestationContent:
    """Tests for attestation content details"""
    
    def test_attestation_includes_invariants_checked(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Attestation lists which invariants were checked"""
        stream_id = harness.create_stream(agent_id=agent)
        
        attestations = harness.get_attestations()
        att = next(
            (a for a in attestations if a.target == stream_id),
            None
        )
        
        assert att is not None
        assert isinstance(att.invariants_checked, list)
        # At least some invariants should be checked for any transition
        # (depending on implementation)
    
    def test_attestation_reason_is_meaningful(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Attestation reason provides meaningful explanation"""
        stream_id = harness.create_stream(agent_id=agent_a)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Non-owner tries interrupt
        registrar.request(TransitionAction.INTERRUPT, agent_b, stream_id)
        
        attestations = harness.get_attestations()
        denial = next(
            (a for a in attestations 
             if a.target == stream_id and a.actor == agent_b and a.decision == "denied"),
            None
        )
        
        assert denial is not None
        assert len(denial.reason) > 0, "Reason must not be empty"
        # Reason should explain WHY it was denied
        assert "owner" in denial.reason.lower() or "not_owner" in denial.reason.lower()
    
    def test_attestation_timestamp_is_valid(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Attestation timestamps are valid and ordered"""
        import time
        from datetime import datetime, timedelta
        
        before = datetime.utcnow()
        
        stream_id = harness.create_stream(agent_id=agent)
        time.sleep(0.01)  # Small delay
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        
        after = datetime.utcnow()
        
        attestations = harness.get_attestations()
        target_atts = [a for a in attestations if a.target == stream_id]
        
        for att in target_atts:
            # Timestamp within reasonable bounds
            assert att.timestamp >= before - timedelta(seconds=1)
            assert att.timestamp <= after + timedelta(seconds=1)
        
        # Timestamps should be ordered
        for i in range(len(target_atts) - 1):
            assert target_atts[i].timestamp <= target_atts[i + 1].timestamp
    
    def test_attestation_to_dict_serializable(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Attestation can be serialized to dict"""
        import json
        
        stream_id = harness.create_stream(agent_id=agent)
        
        attestations = harness.get_attestations()
        att = next((a for a in attestations if a.target == stream_id), None)
        
        assert att is not None
        
        # Should be convertible to dict
        att_dict = att.to_dict()
        assert isinstance(att_dict, dict)
        
        # Should be JSON serializable
        json_str = json.dumps(att_dict)
        assert json_str
        
        # Required fields in dict
        assert "id" in att_dict
        assert "actor" in att_dict
        assert "action" in att_dict
        assert "target" in att_dict
        assert "decision" in att_dict


class TestAttestationQuerying:
    """Tests for attestation querying capabilities"""
    
    def test_query_by_actor(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Can query attestations by actor"""
        stream1 = harness.create_stream(agent_id=agent_a)
        stream2 = harness.create_stream(agent_id=agent_b)
        
        # Query by actor
        agent_a_atts = registrar.attestation_store.query(actor=agent_a)
        agent_b_atts = registrar.attestation_store.query(actor=agent_b)
        
        assert all(a.actor == agent_a for a in agent_a_atts)
        assert all(a.actor == agent_b for a in agent_b_atts)
    
    def test_query_by_action(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Can query attestations by action"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        start_atts = registrar.attestation_store.query(action="start")
        compile_atts = registrar.attestation_store.query(action="compile")
        
        assert all(a.action == "start" for a in start_atts)
        assert all(a.action == "compile" for a in compile_atts)
    
    def test_query_by_decision(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Can query attestations by decision"""
        stream_id = harness.create_stream(agent_id=agent_a)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Create a denial
        registrar.request(TransitionAction.INTERRUPT, agent_b, stream_id)
        
        allowed_atts = registrar.attestation_store.query(decision="allowed")
        denied_atts = registrar.attestation_store.query(decision="denied")
        
        assert all(a.decision == "allowed" for a in allowed_atts)
        assert all(a.decision == "denied" for a in denied_atts)
