"""
Audio Transitions — Mapped to Registrum Transition Structure

Registrum's Transition model:
    {
        from: StateID | null,   # Parent state (null for root)
        to: State,              # Proposed new state
        metadata?: {...}        # Structural metadata only
    }

Voice Soundboard maps audio transitions to this model:
    - from: previous stream state ID (or null for new stream)
    - to: proposed new AudioState
    - metadata: action, actor, reason, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from .states import AudioState, StateID


class TransitionAction(Enum):
    """
    Audio-specific transition actions.
    
    These map to state changes that Registrum validates.
    """
    # Stream lifecycle
    START = "start"
    COMPILE = "compile"
    SYNTHESIZE = "synthesize"
    PLAY = "play"
    INTERRUPT = "interrupt"
    STOP = "stop"
    FAIL = "fail"
    RESTART = "restart"
    
    # Ownership
    CLAIM = "claim"
    RELEASE = "release"
    TRANSFER = "transfer"
    
    # Accessibility
    ENABLE_OVERRIDE = "enable_override"
    DISABLE_OVERRIDE = "disable_override"
    UPDATE_OVERRIDE = "update_override"
    
    # Plugin
    MUTATE_GRAPH = "mutate_graph"
    COMMIT = "commit"
    ROLLBACK = "rollback"


@dataclass(frozen=True)
class TransitionRequest:
    """
    Request for a state transition.
    
    This is submitted to the registrar, which decides whether
    to allow or deny the transition based on invariants.
    """
    action: TransitionAction
    actor: str  # Agent or system ID requesting the transition
    target: StateID | None = None  # Stream ID (None for new stream)
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Request tracking
    request_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_registrum_metadata(self) -> dict[str, Any]:
        """Convert to Registrum transition metadata."""
        return {
            "action": self.action.value,
            "actor": self.actor,
            "reason": self.reason,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            **self.metadata,
        }


@dataclass
class AudioTransition:
    """
    A complete audio transition — maps to Registrum Transition.
    
    This represents a proposed change from one AudioState to another.
    The registrar validates this against all invariants before allowing it.
    
    Registrum mapping:
        from     -> from_state_id
        to       -> to_state (as Registrum State)
        metadata -> request metadata
    """
    from_state_id: StateID | None
    to_state: AudioState
    request: TransitionRequest
    
    def to_registrum_transition(self) -> dict[str, Any]:
        """
        Convert to Registrum Transition format.
        
        Returns:
            {
                from: StateID | null,
                to: State,
                metadata: {...}
            }
        """
        return {
            "from": self.from_state_id,
            "to": self.to_state.to_registrum_state(),
            "metadata": self.request.to_registrum_metadata(),
        }


class DecisionKind(Enum):
    """Registrar decision outcomes."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass
class InvariantViolation:
    """
    Record of an invariant violation.
    
    Maps directly to Registrum's InvariantViolation structure.
    """
    invariant_id: str
    classification: Literal["REJECT", "HALT"]
    message: str
    
    @classmethod
    def from_registrum(cls, data: dict[str, Any]) -> InvariantViolation:
        return cls(
            invariant_id=data["invariantId"],
            classification=data.get("classification", "REJECT"),
            message=data.get("message", ""),
        )


@dataclass
class TransitionResult:
    """
    Result of a transition request — decision from registrar.
    
    Maps to Registrum's RegistrationResult:
        - Accepted: {kind: "accepted", stateId, orderIndex, appliedInvariants}
        - Rejected: {kind: "rejected", violations}
    """
    kind: DecisionKind
    request: TransitionRequest
    
    # On acceptance
    state_id: StateID | None = None
    order_index: int | None = None
    applied_invariants: list[str] = field(default_factory=list)
    
    # On rejection
    violations: list[InvariantViolation] = field(default_factory=list)
    
    # Always present
    attestation_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Domain-specific
    accessibility_driven: bool = False
    
    @property
    def allowed(self) -> bool:
        """Convenience property for checking if transition was allowed."""
        return self.kind == DecisionKind.ACCEPTED
    
    @property
    def denied(self) -> bool:
        """Convenience property for checking if transition was denied."""
        return self.kind == DecisionKind.REJECTED
    
    @property
    def reason(self) -> str:
        """Human-readable reason for the decision."""
        if self.allowed:
            return f"Transition accepted, registered as {self.state_id}"
        else:
            violation_msgs = [v.message for v in self.violations]
            return f"Transition denied: {'; '.join(violation_msgs)}"
    
    @classmethod
    def from_registrum_result(
        cls,
        registrum_result: dict[str, Any],
        request: TransitionRequest,
    ) -> TransitionResult:
        """
        Create TransitionResult from Registrum RegistrationResult.
        
        Args:
            registrum_result: Registrum result dict
            request: Original transition request
            
        Returns:
            TransitionResult instance
        """
        kind = DecisionKind.ACCEPTED if registrum_result["kind"] == "accepted" else DecisionKind.REJECTED
        
        violations = []
        if kind == DecisionKind.REJECTED:
            violations = [
                InvariantViolation.from_registrum(v)
                for v in registrum_result.get("violations", [])
            ]
        
        return cls(
            kind=kind,
            request=request,
            state_id=registrum_result.get("stateId"),
            order_index=registrum_result.get("orderIndex"),
            applied_invariants=registrum_result.get("appliedInvariants", []),
            violations=violations,
        )


@dataclass
class Effect:
    """
    An effect to be applied after a successful transition.
    
    Effects are only applied if the transition is accepted.
    They represent the actual runtime changes (playing audio, etc.)
    that happen as a result of the state change.
    """
    effect_type: str
    target: str
    parameters: dict[str, Any] = field(default_factory=dict)
    
    # Effect tracking
    effect_id: str = field(default_factory=lambda: str(uuid4()))
    applied: bool = False
    applied_at: datetime | None = None
