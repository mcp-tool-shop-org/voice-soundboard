"""
Audio Registrar — Domain-specific registrar for Voice Soundboard.

This is the main entry point for state management in v2.7.
All meaningful state transitions go through this registrar.

Architecture:
    1. Request comes in (TransitionRequest)
    2. AudioRegistrar validates against domain invariants
    3. AudioRegistrar forwards to RegistrumBridge
    4. RegistrumBridge validates against 11 structural invariants
    5. Decision returned (TransitionResult)
    6. If accepted, effects can be applied

Key principle:
    > Is all meaningful state change mediated, auditable, and replayable?
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from .bridge import RegistrumBridge, RegistrumConfig
from .errors import (
    AccessibilityBypassError,
    InvariantViolationError,
    OwnershipError,
    RegistrarError,
)
from .invariants import DOMAIN_INVARIANTS, DomainInvariant, list_domain_invariants
from .states import AccessibilityState, AudioState, StateID, StreamOwnership, StreamState
from .transitions import (
    AudioTransition,
    DecisionKind,
    Effect,
    InvariantViolation,
    TransitionAction,
    TransitionRequest,
    TransitionResult,
)


@dataclass
class Attestation:
    """
    Record of a registrar decision.
    
    Every request produces an attestation, whether allowed or denied.
    Attestations are immutable once created.
    """
    id: str
    timestamp: datetime
    actor: str
    action: str
    target: str | None
    decision: str  # "allowed" or "denied"
    reason: str
    invariants_checked: list[str]
    accessibility_driven: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "decision": self.decision,
            "reason": self.reason,
            "invariants_checked": self.invariants_checked,
            "accessibility_driven": self.accessibility_driven,
            "metadata": self.metadata,
        }


class AttestationStore:
    """
    Storage for attestations.
    
    Attestations are:
    - Immutable once stored
    - Queryable by various criteria
    - Replayable to reconstruct state
    """
    
    def __init__(self) -> None:
        self._attestations: list[Attestation] = []
    
    def record(self, attestation: Attestation) -> None:
        """Record an attestation (immutable)."""
        self._attestations.append(attestation)
    
    def query(
        self,
        actor: str | None = None,
        action: str | None = None,
        target: str | None = None,
        since: datetime | None = None,
        decision: str | None = None,
    ) -> list[Attestation]:
        """Query attestations by criteria."""
        results = self._attestations
        
        if actor:
            results = [a for a in results if a.actor == actor]
        if action:
            results = [a for a in results if a.action == action]
        if target:
            results = [a for a in results if a.target == target]
        if since:
            results = [a for a in results if a.timestamp >= since]
        if decision:
            results = [a for a in results if a.decision == decision]
        
        return results
    
    def all(self) -> list[Attestation]:
        """Get all attestations."""
        return list(self._attestations)
    
    def count(self) -> int:
        """Get attestation count."""
        return len(self._attestations)


class AudioRegistrar:
    """
    The Audio Registrar — single authority for audio state transitions.
    
    This class:
    1. Validates transitions against domain invariants
    2. Forwards to Registrum for structural validation
    3. Records attestations for all decisions
    4. Provides replay capability
    
    Usage:
        registrar = AudioRegistrar()
        
        # Request a transition
        result = registrar.request(
            action="start",
            actor="agent_1",
            target="stream_1",
        )
        
        if result.allowed:
            runtime.apply(result)
        else:
            log.info(f"Denied: {result.reason}")
    """
    
    def __init__(
        self,
        config: RegistrumConfig | None = None,
        domain_invariants: list[DomainInvariant] | None = None,
    ) -> None:
        self.config = config or RegistrumConfig()
        self._bridge = RegistrumBridge(self.config)
        self._states: dict[StateID, AudioState] = {}
        self._attestation_store = AttestationStore()
        self._domain_invariants = domain_invariants or list(DOMAIN_INVARIANTS)
    
    @property
    def attestation_store(self) -> AttestationStore:
        """Access to attestation store."""
        return self._attestation_store
    
    def request(
        self,
        action: str | TransitionAction,
        actor: str,
        target: StateID | None = None,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TransitionResult:
        """
        Request a state transition.
        
        This is the main entry point for all state changes.
        
        Args:
            action: The transition action (e.g., "start", "interrupt")
            actor: The agent or system requesting the transition
            target: Target stream ID (None for new streams)
            reason: Human-readable reason for the transition
            metadata: Additional metadata for the transition
            
        Returns:
            TransitionResult with decision (allowed/denied) and details
        """
        # Normalize action
        if isinstance(action, str):
            action = TransitionAction(action)
        
        # Create request
        request = TransitionRequest(
            action=action,
            actor=actor,
            target=target,
            reason=reason,
            metadata=metadata or {},
        )
        
        # Build proposed state
        current_state = self._states.get(target) if target else None
        proposed_state = self._build_proposed_state(request, current_state)
        
        # Create transition
        transition = AudioTransition(
            from_state_id=target if target and target in self._states else None,
            to_state=proposed_state,
            request=request,
        )
        
        # Check domain invariants first
        domain_violations = self._check_domain_invariants(transition)
        
        if domain_violations:
            # Domain invariants failed
            result = TransitionResult(
                kind=DecisionKind.REJECTED,
                request=request,
                violations=domain_violations,
            )
        else:
            # Forward to Registrum for structural validation
            result = self._bridge.register(transition)
        
        # Check for accessibility-driven decision
        result.accessibility_driven = self._is_accessibility_driven(request, current_state)
        
        # Record attestation
        attestation = Attestation(
            id=result.attestation_id,
            timestamp=result.timestamp,
            actor=actor,
            action=action.value,
            target=target,
            decision="allowed" if result.allowed else "denied",
            reason=result.reason,
            invariants_checked=result.applied_invariants + [v.invariant_id for v in result.violations],
            accessibility_driven=result.accessibility_driven,
            metadata=request.metadata,
        )
        self._attestation_store.record(attestation)
        
        # Update internal state on acceptance
        if result.allowed:
            self._states[proposed_state.stream_id] = proposed_state
        
        return result
    
    def _build_proposed_state(
        self,
        request: TransitionRequest,
        current: AudioState | None,
    ) -> AudioState:
        """Build the proposed new state for a transition."""
        if current is None:
            # New stream - apply the action to compute initial state
            initial_state = self._compute_new_state(request.action, StreamState.IDLE)
            return AudioState(
                stream_id=request.target or str(uuid4()),
                state=initial_state,
                ownership=StreamOwnership(
                    stream_id=request.target or str(uuid4()),
                    session_id=request.metadata.get("session_id", "default"),
                    agent_id=request.actor,
                    priority=request.metadata.get("priority", 5),
                ),
            )
        
        # Transition existing stream
        new_state = self._compute_new_state(request.action, current.state)
        
        # Handle accessibility state updates
        new_accessibility = self._compute_accessibility_state(
            request.action, current.accessibility, request.metadata
        )
        
        return AudioState(
            stream_id=current.stream_id,
            state=new_state,
            ownership=current.ownership,
            accessibility=new_accessibility,
            parent_state_id=current.stream_id,
            version=current.version + 1,
        )
    
    def _compute_accessibility_state(
        self,
        action: TransitionAction,
        current: AccessibilityState,
        metadata: dict[str, Any],
    ) -> AccessibilityState:
        """Compute new accessibility state based on action."""
        if action == TransitionAction.ENABLE_OVERRIDE:
            return AccessibilityState(
                speech_rate_override=metadata.get("speech_rate", current.speech_rate_override),
                pause_amplification=metadata.get("pause_amplification", current.pause_amplification),
                forced_captions=metadata.get("forced_captions", current.forced_captions),
                override_scope=metadata.get("scope", current.override_scope),
                override_active=True,
            )
        elif action == TransitionAction.DISABLE_OVERRIDE:
            return AccessibilityState(
                speech_rate_override=current.speech_rate_override,
                pause_amplification=current.pause_amplification,
                forced_captions=current.forced_captions,
                override_scope=current.override_scope,
                override_active=False,
            )
        elif action == TransitionAction.UPDATE_OVERRIDE:
            return AccessibilityState(
                speech_rate_override=metadata.get("speech_rate", current.speech_rate_override),
                pause_amplification=metadata.get("pause_amplification", current.pause_amplification),
                forced_captions=metadata.get("forced_captions", current.forced_captions),
                override_scope=metadata.get("scope", current.override_scope),
                override_active=current.override_active,
            )
        # Non-accessibility actions preserve current state
        return current
    
    def _compute_new_state(
        self,
        action: TransitionAction,
        current: StreamState,
    ) -> StreamState:
        """Compute new state based on action."""
        state_map = {
            TransitionAction.START: StreamState.COMPILING,
            TransitionAction.COMPILE: StreamState.SYNTHESIZING,
            TransitionAction.SYNTHESIZE: StreamState.PLAYING,
            TransitionAction.PLAY: StreamState.PLAYING,
            TransitionAction.INTERRUPT: StreamState.INTERRUPTING,
            TransitionAction.STOP: StreamState.STOPPED,
            TransitionAction.FAIL: StreamState.FAILED,
            TransitionAction.RESTART: StreamState.IDLE,
        }
        return state_map.get(action, current)
    
    def _check_domain_invariants(
        self,
        transition: AudioTransition,
    ) -> list[InvariantViolation]:
        """Check all domain invariants."""
        violations = []
        
        for invariant in self._domain_invariants:
            inv_violations = invariant.check(transition, self._states)
            violations.extend(inv_violations)
            
            # Check for HALT-level violations
            for v in inv_violations:
                if v.classification == "HALT":
                    # HALT violations are critical
                    if invariant.id == "audio.accessibility.supremacy":
                        raise AccessibilityBypassError(
                            message=v.message,
                            stream_id=transition.request.target,
                            bypass_type="invariant_violation",
                        )
        
        return violations
    
    def _is_accessibility_driven(
        self,
        request: TransitionRequest,
        current: AudioState | None,
    ) -> bool:
        """Check if this transition is accessibility-driven."""
        # Explicit accessibility actions
        accessibility_actions = {
            TransitionAction.ENABLE_OVERRIDE,
            TransitionAction.DISABLE_OVERRIDE,
            TransitionAction.UPDATE_OVERRIDE,
        }
        if request.action in accessibility_actions:
            return True
        
        # Interrupt via accessibility override
        if request.action == TransitionAction.INTERRUPT:
            if current and current.accessibility.override_active:
                return True
        
        return False
    
    def get_state(self, stream_id: StateID) -> AudioState | None:
        """Get current state for a stream.
        
        Returns a copy to prevent direct mutation of registrar state.
        """
        state = self._states.get(stream_id)
        return deepcopy(state) if state else None
    
    def list_states(self) -> dict[StateID, AudioState]:
        """Get all current states.
        
        Returns copies to prevent direct mutation.
        """
        return {k: deepcopy(v) for k, v in self._states.items()}
    
    def snapshot(self) -> dict[str, Any]:
        """
        Create a snapshot of the registrar state.
        
        The snapshot can be used to:
        - Save state to disk
        - Transfer state to another instance
        - Debug state issues
        """
        return {
            "version": "2.7.0",
            "timestamp": datetime.utcnow().isoformat(),
            "states": {
                sid: state.to_registrum_state()
                for sid, state in self._states.items()
            },
            "attestation_count": self._attestation_store.count(),
            "registrum_snapshot": self._bridge.snapshot(),
        }
    
    def replay(self, attestations: list[dict[str, Any]]) -> "AudioRegistrar":
        """
        Replay attestations to reconstruct state.
        
        This is used for:
        - Debugging ("why did this happen?")
        - Recovery
        - Testing determinism
        
        Args:
            attestations: List of attestation dicts to replay
            
        Returns:
            New AudioRegistrar with replayed state
        """
        new_registrar = AudioRegistrar(
            config=self.config,
            domain_invariants=self._domain_invariants,
        )
        
        for att in attestations:
            if att.get("decision") == "allowed":
                # Replay the accepted transition
                action = att.get("action", "start")
                actor = att.get("actor", "system")
                target = att.get("target")
                
                new_registrar.request(
                    action=action,
                    actor=actor,
                    target=target,
                    metadata=att.get("metadata", {}),
                )
        
        return new_registrar
    
    def list_invariants(self) -> list[dict[str, Any]]:
        """
        List all active invariants.
        
        Returns both:
        - Registrum's 11 structural invariants
        - Voice Soundboard's domain invariants
        """
        structural = self._bridge.list_invariants()
        domain = list_domain_invariants()
        return structural + domain
    
    def observe(
        self,
        action: str,
        actor: str,
        target: StateID | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """
        Observe a state change without enforcing (shadow mode).
        
        Used during migration to validate that transitions
        would have been allowed/denied correctly.
        
        Args:
            action: The action that occurred
            actor: The actor that performed it
            target: Target stream
            meta: Additional metadata
        """
        # In shadow mode, we record but don't enforce
        attestation = Attestation(
            id=str(uuid4()),
            timestamp=datetime.utcnow(),
            actor=actor,
            action=action,
            target=target,
            decision="observed",
            reason="Shadow mode - not enforced",
            invariants_checked=[],
            metadata=meta or {},
        )
        self._attestation_store.record(attestation)
