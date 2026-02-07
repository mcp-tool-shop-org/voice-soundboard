"""
Domain Invariants — Layered on Registrum's 11 Structural Invariants

Registrum provides 11 structural invariants:
    Identity (3):
        - state.identity.immutable
        - state.identity.explicit
        - state.identity.unique
    Lineage (4):
        - state.lineage.explicit
        - state.lineage.parent_exists
        - state.lineage.single_parent
        - state.lineage.continuous
    Ordering (4):
        - ordering.total
        - ordering.monotonic
        - ordering.gap_free
        - ordering.deterministic

Voice Soundboard adds domain-specific invariants:
    Ownership:
        - audio.ownership.single_owner
        - audio.ownership.required_for_interrupt
    Accessibility:
        - audio.accessibility.supremacy
        - audio.accessibility.auditable
    Lifecycle:
        - audio.lifecycle.no_dead_interrupt
        - audio.lifecycle.commit_boundary
    Plugin:
        - audio.plugin.immutability

These domain invariants are evaluated AFTER Registrum's structural
invariants pass. Both must pass for a transition to be accepted.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from .states import AudioState, StreamState, is_valid_transition
from .transitions import AudioTransition, InvariantViolation, TransitionAction


@runtime_checkable
class DomainInvariant(Protocol):
    """
    Protocol for domain-specific invariants.
    
    Each invariant:
    - Has a unique ID (namespaced: audio.*)
    - Has a description
    - Checks a condition
    - Returns violations on failure
    """
    
    @property
    def id(self) -> str:
        """Unique invariant identifier (e.g., 'audio.ownership.single_owner')."""
        ...
    
    @property
    def description(self) -> str:
        """Human-readable description of what this invariant enforces."""
        ...
    
    @property
    def failure_mode(self) -> Literal["reject", "halt"]:
        """What happens on violation: reject (continue) or halt (stop system)."""
        ...
    
    def check(
        self,
        transition: AudioTransition,
        current_states: dict[str, AudioState],
    ) -> list[InvariantViolation]:
        """
        Check if the invariant holds for this transition.
        
        Args:
            transition: The proposed transition
            current_states: Map of all currently registered states
            
        Returns:
            Empty list if invariant holds, list of violations otherwise
        """
        ...


@dataclass
class BaseInvariant(ABC):
    """Base class for domain invariants with common functionality."""
    
    @property
    @abstractmethod
    def id(self) -> str:
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        ...
    
    @property
    def failure_mode(self) -> Literal["reject", "halt"]:
        return "reject"  # Default to reject, not halt
    
    @abstractmethod
    def check(
        self,
        transition: AudioTransition,
        current_states: dict[str, AudioState],
    ) -> list[InvariantViolation]:
        ...
    
    def _violation(
        self,
        message: str,
        classification: Literal["REJECT", "HALT"] | None = None,
    ) -> InvariantViolation:
        """Helper to create a violation for this invariant."""
        if classification is None:
            classification = "HALT" if self.failure_mode == "halt" else "REJECT"
        return InvariantViolation(
            invariant_id=self.id,
            classification=classification,
            message=message,
        )


# =============================================================================
# Ownership Invariants
# =============================================================================

@dataclass
class SingleOwnerInvariant(BaseInvariant):
    """
    INV-1: Only one active owner per stream.
    
    A stream cannot have multiple simultaneous owners.
    Ownership transfer requires explicit release + claim.
    """
    
    @property
    def id(self) -> str:
        return "audio.ownership.single_owner"
    
    @property
    def description(self) -> str:
        return "Only one active owner per stream"
    
    def check(
        self,
        transition: AudioTransition,
        current_states: dict[str, AudioState],
    ) -> list[InvariantViolation]:
        # Only applies to ownership claim actions
        if transition.request.action != TransitionAction.CLAIM:
            return []
        
        # Check if target stream already has an owner
        target_id = transition.request.target
        if target_id and target_id in current_states:
            current = current_states[target_id]
            if current.ownership is not None:
                # Stream already has an owner
                current_owner = current.ownership.agent_id
                requesting_agent = transition.request.actor
                if current_owner != requesting_agent:
                    return [self._violation(
                        f"Stream {target_id} already owned by {current_owner}, "
                        f"cannot be claimed by {requesting_agent}"
                    )]
        
        return []


@dataclass  
class OwnershipRequiredInvariant(BaseInvariant):
    """
    Ownership is required to control a stream (interrupt or stop).
    
    Only the owner (or an accessibility override owner) can interrupt or stop a stream.
    Non-owners are always denied, regardless of 'interruptible' flag.
    The 'interruptible' flag controls higher-priority agent interruption, 
    but that's handled separately.
    """
    
    # Actions that require ownership
    OWNERSHIP_REQUIRED_ACTIONS = {
        TransitionAction.INTERRUPT,
        TransitionAction.STOP,
    }
    
    @property
    def id(self) -> str:
        return "audio.ownership.required_for_control"
    
    @property
    def description(self) -> str:
        return "Ownership required to control stream (unless accessibility override)"
    
    def check(
        self,
        transition: AudioTransition,
        current_states: dict[str, AudioState],
    ) -> list[InvariantViolation]:
        # Only applies to ownership-controlled actions
        if transition.request.action not in self.OWNERSHIP_REQUIRED_ACTIONS:
            return []
        
        target_id = transition.request.target
        if not target_id or target_id not in current_states:
            return []
        
        current = current_states[target_id]
        requesting_agent = transition.request.actor
        action_name = transition.request.action.value
        
        # Check accessibility override (takes precedence)
        # User-initiated accessibility override can control stream
        if current.accessibility.override_active:
            if requesting_agent.startswith("user_"):
                return []  # User can control with accessibility override
        
        # Check ownership - non-owner is ALWAYS denied
        if current.ownership is None:
            return [self._violation(
                f"Stream {target_id} has no owner, cannot be {action_name}ed"
            )]
        
        if current.ownership.agent_id != requesting_agent:
            return [self._violation(
                f"Only owner ({current.ownership.agent_id}) can {action_name} stream {target_id}, not {requesting_agent}"
            )]
        
        return []


# =============================================================================
# Accessibility Invariants
# =============================================================================

@dataclass
class AccessibilitySupremacyInvariant(BaseInvariant):
    """
    INV-4: Accessibility overrides always win over agent intent.
    
    This invariant has both REJECT and HALT-level behaviors:
    - Agent interrupts when override active: REJECT (normal blocking)
    - Silent override disable: HALT (critical safety violation)
    - Silent override modification: REJECT (normal blocking)
    
    When an accessibility override is active:
    1. The override cannot be silently disabled
    2. Override values cannot be silently modified
    3. Agent interrupts are blocked (only override owner can interrupt)
    """
    
    @property
    def id(self) -> str:
        return "audio.accessibility.supremacy"
    
    @property
    def description(self) -> str:
        return "Accessibility overrides cannot be silently ignored"
    
    @property
    def failure_mode(self) -> Literal["reject", "halt"]:
        return "halt"  # Default is HALT for most violations
    
    def check(
        self,
        transition: AudioTransition,
        current_states: dict[str, AudioState],
    ) -> list[InvariantViolation]:
        target_id = transition.request.target
        if not target_id or target_id not in current_states:
            return []
        
        current = current_states[target_id]
        proposed = transition.to_state
        actor = transition.request.actor
        metadata = transition.request.metadata
        
        # Non-users (plugins/agents) cannot disable accessibility overrides
        # This protects against plugins circumventing accessibility controls
        if transition.request.action == TransitionAction.DISABLE_OVERRIDE:
            if not actor.startswith("user_"):
                return [self._violation(
                    f"Agent/plugin {actor} cannot disable accessibility override on stream {target_id}. "
                    "Only users can disable accessibility overrides.",
                    classification="REJECT",
                )]
        
        # If accessibility override is active, enforce supremacy
        if current.accessibility.override_active:
            # Block agent interrupts when accessibility override is active
            # This is a REJECT (normal blocking), not a HALT (safety violation)
            if transition.request.action == TransitionAction.INTERRUPT:
                # Check if this is an accessibility-driven interrupt (from override owner)
                # Non-user actors (agents) are blocked
                
                # Allow if the actor is the user who owns the override
                # Otherwise, block the interrupt
                if not actor.startswith("user_") and not metadata.get("override_owner"):
                    return [self._violation(
                        f"Agent {actor} cannot interrupt stream {target_id} while accessibility "
                        "override is active. Only the override owner can interrupt.",
                        classification="REJECT",  # Normal rejection, not a safety halt
                    )]
            
            # Check that proposed state doesn't silently disable override
            # This is a HALT-level violation (safety critical)
            if not proposed.accessibility.override_active:
                # Override was disabled — is this an explicit action?
                if transition.request.action != TransitionAction.DISABLE_OVERRIDE:
                    return [self._violation(
                        f"Accessibility override silently disabled on stream {target_id}. "
                        "Must use explicit DISABLE_OVERRIDE action.",
                        classification="HALT",  # Critical safety violation
                    )]
            
            # Check that override values aren't silently modified
            # This is a REJECT (could be accidental), not HALT
            if transition.request.action not in {
                TransitionAction.UPDATE_OVERRIDE,
                TransitionAction.DISABLE_OVERRIDE,
            }:
                current_rate = current.accessibility.speech_rate_override
                proposed_rate = proposed.accessibility.speech_rate_override
                if current_rate != proposed_rate:
                    return [self._violation(
                        f"Speech rate override silently changed from {current_rate} to {proposed_rate}. "
                        "Must use explicit UPDATE_OVERRIDE action.",
                        classification="REJECT",
                    )]
        
        return []


@dataclass
class AccessibilityAuditableInvariant(BaseInvariant):
    """
    All accessibility state changes must be auditable.
    
    Accessibility transitions must produce attestations that
    are explicitly marked as accessibility-driven.
    """
    
    @property
    def id(self) -> str:
        return "audio.accessibility.auditable"
    
    @property
    def description(self) -> str:
        return "All accessibility changes must be registered transitions"
    
    def check(
        self,
        transition: AudioTransition,
        current_states: dict[str, AudioState],
    ) -> list[InvariantViolation]:
        # This invariant is checked at registration time
        # to ensure accessibility changes come through proper channels
        accessibility_actions = {
            TransitionAction.ENABLE_OVERRIDE,
            TransitionAction.DISABLE_OVERRIDE,
            TransitionAction.UPDATE_OVERRIDE,
        }
        
        target_id = transition.request.target
        if target_id and target_id in current_states:
            current = current_states[target_id]
            proposed = transition.to_state
            
            # Check if accessibility state changed
            current_a11y = current.accessibility
            proposed_a11y = proposed.accessibility
            
            a11y_changed = (
                current_a11y.override_active != proposed_a11y.override_active or
                current_a11y.speech_rate_override != proposed_a11y.speech_rate_override or
                current_a11y.pause_amplification != proposed_a11y.pause_amplification or
                current_a11y.forced_captions != proposed_a11y.forced_captions
            )
            
            if a11y_changed and transition.request.action not in accessibility_actions:
                return [self._violation(
                    f"Accessibility state changed without explicit accessibility action. "
                    f"Action was '{transition.request.action.value}', expected one of: "
                    f"{[a.value for a in accessibility_actions]}"
                )]
        
        return []


# =============================================================================
# Lifecycle Invariants
# =============================================================================

@dataclass
class NoDeadInterruptInvariant(BaseInvariant):
    """
    INV-2: Cannot interrupt a stopped stream.
    
    Interrupting a stream that's already stopped is a logic error.
    """
    
    @property
    def id(self) -> str:
        return "audio.lifecycle.no_dead_interrupt"
    
    @property
    def description(self) -> str:
        return "Cannot interrupt a stopped stream"
    
    def check(
        self,
        transition: AudioTransition,
        current_states: dict[str, AudioState],
    ) -> list[InvariantViolation]:
        if transition.request.action != TransitionAction.INTERRUPT:
            return []
        
        target_id = transition.request.target
        if not target_id or target_id not in current_states:
            return [self._violation(
                f"Cannot interrupt non-existent stream: {target_id}"
            )]
        
        current = current_states[target_id]
        terminal_states = {StreamState.STOPPED, StreamState.FAILED}
        
        if current.state in terminal_states:
            return [self._violation(
                f"Cannot interrupt stream {target_id} in state {current.state.value}"
            )]
        
        return []


@dataclass
class CommitBoundaryInvariant(BaseInvariant):
    """
    INV-3: Cannot rollback past commit boundary.
    
    Once a graph is committed, it cannot be rolled back.
    This ensures deterministic behavior.
    """
    
    @property
    def id(self) -> str:
        return "audio.lifecycle.commit_boundary"
    
    @property
    def description(self) -> str:
        return "Cannot rollback past commit boundary"
    
    def check(
        self,
        transition: AudioTransition,
        current_states: dict[str, AudioState],
    ) -> list[InvariantViolation]:
        if transition.request.action != TransitionAction.ROLLBACK:
            return []
        
        # Check if the rollback target is before a commit
        rollback_target = transition.request.metadata.get("rollback_to_order_index")
        if rollback_target is None:
            return []
        
        # Find the last commit index
        target_id = transition.request.target
        if target_id and target_id in current_states:
            last_commit = transition.request.metadata.get("last_commit_index", 0)
            if rollback_target < last_commit:
                return [self._violation(
                    f"Cannot rollback to index {rollback_target}, "
                    f"which is before last commit at index {last_commit}"
                )]
        
        return []


@dataclass
class ValidTransitionInvariant(BaseInvariant):
    """
    Stream state transitions must follow valid paths.
    
    Not all state transitions are allowed. For example,
    IDLE cannot directly transition to PLAYING (must compile first).
    
    Accessibility actions (ENABLE_OVERRIDE, DISABLE_OVERRIDE, UPDATE_OVERRIDE)
    are exempt from state transition validation since they only modify
    accessibility state, not stream lifecycle state.
    """
    
    # Accessibility actions that don't change stream state
    ACCESSIBILITY_ACTIONS = {
        TransitionAction.ENABLE_OVERRIDE,
        TransitionAction.DISABLE_OVERRIDE,
        TransitionAction.UPDATE_OVERRIDE,
    }
    
    @property
    def id(self) -> str:
        return "audio.lifecycle.valid_transition"
    
    @property
    def description(self) -> str:
        return "State transitions must follow valid paths"
    
    def check(
        self,
        transition: AudioTransition,
        current_states: dict[str, AudioState],
    ) -> list[InvariantViolation]:
        target_id = transition.request.target
        
        # Accessibility actions don't change stream state, so skip validation
        if transition.request.action in self.ACCESSIBILITY_ACTIONS:
            return []
        
        # New streams: START action is allowed (IDLE -> COMPILING is valid)
        if not target_id or target_id not in current_states:
            # For new streams, check if the initial transition is valid
            # START from implicit IDLE to COMPILING is the canonical path
            if transition.request.action == TransitionAction.START:
                if transition.to_state.state == StreamState.COMPILING:
                    return []  # Valid start
            # Any other action on new stream should start from IDLE
            if transition.to_state.state != StreamState.IDLE:
                return [self._violation(
                    f"New stream must start in IDLE state, not {transition.to_state.state.value}"
                )]
            return []
        
        current = current_states[target_id]
        from_state = current.state
        to_state = transition.to_state.state
        
        if not is_valid_transition(from_state, to_state):
            return [self._violation(
                f"Invalid transition from {from_state.value} to {to_state.value}"
            )]
        
        return []


# =============================================================================
# Plugin Invariants
# =============================================================================

@dataclass
class PluginImmutabilityInvariant(BaseInvariant):
    """
    INV-5: Plugins cannot mutate committed graphs.
    
    Once a graph is committed (passed compilation), plugins
    cannot modify it. They can only add new processing steps.
    """
    
    @property
    def id(self) -> str:
        return "audio.plugin.immutability"
    
    @property
    def description(self) -> str:
        return "Plugins cannot mutate committed graphs"
    
    def check(
        self,
        transition: AudioTransition,
        current_states: dict[str, AudioState],
    ) -> list[InvariantViolation]:
        if transition.request.action != TransitionAction.MUTATE_GRAPH:
            return []
        
        target_id = transition.request.target
        if not target_id or target_id not in current_states:
            return []
        
        current = current_states[target_id]
        
        # Check if the stream is past compilation (committed)
        committed_states = {
            StreamState.SYNTHESIZING,
            StreamState.PLAYING,
            StreamState.INTERRUPTING,
        }
        
        if current.state in committed_states:
            return [self._violation(
                f"Cannot mutate graph for stream {target_id} in committed state {current.state.value}"
            )]
        
        return []


# =============================================================================
# Invariant Registry
# =============================================================================

# All domain invariants
DOMAIN_INVARIANTS: list[DomainInvariant] = [
    # Ownership
    SingleOwnerInvariant(),
    OwnershipRequiredInvariant(),
    # Accessibility
    AccessibilitySupremacyInvariant(),
    AccessibilityAuditableInvariant(),
    # Lifecycle
    NoDeadInterruptInvariant(),
    CommitBoundaryInvariant(),
    ValidTransitionInvariant(),
    # Plugin
    PluginImmutabilityInvariant(),
]


def get_domain_invariant(invariant_id: str) -> DomainInvariant | None:
    """Get a domain invariant by ID."""
    for inv in DOMAIN_INVARIANTS:
        if inv.id == invariant_id:
            return inv
    return None


def list_domain_invariants() -> list[dict[str, Any]]:
    """List all domain invariants with their metadata."""
    return [
        {
            "id": inv.id,
            "description": inv.description,
            "failure_mode": inv.failure_mode,
        }
        for inv in DOMAIN_INVARIANTS
    ]
