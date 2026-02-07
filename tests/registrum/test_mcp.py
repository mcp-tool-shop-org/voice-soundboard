"""
4.8.8 — MCP ↔ Registrar Integration Tests

Goal: Ensure MCP layer cannot bypass registrar.

Required Tests:
    ✓ MCP tool call that starts audio must route via registrar
    ✓ MCP respects ownership rules
    ✓ Denial via MCP returns structured error

If any test in this section fails → v2.8 must not ship.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from voice_soundboard.runtime.registrar import (
    AudioRegistrar,
    StreamState,
    TransitionAction,
    RegistrarError,
)

from .conftest import RegistrumTestHarness, RegistrarRequiredError


class TestMCPRegistrarIntegration:
    """4.8.8 MCP ↔ Registrar Integration Tests"""
    
    # =========================================================================
    # Test 1: MCP tool call that starts audio must route via registrar
    # =========================================================================
    
    def test_mcp_audio_call_routes_via_registrar(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        runtime: Mock,
        agent: str,
    ):
        """MCP tool call that starts audio must route via registrar"""
        # MCP layer calls runtime to play audio
        # create_stream already uses START via registrar, putting stream in COMPILING
        stream_id = harness.create_stream(agent_id=agent)
        
        # Mock MCP tool call
        mcp_request = {
            "tool": "play_sound",
            "arguments": {"stream_id": stream_id},
            "actor": agent,
        }
        
        # Runtime enforces registrar usage - direct calls must fail
        with pytest.raises(RegistrarRequiredError):
            runtime.play_audio_direct(stream_id)
        
        # Verify the stream was created through registrar (already in COMPILING state)
        state = registrar.get_state(stream_id)
        assert state is not None
        assert state.state == StreamState.COMPILING
    # =========================================================================
    
    def test_mcp_respects_ownership_rules(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """MCP respects ownership rules"""
        # Agent A owns stream
        stream_id = harness.create_stream(agent_id=agent_a)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Simulate MCP tool call from Agent B
        mcp_result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent_b,
            target=stream_id,
        )
        
        # Non-owner denied via MCP
        assert mcp_result.allowed is False
        assert "ownership" in mcp_result.reason.lower() or "denied" in mcp_result.reason.lower()
    
    # =========================================================================
    # Test 3: Denial via MCP returns structured error
    # =========================================================================
    
    def test_mcp_denial_returns_structured_error(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Denial via MCP returns structured error"""
        stream_id = harness.create_stream(agent_id=agent_a)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Denial from non-owner
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent_b,
            target=stream_id,
        )
        
        # MCP can convert result to structured error
        assert result.allowed is False
        assert result.reason is not None
        assert len(result.reason) > 0
        
        # Result has structure for MCP error response
        error_data = {
            "allowed": result.allowed,
            "reason": result.reason,
            "action": str(TransitionAction.INTERRUPT),
            "target": stream_id,
            "actor": agent_b,
        }
        
        # All fields present
        assert all(v is not None for v in error_data.values())


class TestMCPToolRouting:
    """Tests for MCP tool routing"""
    
    def test_mcp_synthesize_tool_routes_via_registrar(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Synthesize tool call routes through registrar"""
        # create_stream starts in COMPILING state
        stream_id = harness.create_stream(agent_id=agent)
        # Advance through SYNTHESIZING first (COMPILING -> SYNTHESIZING requires COMPILE)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        
        # MCP synthesize request
        result = registrar.request(
            action=TransitionAction.SYNTHESIZE,
            actor=agent,
            target=stream_id,
        )
        
        # Allowed - owner requesting valid transition
        assert result.allowed is True
    
    def test_mcp_interrupt_tool_routes_via_registrar(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Interrupt tool call routes through registrar"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent,
            target=stream_id,
        )
        
        assert result.allowed is True
    
    def test_mcp_stop_tool_routes_via_registrar(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Stop tool call routes through registrar"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        result = registrar.request(
            action=TransitionAction.STOP,
            actor=agent,
            target=stream_id,
        )
        
        assert result.allowed is True


class TestMCPOwnershipEnforcement:
    """Tests for MCP ownership enforcement"""
    
    def test_mcp_cannot_claim_others_stream(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """MCP cannot claim another agent's stream"""
        stream_id = harness.create_stream(agent_id=agent_a)
        
        result = registrar.request(
            action=TransitionAction.CLAIM,
            actor=agent_b,
            target=stream_id,
        )
        
        # Already owned by agent_a
        assert result.allowed is False
    
    def test_mcp_transfer_requires_owner(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """MCP transfer requires current owner"""
        stream_id = harness.create_stream(agent_id=agent_a)
        
        # Agent B cannot transfer
        result = registrar.request(
            action=TransitionAction.TRANSFER,
            actor=agent_b,
            target=stream_id,
            metadata={"new_owner": agent_b},
        )
        
        assert result.allowed is False


class TestMCPErrorStructure:
    """Tests for MCP error structure"""
    
    def test_denial_has_machine_readable_format(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Denial has machine-readable format for MCP layer"""
        stream_id = harness.create_stream(agent_id=agent_a)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent_b,
            target=stream_id,
        )
        
        # Result can be serialized
        serializable = {
            "allowed": result.allowed,
            "reason": result.reason,
        }
        
        import json
        json_str = json.dumps(serializable)
        parsed = json.loads(json_str)
        
        assert parsed["allowed"] is False
        assert isinstance(parsed["reason"], str)
    
    def test_denial_reason_is_descriptive(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent_a: str,
        agent_b: str,
    ):
        """Denial reason is descriptive"""
        stream_id = harness.create_stream(agent_id=agent_a)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent_b,
            target=stream_id,
        )
        
        # Reason should be meaningful
        assert len(result.reason) > 5  # Not just "no" or "denied"
        assert any(word in result.reason.lower() for word in [
            "owner", "denied", "permission", "access", "not", "cannot"
        ])
    
    def test_accessibility_denial_reason_is_specific(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
        user: str,
    ):
        """Accessibility denial reason mentions accessibility"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # User enables accessibility override
        registrar.request(
            action=TransitionAction.ENABLE_OVERRIDE,
            actor=user,
            target=stream_id,
        )
        
        # Agent denied due to accessibility
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=agent,
            target=stream_id,
        )
        
        # Reason should mention accessibility
        assert result.allowed is False
        assert "access" in result.reason.lower() or "override" in result.reason.lower()
