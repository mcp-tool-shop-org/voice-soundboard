"""
Voice Soundboard Registrar Module — Registrum Integration

This module integrates with mcp-tool-shop-org/Registrum to provide:
- Structural state management (identity, lineage, ordering)
- Domain-specific invariants layered on top
- Deterministic, auditable state transitions

Registrum provides the constitutional foundation:
- 11 structural invariants (3 identity, 4 lineage, 4 ordering)
- Fail-closed validation
- Replayable history
- Dual-witness architecture

Voice Soundboard layers domain invariants:
- Single owner per stream
- Accessibility supremacy
- Plugin immutability
- Interrupt semantics

v2.7 Theme: State Authority & Deterministic Control

Integration Architecture:
    ┌─────────────────────────────────────────────────────┐
    │              Voice Soundboard Runtime               │
    │  ┌─────────────────────────────────────────────┐   │
    │  │         AudioRegistrar (Python)             │   │
    │  │  - Domain invariants                        │   │
    │  │  - Accessibility supremacy                  │   │
    │  │  - Stream ownership                         │   │
    │  └──────────────────┬──────────────────────────┘   │
    │                     │                              │
    │                     ▼                              │
    │  ┌─────────────────────────────────────────────┐   │
    │  │     RegistrumBridge (Python ↔ TypeScript)   │   │
    │  │  - State serialization                      │   │
    │  │  - Transition mapping                       │   │
    │  │  - Attestation relay                        │   │
    │  └──────────────────┬──────────────────────────┘   │
    │                     │                              │
    └─────────────────────┼──────────────────────────────┘
                          │
                          ▼
    ┌─────────────────────────────────────────────────────┐
    │           Registrum (TypeScript/Node.js)            │
    │  - 11 structural invariants                         │
    │  - Identity, Lineage, Ordering                      │
    │  - Snapshots & Replay                               │
    │  - Optional XRPL attestation                        │
    └─────────────────────────────────────────────────────┘
"""

from .bridge import RegistrumBridge, RegistrumConfig
from .registrar import AudioRegistrar, Attestation, AttestationStore
from .states import StreamState, StreamOwnership, AccessibilityState, AudioState
from .transitions import (
    AudioTransition,
    TransitionAction,
    TransitionRequest,
    TransitionResult,
)
from .invariants import (
    DomainInvariant,
    SingleOwnerInvariant,
    AccessibilitySupremacyInvariant,
    NoDeadInterruptInvariant,
    PluginImmutabilityInvariant,
    CommitBoundaryInvariant,
)
from .errors import (
    RegistrarError,
    InvariantViolationError,
    OwnershipError,
    AccessibilityBypassError,
    RegistrumConnectionError,
)

__all__ = [
    # Bridge to Registrum
    "RegistrumBridge",
    "RegistrumConfig",
    # Audio-specific registrar
    "AudioRegistrar",
    # States (mapped to Registrum State model)
    "StreamState",
    "StreamOwnership",
    "AccessibilityState",
    "AudioState",
    # Transitions (mapped to Registrum Transition model)
    "AudioTransition",
    "TransitionAction",
    "TransitionRequest",
    "TransitionResult",
    # Domain Invariants (layered on Registrum's 11)
    "DomainInvariant",
    "SingleOwnerInvariant",
    "AccessibilitySupremacyInvariant",
    "NoDeadInterruptInvariant",
    "PluginImmutabilityInvariant",
    "CommitBoundaryInvariant",
    # Attestations
    "Attestation",
    "AttestationStore",
    # Errors
    "RegistrarError",
    "InvariantViolationError",
    "OwnershipError",
    "AccessibilityBypassError",
    "RegistrumConnectionError",
]
