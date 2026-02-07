"""
4.8.9 — Plugin Containment Tests

Goal: Third-party code cannot mutate state without registrar.

Required Tests:
    ✓ Plugin hook cannot change lifecycle directly
    ✓ Plugin request routed through registrar
    ✓ Denial logged and reported to plugin

If any test in this section fails → v2.8 must not ship.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Optional

from voice_soundboard.runtime.registrar import (
    AudioRegistrar,
    StreamState,
    TransitionAction,
)

from .conftest import RegistrumTestHarness, RegistrarRequiredError


class MockPlugin:
    """Simulates a third-party plugin"""
    
    def __init__(self, plugin_id: str = "test_plugin"):
        self.plugin_id = plugin_id
        self.denials = []
        self.approvals = []
    
    def on_denial(self, result):
        """Hook called when plugin request is denied"""
        self.denials.append(result)
    
    def on_approval(self, result):
        """Hook called when plugin request is approved"""
        self.approvals.append(result)


class TestPluginContainment:
    """4.8.9 Plugin Containment Tests"""
    
    # =========================================================================
    # Test 1: Plugin hook cannot change lifecycle directly
    # =========================================================================
    
    def test_plugin_cannot_change_lifecycle_directly(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        runtime: Mock,
        agent: str,
    ):
        """Plugin hook cannot change lifecycle directly"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Plugin attempts direct manipulation via runtime
        plugin = MockPlugin()
        
        with pytest.raises(RegistrarRequiredError):
            runtime.stop_audio_direct(stream_id, requester=plugin.plugin_id)
        
        # State unchanged
        state = registrar.get_state(stream_id)
        assert state.state == StreamState.PLAYING
    
    # =========================================================================
    # Test 2: Plugin request routed through registrar
    # =========================================================================
    
    def test_plugin_request_routed_through_registrar(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Plugin request routed through registrar"""
        plugin = MockPlugin()
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Plugin must use registrar
        result = registrar.request(
            action=TransitionAction.STOP,
            actor=plugin.plugin_id,  # Plugin as actor
            target=stream_id,
        )
        
        # Request was processed (may be denied due to ownership)
        assert result is not None
        assert hasattr(result, 'allowed')
    
    # =========================================================================
    # Test 3: Denial logged and reported to plugin
    # =========================================================================
    
    def test_denial_logged_and_reported_to_plugin(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Denial logged and reported to plugin"""
        plugin = MockPlugin()
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Plugin attempts action on stream it doesn't own
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=plugin.plugin_id,
            target=stream_id,
        )
        
        # Plugin receives denial info
        if not result.allowed:
            plugin.on_denial(result)
            
            assert len(plugin.denials) == 1
            assert plugin.denials[0].allowed is False
            assert plugin.denials[0].reason is not None
        
        # Denial is attested (logged)
        attestations = harness.get_attestations()
        plugin_atts = [a for a in attestations if a.actor == plugin.plugin_id]
        assert len(plugin_atts) > 0


class TestPluginDirectAccessPrevention:
    """Tests for preventing plugin direct access"""
    
    def test_plugin_cannot_directly_change_state(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        runtime: Mock,
        agent: str,
    ):
        """Plugin cannot directly change state"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        plugin = MockPlugin()
        
        # Direct state mutation blocked
        with pytest.raises(RegistrarRequiredError):
            runtime.set_stream_state(stream_id, StreamState.STOPPED)
    
    def test_plugin_cannot_directly_interrupt(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        runtime: Mock,
        agent: str,
    ):
        """Plugin cannot directly interrupt"""
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        plugin = MockPlugin()
        
        with pytest.raises(RegistrarRequiredError):
            runtime.interrupt_audio_direct(stream_id)
    
    def test_plugin_cannot_bypass_ownership_check(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Plugin cannot bypass ownership check"""
        plugin = MockPlugin("malicious_plugin")
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Plugin attempts to interrupt without ownership
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=plugin.plugin_id,
            target=stream_id,
        )
        
        # Denied - plugin doesn't own stream
        assert result.allowed is False


class TestPluginOwnershipRules:
    """Tests for plugin ownership rules"""
    
    def test_plugin_can_control_own_stream(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
    ):
        """Plugin can control stream it creates"""
        plugin = MockPlugin("my_plugin")
        
        # Plugin creates own stream
        stream_id = harness.create_stream(agent_id=plugin.plugin_id)
        harness.advance_stream(stream_id, StreamState.SYNTHESIZING)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Plugin can stop its own stream
        result = registrar.request(
            action=TransitionAction.STOP,
            actor=plugin.plugin_id,
            target=stream_id,
        )
        
        assert result.allowed is True
    
    def test_plugin_cannot_control_agent_stream(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Plugin cannot control agent's stream"""
        plugin = MockPlugin()
        
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Plugin cannot stop agent's stream
        result = registrar.request(
            action=TransitionAction.STOP,
            actor=plugin.plugin_id,
            target=stream_id,
        )
        
        assert result.allowed is False


class TestPluginDenialReporting:
    """Tests for plugin denial reporting"""
    
    def test_plugin_receives_denial_reason(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Plugin receives denial reason"""
        plugin = MockPlugin()
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=plugin.plugin_id,
            target=stream_id,
        )
        
        plugin.on_denial(result)
        
        assert result.reason is not None
        assert len(result.reason) > 0
    
    def test_plugin_denial_attested(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Plugin denial is attested"""
        plugin = MockPlugin("attested_plugin")
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=plugin.plugin_id,
            target=stream_id,
        )
        
        # Denial attested
        attestations = harness.get_attestations()
        denial_atts = [
            a for a in attestations
            if a.actor == plugin.plugin_id and a.decision == "denied"
        ]
        
        assert len(denial_atts) == 1
    
    def test_multiple_plugin_denials_tracked(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
    ):
        """Multiple plugin denials are tracked"""
        plugin = MockPlugin()
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # Multiple denial attempts
        for _ in range(3):
            result = registrar.request(
                action=TransitionAction.INTERRUPT,
                actor=plugin.plugin_id,
                target=stream_id,
            )
            plugin.on_denial(result)
        
        assert len(plugin.denials) == 3
        
        # All attested
        attestations = harness.get_attestations()
        denial_atts = [
            a for a in attestations
            if a.actor == plugin.plugin_id and a.decision == "denied"
        ]
        
        assert len(denial_atts) == 3


class TestPluginAccessibilityOverride:
    """Tests for plugin interaction with accessibility"""
    
    def test_plugin_blocked_by_accessibility_override(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        user: str,
    ):
        """Plugin blocked by accessibility override"""
        plugin = MockPlugin()
        
        # Plugin owns stream
        stream_id = harness.create_stream(agent_id=plugin.plugin_id)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # User enables accessibility override
        registrar.request(
            action=TransitionAction.ENABLE_OVERRIDE,
            actor=user,
            target=stream_id,
        )
        
        # Plugin blocked even on own stream
        result = registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=plugin.plugin_id,
            target=stream_id,
        )
        
        assert result.allowed is False
    
    def test_plugin_cannot_disable_accessibility_override(
        self,
        harness: RegistrumTestHarness,
        registrar: AudioRegistrar,
        agent: str,
        user: str,
    ):
        """Plugin cannot disable accessibility override"""
        plugin = MockPlugin()
        stream_id = harness.create_stream(agent_id=agent)
        harness.advance_stream(stream_id, StreamState.PLAYING)
        
        # User enables override
        registrar.request(
            action=TransitionAction.ENABLE_OVERRIDE,
            actor=user,
            target=stream_id,
        )
        
        # Plugin cannot disable
        result = registrar.request(
            action=TransitionAction.DISABLE_OVERRIDE,
            actor=plugin.plugin_id,
            target=stream_id,
        )
        
        assert result.allowed is False
