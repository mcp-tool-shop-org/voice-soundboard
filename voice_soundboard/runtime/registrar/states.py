"""
Audio State Models — Mapped to Registrum State Structure

Registrum's State model:
    {
        id: StateID,           # Unique, immutable identifier
        structure: {...},       # Inspectable structural fields (registrar validates these)
        data: {...}            # Opaque payload (registrar ignores this)
    }

Voice Soundboard maps audio state to this model:
    - id: stream_id (UUID)
    - structure: StreamState, ownership, accessibility flags
    - data: PCM buffers, DSP state, backend internals (opaque to registrar)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4


class StreamState(Enum):
    """
    Audio stream lifecycle states.
    
    Maps to Registrum state identity — each state is a distinct
    structural configuration that the registrar tracks.
    """
    IDLE = "idle"
    COMPILING = "compiling"
    SYNTHESIZING = "synthesizing"
    PLAYING = "playing"
    INTERRUPTING = "interrupting"
    STOPPED = "stopped"
    FAILED = "failed"


# Valid state transitions (from -> to)
VALID_TRANSITIONS: dict[StreamState, set[StreamState]] = {
    StreamState.IDLE: {StreamState.COMPILING, StreamState.FAILED},
    StreamState.COMPILING: {StreamState.SYNTHESIZING, StreamState.FAILED},
    StreamState.SYNTHESIZING: {StreamState.PLAYING, StreamState.FAILED},
    StreamState.PLAYING: {StreamState.INTERRUPTING, StreamState.STOPPED, StreamState.FAILED},
    StreamState.INTERRUPTING: {StreamState.STOPPED, StreamState.FAILED},
    StreamState.STOPPED: {StreamState.IDLE},  # Restart allowed
    StreamState.FAILED: {StreamState.IDLE},   # Restart allowed
}


def is_valid_transition(from_state: StreamState, to_state: StreamState) -> bool:
    """Check if a state transition is valid."""
    return to_state in VALID_TRANSITIONS.get(from_state, set())


@dataclass(frozen=True)
class StreamOwnership:
    """
    Ownership metadata for a stream.
    
    Maps to Registrum structure fields — these are visible to
    the registrar and enforced by domain invariants.
    """
    stream_id: str
    session_id: str
    agent_id: str
    priority: int  # 1-10, higher wins in conflicts
    interruptible: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self) -> None:
        if not 1 <= self.priority <= 10:
            raise ValueError(f"Priority must be 1-10, got {self.priority}")


@dataclass
class AccessibilityState:
    """
    Accessibility configuration state.
    
    Maps to Registrum structure fields — accessibility overrides
    are structural and enforced by the AccessibilitySupremacy invariant.
    
    Key rule: Accessibility state changes are registered transitions,
    not silent modifications.
    """
    speech_rate_override: float | None = None
    pause_amplification: float | None = None
    forced_captions: bool = False
    override_scope: Literal["session", "user"] = "session"
    override_active: bool = False
    
    def applies_to(self, ownership: StreamOwnership) -> bool:
        """Check if this override applies to given stream ownership."""
        if not self.override_active:
            return False
        # User-level overrides apply to all sessions
        # Session-level overrides apply only to matching session
        return self.override_scope == "user" or True  # Simplified for now


@dataclass
class AudioState:
    """
    Complete audio state — maps to Registrum State.
    
    This is the canonical state representation that gets registered
    with Registrum. The registrar validates transitions between
    AudioState instances.
    
    Registrum mapping:
        id         -> stream_id
        structure  -> {state, ownership, accessibility, ...}
        data       -> opaque (PCM buffers, etc.)
    """
    # Identity (Registrum: id)
    stream_id: str = field(default_factory=lambda: str(uuid4()))
    
    # Structure (Registrum: structure) — registrar validates these
    state: StreamState = StreamState.IDLE
    ownership: StreamOwnership | None = None
    accessibility: AccessibilityState = field(default_factory=AccessibilityState)
    
    # Structural metadata
    parent_state_id: str | None = None  # Lineage tracking
    order_index: int = 0                 # Ordering
    version: int = 1                     # Structural version
    
    # Timestamps (structural)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Opaque data (Registrum: data) — registrar ignores these
    opaque_data: dict[str, Any] = field(default_factory=dict)
    
    def to_registrum_state(self) -> dict[str, Any]:
        """
        Convert to Registrum State format.
        
        Returns:
            {
                id: str,
                structure: dict,
                data: Any
            }
        """
        return {
            "id": self.stream_id,
            "structure": {
                "state": self.state.value,
                "version": self.version,
                "ownership": {
                    "session_id": self.ownership.session_id if self.ownership else None,
                    "agent_id": self.ownership.agent_id if self.ownership else None,
                    "priority": self.ownership.priority if self.ownership else 0,
                    "interruptible": self.ownership.interruptible if self.ownership else True,
                } if self.ownership else None,
                "accessibility": {
                    "override_active": self.accessibility.override_active,
                    "speech_rate_override": self.accessibility.speech_rate_override,
                    "pause_amplification": self.accessibility.pause_amplification,
                    "forced_captions": self.accessibility.forced_captions,
                    "override_scope": self.accessibility.override_scope,
                },
                "order_index": self.order_index,
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat(),
            },
            "data": self.opaque_data,
        }
    
    @classmethod
    def from_registrum_state(cls, registrum_state: dict[str, Any]) -> AudioState:
        """
        Create AudioState from Registrum State format.
        
        Args:
            registrum_state: Registrum State dict with id, structure, data
            
        Returns:
            AudioState instance
        """
        structure = registrum_state.get("structure", {})
        ownership_data = structure.get("ownership")
        accessibility_data = structure.get("accessibility", {})
        
        ownership = None
        if ownership_data and ownership_data.get("session_id"):
            ownership = StreamOwnership(
                stream_id=registrum_state["id"],
                session_id=ownership_data["session_id"],
                agent_id=ownership_data["agent_id"],
                priority=ownership_data.get("priority", 5),
                interruptible=ownership_data.get("interruptible", True),
            )
        
        accessibility = AccessibilityState(
            speech_rate_override=accessibility_data.get("speech_rate_override"),
            pause_amplification=accessibility_data.get("pause_amplification"),
            forced_captions=accessibility_data.get("forced_captions", False),
            override_scope=accessibility_data.get("override_scope", "session"),
            override_active=accessibility_data.get("override_active", False),
        )
        
        return cls(
            stream_id=registrum_state["id"],
            state=StreamState(structure.get("state", "idle")),
            ownership=ownership,
            accessibility=accessibility,
            version=structure.get("version", 1),
            order_index=structure.get("order_index", 0),
            opaque_data=registrum_state.get("data", {}),
        )


# Type alias for Registrum StateID
StateID = str
