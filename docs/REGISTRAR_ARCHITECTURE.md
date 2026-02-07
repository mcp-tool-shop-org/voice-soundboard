# Registrar Architecture (v2.9)

**Version**: 2.9.0 (FROZEN)  
**Status**: Authoritative Reference  
**Last Updated**: 2026-02-07

> ⚠️ **FROZEN**: This architecture is frozen at v2.9.
> The control plane cannot change without RFC approval.

---

## Executive Summary

The **Audio Registrar** is the single authority for all audio state transitions in Voice Soundboard. It ensures that:

1. **Every state change is mediated** — No bypass allowed
2. **Every decision is auditable** — Attestations for all requests
3. **State is replayable** — Can explain and reconstruct history
4. **Accessibility is supreme** — User overrides cannot be bypassed

---

## 1. Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VOICE SOUNDBOARD                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Agents    │  │   Plugins   │  │     MCP     │  │    User     │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │               │
│         └────────────────┴────────────────┴────────────────┘               │
│                                   │                                         │
│                                   ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        AUDIO REGISTRAR                                │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    Domain Invariants (7)                        │  │  │
│  │  │  ┌──────────┐ ┌─────────────┐ ┌──────────┐ ┌────────┐         │  │  │
│  │  │  │Ownership │ │Accessibility│ │Lifecycle │ │ Plugin │         │  │  │
│  │  │  └──────────┘ └─────────────┘ └──────────┘ └────────┘         │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                │                                      │  │
│  │                                ▼                                      │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    REGISTRUM BRIDGE                             │  │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                        │  │  │
│  │  │  │ Identity │ │ Lineage  │ │ Ordering │                        │  │  │
│  │  │  │ (3 inv)  │ │ (4 inv)  │ │ (4 inv)  │                        │  │  │
│  │  │  └──────────┘ └──────────┘ └──────────┘                        │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                                │                                      │  │
│  │                                ▼                                      │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │                    ATTESTATION STORE                            │  │  │
│  │  │         [Immutable audit trail of all decisions]               │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                   │                                         │
│                                   ▼                                         │
│                     ┌─────────────────────────────┐                        │
│                     │        AUDIO RUNTIME        │                        │
│                     │  (Effects applied on allow) │                        │
│                     └─────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Summary

| Component | Responsibility |
|-----------|---------------|
| **AudioRegistrar** | Single authority for state transitions |
| **Domain Invariants** | Business rules (ownership, accessibility, etc.) |
| **RegistrumBridge** | Structural validation (identity, lineage, ordering) |
| **AttestationStore** | Immutable audit trail |
| **Audio Runtime** | Effect execution (only on allow) |

---

## 2. Component Details

### 2.1 AudioRegistrar

The main entry point for all state changes.

```python
class AudioRegistrar:
    """
    The Audio Registrar — single authority for audio state transitions.
    """
    
    def __init__(
        self,
        config: RegistrumConfig | None = None,
        domain_invariants: list[DomainInvariant] | None = None,
    ) -> None: ...
    
    def request(
        self,
        action: str | TransitionAction,
        actor: str,
        target: StateID | None = None,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TransitionResult:
        """Main entry point for state changes."""
        ...
    
    def get_state(self, stream_id: StateID) -> AudioState | None:
        """Get current state for a stream."""
        ...
    
    def list_states(self) -> dict[StateID, AudioState]:
        """Get all current states."""
        ...
    
    def snapshot(self) -> dict[str, Any]:
        """Create recoverable snapshot."""
        ...
    
    def replay(self, attestations: list[dict]) -> AudioRegistrar:
        """Replay attestations to reconstruct state."""
        ...
```

**Key Properties**:
- **Singleton Authority**: No other component can change state
- **Synchronous Decisions**: All requests return immediately
- **Deterministic**: Same inputs → same outputs

### 2.2 AttestationStore

Immutable record of all decisions.

```python
class AttestationStore:
    """Storage for attestations."""
    
    def record(self, attestation: Attestation) -> None:
        """Record an attestation (immutable)."""
        ...
    
    def query(
        self,
        actor: str | None = None,
        action: str | None = None,
        target: str | None = None,
        since: datetime | None = None,
        decision: str | None = None,
    ) -> list[Attestation]:
        """Query attestations by criteria."""
        ...
    
    def all(self) -> list[Attestation]:
        """Get all attestations."""
        ...
```

**Key Properties**:
- **Append-Only**: Attestations cannot be modified or deleted
- **Queryable**: Support filtering by actor, action, target, time
- **Replayable**: Can recreate registrar state from attestations

### 2.3 RegistrumBridge

Connection to Registrum's structural validation.

```python
class RegistrumBridge:
    """Bridge to Registrum structural invariants."""
    
    def register(self, transition: AudioTransition) -> TransitionResult:
        """Validate and register a transition."""
        ...
    
    def list_invariants(self) -> list[dict]:
        """List Registrum's 11 structural invariants."""
        ...
    
    def snapshot(self) -> dict:
        """Capture Registrum state."""
        ...
```

**Structural Invariants (11)**:
- Identity (3): immutable, explicit, unique
- Lineage (4): explicit, parent_exists, single_parent, continuous
- Ordering (4): total, monotonic, gap_free, deterministic

---

## 3. Request Flow

### 3.1 Request Processing Sequence

```
┌─────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────┐
│ Caller  │     │AudioRegistrar│     │ Domain Inv  │     │  Registrum │
└────┬────┘     └──────┬───────┘     └──────┬──────┘     └─────┬──────┘
     │                 │                    │                  │
     │  request(...)   │                    │                  │
     │────────────────►│                    │                  │
     │                 │                    │                  │
     │                 │  check(transition) │                  │
     │                 │───────────────────►│                  │
     │                 │                    │                  │
     │                 │  violations[]      │                  │
     │                 │◄───────────────────│                  │
     │                 │                    │                  │
     │                 │          [if no violations]          │
     │                 │                    │                  │
     │                 │                    │  register(trans) │
     │                 │────────────────────────────────────►│
     │                 │                    │                  │
     │                 │                    │  result         │
     │                 │◄────────────────────────────────────│
     │                 │                    │                  │
     │                 │  [record attestation]                │
     │                 │                    │                  │
     │                 │  [update state if allowed]           │
     │                 │                    │                  │
     │  result         │                    │                  │
     │◄────────────────│                    │                  │
     │                 │                    │                  │
```

### 3.2 Decision Algorithm

```python
def process_request(request: TransitionRequest) -> TransitionResult:
    # 1. Build proposed state
    current = get_state(request.target)
    proposed = build_proposed_state(request, current)
    transition = AudioTransition(current, proposed, request)
    
    # 2. Check domain invariants
    domain_violations = []
    for invariant in DOMAIN_INVARIANTS:
        violations = invariant.check(transition, all_states)
        domain_violations.extend(violations)
        
        # HALT-level violations are critical
        if any(v.classification == "HALT" for v in violations):
            raise AccessibilityBypassError(...)
    
    # 3. If domain invariants pass, check Registrum
    if not domain_violations:
        result = registrum_bridge.register(transition)
    else:
        result = TransitionResult(REJECTED, violations=domain_violations)
    
    # 4. Record attestation (always)
    attestation = create_attestation(request, result)
    attestation_store.record(attestation)
    
    # 5. Update state (only on allow)
    if result.allowed:
        states[proposed.stream_id] = proposed
    
    return result
```

---

## 4. State Management

### 4.1 State Storage

```
┌────────────────────────────────────────────────────────────────┐
│                     AudioRegistrar._states                      │
├────────────────────────────────────────────────────────────────┤
│  StreamID        │  AudioState                                 │
├──────────────────┼─────────────────────────────────────────────┤
│  "stream_abc123" │  {                                          │
│                  │    stream_id: "stream_abc123",              │
│                  │    state: PLAYING,                          │
│                  │    ownership: {agent_id: "agent_1", ...},   │
│                  │    accessibility: {override_active: false}, │
│                  │    version: 5,                              │
│                  │    ...                                      │
│                  │  }                                          │
├──────────────────┼─────────────────────────────────────────────┤
│  "stream_def456" │  {...}                                      │
└──────────────────┴─────────────────────────────────────────────┘
```

### 4.2 State Updates

States are **only** updated through `request()`:

```python
# ✅ Correct: State change via registrar
result = registrar.request(
    action=TransitionAction.INTERRUPT,
    actor="agent_1",
    target="stream_abc123",
)
if result.allowed:
    # State already updated internally
    pass

# ❌ Forbidden: Direct state mutation
registrar._states["stream_abc123"].state = StreamState.STOPPED  # NEVER DO THIS
```

### 4.3 Multi-Stream Support

The registrar supports multiple concurrent streams:

```python
# Create multiple streams
stream_a = registrar.request(action="start", actor="agent_1")
stream_b = registrar.request(action="start", actor="agent_1")
stream_c = registrar.request(action="start", actor="agent_2")

# Independent lifecycles
registrar.request(action="interrupt", actor="agent_1", target=stream_a.target)
# stream_b and stream_c unaffected
```

---

## 5. Attestation System

### 5.1 Attestation Structure

```python
@dataclass
class Attestation:
    id: str                      # Unique ID (UUID)
    timestamp: datetime          # When decision was made
    actor: str                   # Who requested
    action: str                  # What action
    target: str | None           # Which stream
    decision: str               # "allowed" or "denied"
    reason: str                  # Why
    invariants_checked: list[str]  # Which invariants evaluated
    accessibility_driven: bool   # Was this accessibility-related?
    metadata: dict              # Extension point
```

### 5.2 Attestation Guarantees

| Guarantee | Description |
|-----------|-------------|
| **Complete** | Every request produces an attestation |
| **Immutable** | Attestations cannot be modified |
| **Ordered** | Attestations have global ordering |
| **Queryable** | Can filter by any field |
| **Replayable** | Can reconstruct state from attestations |

### 5.3 Replay Mechanism

```python
# Capture attestations
original_attestations = registrar.attestation_store.all()
serialized = [a.to_dict() for a in original_attestations]

# Later: Replay to reconstruct state
recovered_registrar = registrar.replay(serialized)

# State is identical
for stream_id in original_registrar.list_states():
    original = original_registrar.get_state(stream_id)
    recovered = recovered_registrar.get_state(stream_id)
    assert original.state == recovered.state
```

---

## 6. Invariant System

### 6.1 Two-Layer Validation

```
┌─────────────────────────────────────────────────────────────┐
│                    Domain Invariants                         │
│  (Voice Soundboard business rules)                          │
│                                                              │
│  audio.ownership.single_owner                                │
│  audio.ownership.required_for_interrupt                      │
│  audio.accessibility.supremacy ← HALT LEVEL                  │
│  audio.accessibility.auditable                               │
│  audio.lifecycle.no_dead_interrupt                           │
│  audio.lifecycle.commit_boundary                             │
│  audio.lifecycle.valid_transition                            │
│  audio.plugin.immutability                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ Must pass
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                Registrum Structural Invariants               │
│  (Formal state machine guarantees)                          │
│                                                              │
│  state.identity.immutable                                    │
│  state.identity.explicit                                     │
│  state.identity.unique                                       │
│  state.lineage.explicit                                      │
│  state.lineage.parent_exists                                 │
│  state.lineage.single_parent                                 │
│  state.lineage.continuous                                    │
│  ordering.total                                              │
│  ordering.monotonic                                          │
│  ordering.gap_free                                           │
│  ordering.deterministic                                      │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Invariant Evaluation

```python
# Domain invariants are evaluated FIRST
for invariant in DOMAIN_INVARIANTS:
    violations = invariant.check(transition, current_states)
    
    if violations:
        # Check for HALT-level
        for v in violations:
            if v.classification == "HALT":
                # System must stop
                raise AccessibilityBypassError(v.message)
        
        # REJECT-level: deny but continue
        return TransitionResult(REJECTED, violations=violations)

# Only if domain passes, check Registrum
registrum_result = bridge.register(transition)
```

### 6.3 HALT vs REJECT

| Level | Effect | Recovery |
|-------|--------|----------|
| **REJECT** | Transition denied, system continues | Retry with fix |
| **HALT** | System stops immediately | Manual intervention |

**HALT-level invariants** (currently one):
- `audio.accessibility.supremacy` — User override bypass

---

## 7. Integration Points

### 7.1 MCP Integration

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   MCP Tool   │────────►│  Registrar   │────────►│    Result    │
│  play_sound  │         │   request()  │         │  allow/deny  │
└──────────────┘         └──────────────┘         └──────────────┘
```

MCP tools **must** route through registrar:

```python
# MCP tool implementation
async def play_sound(text: str, voice: str) -> MCPResult:
    # Create stream via registrar
    result = registrar.request(
        action=TransitionAction.START,
        actor=mcp_context.agent_id,
        metadata={"text": text, "voice": voice},
    )
    
    if not result.allowed:
        return MCPResult(
            error=True,
            message=result.reason,
        )
    
    # Continue with synthesis...
```

### 7.2 Plugin Integration

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│    Plugin    │────────►│  Registrar   │────────►│    Result    │
│  modify_graph│         │   request()  │         │  allow/deny  │
└──────────────┘         └──────────────┘         └──────────────┘
```

Plugins **cannot** bypass registrar:

```python
# ❌ Forbidden: Direct graph mutation
stream.graph.add_effect(reverb)

# ✅ Required: Request via registrar
result = registrar.request(
    action=TransitionAction.MUTATE_GRAPH,
    actor=plugin.id,
    target=stream.id,
    metadata={"effect": "reverb"},
)
```

### 7.3 Runtime Integration

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   Runtime    │────────►│  Registrar   │────────►│    Effect    │
│  play_audio  │         │   request()  │         │   execute    │
└──────────────┘         └──────────────┘         └──────────────┘
```

Runtime effects **only** execute on allow:

```python
class AudioRuntime:
    def play(self, stream_id: str) -> None:
        # Must go through registrar
        result = self.registrar.request(
            action=TransitionAction.PLAY,
            actor="runtime",
            target=stream_id,
        )
        
        if result.allowed:
            self._apply_play_effect(stream_id)
        else:
            raise RegistrarDeniedError(result.reason)
```

---

## 8. Performance Characteristics

### 8.1 Latency Budget

| Operation | Target | Notes |
|-----------|--------|-------|
| `request()` p50 | < 100 µs | Hot path |
| `request()` p99 | < 1 ms | Including attestation |
| `get_state()` | < 50 µs | Direct lookup |
| `query()` attestations | < 10 ms | For small result sets |

### 8.2 Hot-Path Optimization

```
┌────────────────────────────────────────────────────────────┐
│                    HOT PATH (< 1ms)                        │
│                                                            │
│  request() → domain_check() → registrum_check()            │
│                              ↓                             │
│  No IPC        ←→          state_update()                  │
│  No disk I/O   ←→          attestation_record()            │
│  No network    ←→                                          │
└────────────────────────────────────────────────────────────┘
```

**Guarantees**:
- No inter-process communication
- No disk I/O on critical path
- No network calls
- Memory-only state storage
- Synchronous attestation recording

### 8.3 Thread Safety

The registrar is **not** thread-safe by default. Concurrency must be managed externally:

```python
# Option 1: Single-threaded (recommended for audio)
registrar = AudioRegistrar()
# All calls from single thread

# Option 2: External locking
lock = threading.Lock()

def safe_request(...):
    with lock:
        return registrar.request(...)
```

---

## 9. Failure Modes

### 9.1 Failure Catalog

| Failure | Behavior | Recovery |
|---------|----------|----------|
| Domain invariant REJECT | Transition denied | Retry with fix |
| Domain invariant HALT | System stops | Manual restart |
| Registrum validation fail | Transition denied | Fix state |
| State corruption | Undefined | Replay from attestations |

### 9.2 Safe Halt

When a HALT-level invariant is violated:

```python
def _check_domain_invariants(self, transition):
    for invariant in self._domain_invariants:
        violations = invariant.check(transition, self._states)
        
        for v in violations:
            if v.classification == "HALT":
                # Log critical error
                logger.critical(f"HALT: {v.message}")
                
                # Record attestation before halt
                attestation = self._create_halt_attestation(v)
                self._attestation_store.record(attestation)
                
                # Raise to stop system
                raise AccessibilityBypassError(v.message)
```

### 9.3 Recovery via Replay

```python
# After failure, recover from attestations
attestations = load_attestations_from_storage()

# Replay only successful transitions
allowed_only = [a for a in attestations if a["decision"] == "allowed"]

# Reconstruct state
recovered = AudioRegistrar()
for att in allowed_only:
    recovered.request(
        action=att["action"],
        actor=att["actor"],
        target=att["target"],
    )
```

---

## 10. Configuration

### 10.1 RegistrumConfig

```python
@dataclass
class RegistrumConfig:
    """Configuration for Registrum bridge."""
    
    # Structural validation options
    strict_lineage: bool = True
    strict_ordering: bool = True
    
    # Performance tuning
    cache_size: int = 1000
    
    # Debug options
    trace_enabled: bool = False
    invariant_timing: bool = False
```

### 10.2 Domain Invariant Customization

```python
# Use default invariants
registrar = AudioRegistrar()

# Use custom invariants (e.g., for testing)
custom_invariants = [
    SingleOwnerInvariant(),
    AccessibilitySupremacyInvariant(),
    # ... subset or custom invariants
]
registrar = AudioRegistrar(domain_invariants=custom_invariants)
```

---

## 11. API Reference

### 11.1 AudioRegistrar

```python
class AudioRegistrar:
    def request(
        self,
        action: str | TransitionAction,
        actor: str,
        target: StateID | None = None,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> TransitionResult:
        """Request a state transition."""
    
    def get_state(self, stream_id: StateID) -> AudioState | None:
        """Get current state for a stream."""
    
    def list_states(self) -> dict[StateID, AudioState]:
        """Get all current states."""
    
    def snapshot(self) -> dict[str, Any]:
        """Create recoverable snapshot."""
    
    def replay(self, attestations: list[dict]) -> AudioRegistrar:
        """Replay attestations to reconstruct state."""
    
    def list_invariants(self) -> list[dict[str, Any]]:
        """List all active invariants."""
    
    def observe(
        self, action: str, actor: str,
        target: StateID | None = None,
        meta: dict | None = None,
    ) -> None:
        """Shadow mode observation."""
    
    @property
    def attestation_store(self) -> AttestationStore:
        """Access attestation store."""
```

### 11.2 TransitionResult

```python
@dataclass
class TransitionResult:
    kind: DecisionKind           # ACCEPTED or REJECTED
    request: TransitionRequest   # Original request
    violations: list[InvariantViolation]  # If rejected
    effects: list[Effect]        # If accepted
    attestation_id: str          # Created attestation
    timestamp: datetime          # Decision time
    applied_invariants: list[str]  # Which invariants passed
    accessibility_driven: bool   # A11y-related?
    
    @property
    def allowed(self) -> bool:
        return self.kind == DecisionKind.ACCEPTED
    
    @property
    def reason(self) -> str:
        if self.violations:
            return self.violations[0].message
        return "Allowed"
```

---

*This document is the authoritative architecture reference for Voice Soundboard v2.9.*
*Changes require RFC approval. See ROADMAP_v2.9.md for change process.*
