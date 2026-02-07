# State Model & Invariants Reference (v2.9)

**Version**: 2.9.0 (FROZEN)  
**Status**: Authoritative Reference  
**Last Updated**: 2026-02-07

> ⚠️ **FROZEN**: This document defines the state model that is frozen at v2.9.
> Changes after v2.9 require an RFC and core maintainer approval.

---

## Overview

Voice Soundboard's state model is built on **Registrum**, a formal state management system that provides structural guarantees. This document is the authoritative reference for:

1. **States** — The lifecycle states a stream can occupy
2. **Transitions** — Valid paths between states
3. **Invariants** — Rules that must always hold
4. **Ownership** — Authority model for stream control
5. **Accessibility** — User override semantics

---

## 1. State Model

### 1.1 Stream States

Every audio stream exists in exactly one of these states:

| State | Code | Description | Terminal |
|-------|------|-------------|----------|
| **IDLE** | `idle` | Stream created, awaiting work | No |
| **COMPILING** | `compiling` | Text being compiled to graph | No |
| **SYNTHESIZING** | `synthesizing` | Audio being generated | No |
| **PLAYING** | `playing` | Audio actively playing | No |
| **INTERRUPTING** | `interrupting` | Interrupt in progress | No |
| **STOPPED** | `stopped` | Playback complete (normal) | Yes |
| **FAILED** | `failed` | Error occurred | Yes |

```python
from voice_soundboard.runtime.registrar import StreamState

# All valid states
StreamState.IDLE
StreamState.COMPILING
StreamState.SYNTHESIZING
StreamState.PLAYING
StreamState.INTERRUPTING
StreamState.STOPPED
StreamState.FAILED
```

### 1.2 State Diagram

```
                    ┌──────────────────────────────────────────────────────────┐
                    │                                                          │
                    ▼                                                          │
    ┌────────┐   START   ┌───────────┐  COMPILE   ┌──────────────┐  SYNTH   ┌─────────┐
    │  IDLE  │ ────────► │ COMPILING │ ─────────► │ SYNTHESIZING │ ───────► │ PLAYING │
    └────────┘           └───────────┘            └──────────────┘          └─────────┘
        ▲                      │                         │                       │
        │                      │ FAIL                    │ FAIL                  │ STOP
        │                      ▼                         ▼                       ▼
        │              ┌────────────────────────────────────────────────┐   ┌─────────┐
        │ RESTART      │                   FAILED                       │   │ STOPPED │
        └──────────────┤                                                │   └────┬────┘
                       └────────────────────────────────────────────────┘        │
                                           ▲                                     │
                                           │ FAIL                         RESTART│
                       ┌──────────────┐    │                                     │
                       │ INTERRUPTING │ ───┘                                     │
                       └──────────────┘                                          │
                              ▲                                                  │
                              │ INTERRUPT                                        │
                              └──────────────────────────────────────────────────┘
```

### 1.3 Valid Transitions

| From State | Valid To States | Actions |
|------------|-----------------|---------|
| `IDLE` | `COMPILING`, `FAILED` | START, FAIL |
| `COMPILING` | `SYNTHESIZING`, `FAILED` | COMPILE (complete), FAIL |
| `SYNTHESIZING` | `PLAYING`, `FAILED` | SYNTHESIZE (complete), FAIL |
| `PLAYING` | `INTERRUPTING`, `STOPPED`, `FAILED` | INTERRUPT, STOP, FAIL |
| `INTERRUPTING` | `STOPPED`, `FAILED` | (auto), FAIL |
| `STOPPED` | `IDLE` | RESTART |
| `FAILED` | `IDLE` | RESTART |

```python
from voice_soundboard.runtime.registrar.states import VALID_TRANSITIONS, is_valid_transition

# Check transition validity
is_valid_transition(StreamState.IDLE, StreamState.COMPILING)  # True
is_valid_transition(StreamState.IDLE, StreamState.PLAYING)    # False
```

---

## 2. Transition Actions

### 2.1 Lifecycle Actions

| Action | From States | To State | Description |
|--------|-------------|----------|-------------|
| `START` | IDLE | COMPILING | Begin processing |
| `COMPILE` | COMPILING | SYNTHESIZING | Compilation complete |
| `SYNTHESIZE` | SYNTHESIZING | PLAYING | Synthesis complete |
| `PLAY` | SYNTHESIZING | PLAYING | Begin playback |
| `INTERRUPT` | PLAYING | INTERRUPTING | User/agent interrupt |
| `STOP` | PLAYING | STOPPED | Normal completion |
| `FAIL` | Any non-terminal | FAILED | Error occurred |
| `RESTART` | STOPPED, FAILED | IDLE | Reset for reuse |

### 2.2 Ownership Actions

| Action | Description | Requirements |
|--------|-------------|--------------|
| `CLAIM` | Take ownership of stream | Stream must be unowned |
| `RELEASE` | Give up ownership | Must be current owner |
| `TRANSFER` | Transfer to another agent | Must be current owner |

### 2.3 Accessibility Actions

| Action | Description | Who Can Execute |
|--------|-------------|-----------------|
| `ENABLE_OVERRIDE` | Activate accessibility override | User only |
| `DISABLE_OVERRIDE` | Deactivate override | User only |
| `UPDATE_OVERRIDE` | Modify override parameters | User only |

### 2.4 Plugin Actions

| Action | Description | Requirements |
|--------|-------------|--------------|
| `MUTATE_GRAPH` | Plugin modifies audio graph | Must be pre-commit |
| `COMMIT` | Freeze graph for synthesis | Own or delegate authority |
| `ROLLBACK` | Revert to previous state | Cannot cross commit boundary |

```python
from voice_soundboard.runtime.registrar import TransitionAction

# All transition actions
TransitionAction.START
TransitionAction.COMPILE
TransitionAction.SYNTHESIZE
TransitionAction.PLAY
TransitionAction.INTERRUPT
TransitionAction.STOP
TransitionAction.FAIL
TransitionAction.RESTART
TransitionAction.CLAIM
TransitionAction.RELEASE
TransitionAction.TRANSFER
TransitionAction.ENABLE_OVERRIDE
TransitionAction.DISABLE_OVERRIDE
TransitionAction.UPDATE_OVERRIDE
TransitionAction.MUTATE_GRAPH
TransitionAction.COMMIT
TransitionAction.ROLLBACK
```

---

## 3. Invariants

### 3.1 Invariant Hierarchy

Voice Soundboard enforces two layers of invariants:

```
┌─────────────────────────────────────────────────────┐
│           Domain Invariants (7 rules)               │
│  audio.ownership.*  audio.accessibility.*           │
│  audio.lifecycle.*  audio.plugin.*                  │
├─────────────────────────────────────────────────────┤
│         Registrum Structural Invariants (11)        │
│  identity.*  lineage.*  ordering.*                  │
└─────────────────────────────────────────────────────┘
```

**Evaluation Order**: Registrum invariants first, then domain invariants.  
**Both must pass** for a transition to be accepted.

### 3.2 Invariant Levels

| Level | Code | Behavior | Recovery |
|-------|------|----------|----------|
| **INFO** | `INFO` | Log only | Continue |
| **WARN** | `WARN` | Log + alert | Continue |
| **REJECT** | `REJECT` | Deny transition | Retry with fix |
| **HALT** | `HALT` | Stop system | Manual intervention |

### 3.3 Domain Invariants (Frozen)

#### Ownership Invariants

| ID | Name | Level | Description |
|----|------|-------|-------------|
| `audio.ownership.single_owner` | Single Owner | REJECT | Only one active owner per stream |
| `audio.ownership.required_for_interrupt` | Ownership Required | REJECT | Must own stream to interrupt (unless accessibility) |

**Single Owner Rule**:
```python
# ❌ Violation: Stream already has owner
stream = create_stream(owner="agent_a")
claim(stream, actor="agent_b")  # REJECTED: already owned

# ✅ Correct: Transfer ownership explicitly
stream = create_stream(owner="agent_a")
transfer(stream, from="agent_a", to="agent_b")  # OK
```

**Ownership Required Rule**:
```python
# ❌ Violation: Non-owner attempting interrupt
stream = create_stream(owner="agent_a")
interrupt(stream, actor="agent_b")  # REJECTED: not owner

# ✅ Correct: Owner interrupts
interrupt(stream, actor="agent_a")  # OK

# ✅ Exception: Accessibility override
enable_override(stream, actor="user")
interrupt(stream, actor="agent_b")  # OK (override active)
```

#### Accessibility Invariants

| ID | Name | Level | Description |
|----|------|-------|-------------|
| `audio.accessibility.supremacy` | Accessibility Supremacy | **HALT** | Accessibility overrides cannot be silently ignored |
| `audio.accessibility.auditable` | Accessibility Auditable | REJECT | All accessibility changes must be registered transitions |

> ⚠️ **CRITICAL**: `audio.accessibility.supremacy` is a HALT-level invariant.
> Violations stop the system. This is a safety requirement.

**Supremacy Rule**:
```python
# ❌ Violation: Silent override disable (HALT!)
stream.accessibility.override_active = False  # HALT: silent modification

# ✅ Correct: Explicit disable action
disable_override(stream, actor="user")  # OK: registered transition
```

**Auditable Rule**:
```python
# ❌ Violation: Accessibility change without proper action
stream.accessibility.speech_rate_override = 0.5  # REJECTED

# ✅ Correct: Explicit accessibility action
update_override(stream, speech_rate=0.5, actor="user")  # OK
```

#### Lifecycle Invariants

| ID | Name | Level | Description |
|----|------|-------|-------------|
| `audio.lifecycle.no_dead_interrupt` | No Dead Interrupt | REJECT | Cannot interrupt STOPPED/FAILED stream |
| `audio.lifecycle.commit_boundary` | Commit Boundary | REJECT | Cannot rollback past commit |
| `audio.lifecycle.valid_transition` | Valid Transition | REJECT | Must follow valid state paths |

**No Dead Interrupt Rule**:
```python
# ❌ Violation: Interrupting stopped stream
stream = create_stream()
advance_to(stream, StreamState.STOPPED)
interrupt(stream)  # REJECTED: already stopped

# ✅ Correct: Restart first
restart(stream)  # Stream → IDLE
start(stream)    # Stream → COMPILING
# ... eventually → PLAYING
interrupt(stream)  # OK
```

**Valid Transition Rule**:
```python
# ❌ Violation: Invalid transition
stream = create_stream()  # IDLE
play(stream)  # REJECTED: IDLE → PLAYING invalid

# ✅ Correct: Follow valid path
start(stream)      # IDLE → COMPILING
compile(stream)    # COMPILING → SYNTHESIZING
synthesize(stream) # SYNTHESIZING → PLAYING
```

#### Plugin Invariants

| ID | Name | Level | Description |
|----|------|-------|-------------|
| `audio.plugin.immutability` | Plugin Immutability | REJECT | Plugins cannot mutate committed graphs |

**Immutability Rule**:
```python
# ❌ Violation: Modifying committed graph
stream = create_stream()
advance_to(stream, StreamState.SYNTHESIZING)  # Graph committed
plugin.modify_graph(stream)  # REJECTED: already committed

# ✅ Correct: Modify before commit
stream = create_stream()
advance_to(stream, StreamState.COMPILING)
plugin.modify_graph(stream)  # OK: pre-commit
commit(stream)  # Now frozen
```

### 3.4 Registrum Structural Invariants

These are provided by Registrum and cannot be overridden:

#### Identity Invariants (3)

| ID | Description |
|----|-------------|
| `state.identity.immutable` | State IDs never change |
| `state.identity.explicit` | State IDs are always defined |
| `state.identity.unique` | State IDs are globally unique |

#### Lineage Invariants (4)

| ID | Description |
|----|-------------|
| `state.lineage.explicit` | Parent state is always specified |
| `state.lineage.parent_exists` | Parent must exist (if referenced) |
| `state.lineage.single_parent` | States have at most one parent |
| `state.lineage.continuous` | No gaps in lineage chain |

#### Ordering Invariants (4)

| ID | Description |
|----|-------------|
| `ordering.total` | All states are totally ordered |
| `ordering.monotonic` | Order indices only increase |
| `ordering.gap_free` | No gaps in order sequence |
| `ordering.deterministic` | Same input → same order |

---

## 4. Ownership Model

### 4.1 Ownership Structure

```python
@dataclass(frozen=True)
class StreamOwnership:
    stream_id: str      # Associated stream
    session_id: str     # Session context
    agent_id: str       # Owning agent
    priority: int       # 1-10, higher wins conflicts
    interruptible: bool # Can others interrupt?
    created_at: datetime
```

### 4.2 Ownership Rules

1. **Creation**: Stream creator becomes initial owner
2. **Transfer**: Only current owner can transfer
3. **Release**: Only current owner can release
4. **Claim**: Can only claim unowned streams
5. **Priority**: Higher priority wins on conflict (within rules)

### 4.3 Ownership and Interrupt

```
┌─────────────────────────────────────────────────────────┐
│                    INTERRUPT REQUEST                    │
└─────────────────────────────┬───────────────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Accessibility       │ YES
                   │ Override Active?    │────────► ALLOW
                   └──────────┬──────────┘
                              │ NO
                              ▼
                   ┌─────────────────────┐
                   │ Requester is        │ YES
                   │ Current Owner?      │────────► ALLOW
                   └──────────┬──────────┘
                              │ NO
                              ▼
                   ┌─────────────────────┐
                   │ Stream is           │ YES
                   │ Interruptible?      │────────► ALLOW (with priority check)
                   └──────────┬──────────┘
                              │ NO
                              ▼
                           DENY
```

---

## 5. Accessibility Model

### 5.1 Accessibility State

```python
@dataclass
class AccessibilityState:
    speech_rate_override: float | None  # Override speech rate
    pause_amplification: float | None   # Amplify pauses
    forced_captions: bool               # Force caption output
    override_scope: "session" | "user"  # Override applies to...
    override_active: bool               # Is override currently active
```

### 5.2 Accessibility Override Semantics

**Supremacy Hierarchy**:
```
    User Accessibility Override    (HIGHEST - always wins)
            │
            ▼
    Agent/Owner Intent             (normal operation)
            │
            ▼
    Plugin Modifications           (LOWEST)
```

**Override Scope**:
- `session`: Override applies only to current session
- `user`: Override applies to all sessions for this user

### 5.3 Override Lifecycle

```
User enables override
        │
        ▼
┌───────────────────┐
│  Override Active  │◄───── User can update parameters
└────────┬──────────┘
         │
         │ User disables (explicit)
         │ or Session ends (scope=session)
         ▼
┌───────────────────┐
│ Override Inactive │
└───────────────────┘
```

---

## 6. Attestation Model

### 6.1 Attestation Structure (Frozen)

Every registrar decision produces an attestation:

```python
@dataclass
class Attestation:
    # Identity
    id: str                    # Unique attestation ID
    timestamp: float           # Unix timestamp
    
    # Action
    action: str                # TransitionAction name
    actor: str                 # Who requested
    target: str                # Stream ID
    
    # Decision
    decision: str              # "allowed" or "denied"
    reason: str                # Human-readable explanation
    
    # Context
    parameters: dict           # Action parameters
    invariants_checked: list   # Which invariants were evaluated
    
    # Extensions (v3-safe)
    metadata: dict             # Future-proof extension point
```

### 6.2 Attestation Guarantees

1. **Every request is attested** — No silent decisions
2. **Denials are attested** — Failed attempts are recorded
3. **Accessibility marked** — Override-influenced decisions are flagged
4. **Immutable** — Attestations cannot be modified after creation
5. **Ordered** — Attestations follow global ordering

### 6.3 Attestation for Replay

Attestations enable deterministic replay:

```python
# Capture attestations
attestations = registrar.attestation_store.all()

# Replay into fresh registrar
recovered = AudioRegistrar.replay([a.to_dict() for a in attestations])

# State fully reconstructed
assert recovered.get_state(stream_id) == original_state
```

---

## 7. Decision Flow

### 7.1 Request Processing

```
┌─────────────────┐
│Transition       │
│Request          │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              REGISTRUM VALIDATION                        │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Identity      │  │ Lineage      │  │ Ordering     │  │
│  │ Invariants    │  │ Invariants   │  │ Invariants   │  │
│  └───────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────┬───────────────────────────────┘
                          │ Pass
                          ▼
┌─────────────────────────────────────────────────────────┐
│              DOMAIN VALIDATION                           │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Ownership     │  │ Accessibility│  │ Lifecycle    │  │
│  │ Invariants    │  │ Invariants   │  │ Invariants   │  │
│  └───────────────┘  └──────────────┘  └──────────────┘  │
│  ┌───────────────┐                                      │
│  │ Plugin        │                                      │
│  │ Invariants    │                                      │
│  └───────────────┘                                      │
└─────────────────────────┬───────────────────────────────┘
                          │ Pass
                          ▼
┌─────────────────────────────────────────────────────────┐
│              ATTESTATION                                 │
│  Record decision, create attestation, update state      │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              TRANSITION RESULT                           │
│  {allowed: true, reason: "...", attestation_id: "..."}  │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Decision Outcomes

| Outcome | Invariant Level | State Change | Attestation |
|---------|-----------------|--------------|-------------|
| **ALLOW** | All pass | Applied | Created (allowed) |
| **DENY** | REJECT violation | None | Created (denied) |
| **HALT** | HALT violation | None | Created + **SYSTEM HALT** |

---

## 8. Version Information

### 8.1 Schema Version

```python
# v2.9 FROZEN
REGISTRAR_SCHEMA_VERSION = "2.9.0"
STATE_SCHEMA_FROZEN = True

# Version check
def check_compatibility(version: str) -> bool:
    """Check if version is compatible with v2.9 schema."""
    major, minor, _ = version.split(".")
    return major == "2" and int(minor) >= 6
```

### 8.2 Supported Versions

| Version | Status | Notes |
|---------|--------|-------|
| 2.6.x | Supported | Full compatibility |
| 2.7.x | Supported | Full compatibility |
| 2.8.x | Supported | Full compatibility |
| 2.9.x | Current | Schema frozen |
| 3.0.x | Future | Will support 2.9 schema |

### 8.3 v3 Compatibility Promise

The v2.9 state model is guaranteed compatible with v3:

- ✅ States will not change
- ✅ Transitions will not change
- ✅ Invariants will not change
- ✅ Attestation format will not change
- ✅ Ownership model will not change
- ✅ Accessibility model will not change

v3 may **add** (not modify):
- New metadata fields in `Attestation.metadata`
- New opaque data in `AudioState.opaque_data`
- New optional parameters to existing actions

---

## Appendix A: Quick Reference

### State Transitions

```
IDLE ──────────────► COMPILING ──────────► SYNTHESIZING ──────────► PLAYING
  ▲                      │                       │                      │
  │                      │                       │                      │
  │ RESTART              │ FAIL                  │ FAIL                 │ STOP
  │                      ▼                       ▼                      ▼
  └─────────────── FAILED ◄─────────────────────────────────────── STOPPED
                         ▲                                              │
                         │             INTERRUPT                        │
                         └──────────── INTERRUPTING ◄───────────────────┘
```

### Invariant Quick Reference

| Invariant | Level | One-liner |
|-----------|-------|-----------|
| `audio.ownership.single_owner` | REJECT | One owner per stream |
| `audio.ownership.required_for_interrupt` | REJECT | Owner or accessibility to interrupt |
| `audio.accessibility.supremacy` | **HALT** | User override cannot be bypassed |
| `audio.accessibility.auditable` | REJECT | Accessibility changes are explicit |
| `audio.lifecycle.no_dead_interrupt` | REJECT | Can't interrupt terminal states |
| `audio.lifecycle.commit_boundary` | REJECT | Can't rollback past commit |
| `audio.lifecycle.valid_transition` | REJECT | Follow state machine |
| `audio.plugin.immutability` | REJECT | Can't modify committed graphs |

### Decision Matrix

| Actor | Accessibility Override | Owner | Action | Result |
|-------|------------------------|-------|--------|--------|
| User | - | - | ENABLE_OVERRIDE | ✅ ALLOW |
| User | Active | - | DISABLE_OVERRIDE | ✅ ALLOW |
| Agent | Active | Yes | INTERRUPT | ❌ DENY |
| Agent | Active | No | INTERRUPT | ❌ DENY |
| Agent | Inactive | Yes | INTERRUPT | ✅ ALLOW |
| Agent | Inactive | No | INTERRUPT | ❌ DENY |

---

*This document is the authoritative reference for Voice Soundboard v2.9 state model.*
*Changes require RFC approval. See ROADMAP_v2.9.md for change process.*
