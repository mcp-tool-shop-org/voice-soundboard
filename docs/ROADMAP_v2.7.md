# Voice Soundboard v2.7 Roadmap

**Target**: Q2-Q3 2027  
**Theme**: "State Authority & Deterministic Control"  
**Codename**: Registrum Integration  
**Foundation**: [mcp-tool-shop-org/Registrum](https://github.com/mcp-tool-shop-org/Registrum)

---

## Executive Summary

v2.7 introduces a **single authoritative state registrar** based on [Registrum](https://github.com/mcp-tool-shop-org/Registrum) to mediate all meaningful runtime state transitions. This is a **correctness release**, not a feature release.

### Registrum Foundation

Registrum provides the constitutional foundation:

| Registrum Provides | Voice Soundboard Adds |
|-------------------|----------------------|
| 11 structural invariants | 8 domain invariants |
| Identity guarantees | Stream ownership |
| Lineage tracking | Session/agent binding |
| Ordering constraints | Accessibility supremacy |
| Deterministic decisions | Audio lifecycle states |
| Replay capability | Domain-specific replay |
| Optional XRPL attestation | Internal attestation store |

### Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Voice Soundboard Runtime (Python)              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              AudioRegistrar                           │  │
│  │  - 8 domain invariants (ownership, accessibility...)  │  │
│  │  - State management (streams, sessions)               │  │
│  │  - Attestation recording                              │  │
│  └────────────────────────┬──────────────────────────────┘  │
│                           │                                 │
│                           ▼                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              RegistrumBridge                          │  │
│  │  - Modes: in-memory | subprocess | http | mcp         │  │
│  │  - State serialization (AudioState → Registrum State) │  │
│  │  - Transition mapping                                 │  │
│  └────────────────────────┬──────────────────────────────┘  │
│                           │                                 │
└───────────────────────────┼─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           Registrum (TypeScript/Node.js)                    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  StructuralRegistrar                                  │  │
│  │  - 11 invariants: Identity(3) + Lineage(4) + Order(4) │  │
│  │  - Dual-witness architecture                          │  │
│  │  - Deterministic & replayable                         │  │
│  └───────────────────────────────────────────────────────┘  │
│  github.com/mcp-tool-shop-org/Registrum                     │
└─────────────────────────────────────────────────────────────┘
```

### Invariant Mapping

**Registrum's 11 Structural Invariants:**
- Identity: `state.identity.immutable`, `state.identity.explicit`, `state.identity.unique`
- Lineage: `state.lineage.explicit`, `state.lineage.parent_exists`, `state.lineage.single_parent`, `state.lineage.continuous`
- Ordering: `ordering.total`, `ordering.monotonic`, `ordering.gap_free`, `ordering.deterministic`

**Voice Soundboard's 8 Domain Invariants (layered on top):**
- Ownership: `audio.ownership.single_owner`, `audio.ownership.required_for_interrupt`
- Accessibility: `audio.accessibility.supremacy` (HALT), `audio.accessibility.auditable`
- Lifecycle: `audio.lifecycle.no_dead_interrupt`, `audio.lifecycle.commit_boundary`, `audio.lifecycle.valid_transition`
- Plugin: `audio.plugin.immutability`

### What v2.7 Delivers

| Capability | Before v2.7 | After v2.7 |
|------------|-------------|------------|
| State location | Distributed, implicit | Centralized, explicit |
| State changes | Unmediated | Registrar-gated |
| Audit trail | None | Full attestation |
| Bug reproduction | Race conditions | Deterministic replay |
| Accessibility | Advisory | Authoritative |
| MCP control | Direct mutation | Request-based |

### Core Question

> Is all meaningful state change mediated, auditable, and replayable?

If **yes** → v2.7 can ship  
If **no** → v2.7 cannot ship

---

## Breaking Changes

**None.** This is an internal-only architectural change.

- ✅ Public API unchanged
- ✅ Existing apps behave identically
- ✅ No new required configuration
- ✅ Registrar is internal (no opt-out needed)

---

## 📋 GitHub Issues Index

Each section below becomes a GitHub issue. Use this index for tracking.

| Issue # | Title | Priority | Phase | Blocks |
|---------|-------|----------|-------|--------|
| #1 | [Entry Criteria] v2.6 Prerequisites | P0 | 0 | All |
| #2 | [Scope] Registrar Boundary Definition | P0 | 1 | #3-#12 |
| #3 | [State] Audio Stream State Model | P0 | 2 | #5, #6 |
| #4 | [State] Session/Ownership State Model | P0 | 2 | #5, #6 |
| #5 | [State] Accessibility State Model | P0 | 2 | #8 |
| #6 | [Core] Centralized State Transitions | P0 | 3 | #7 |
| #7 | [Core] Invariant Definition & Enforcement | P0 | 4 | #8, #9, #10 |
| #8 | [Core] Attestation & Audit Trail | P0 | 5 | #10, #11 |
| #9 | [Safety] Accessibility Guarantees | P0 | 6 | #12 |
| #10 | [Integration] MCP ↔ Registrar Bridge | P0 | 7 | #11 |
| #11 | [Testing] Deterministic Test Suite | P0 | 8 | #12 |
| #12 | [Release] Performance & Gate Criteria | P0 | 9 | ship |

---

## 🧾 Issue #1: Entry Criteria (v2.6 Prerequisites)

**Labels**: `priority/P0`, `type/gate`, `phase/0-entry`  
**Blocks**: All other v2.7 work  
**Assignee**: Tech Lead

### Description

Before any v2.7 work begins, these v2.6 conditions must be verified.

### Acceptance Criteria

- [ ] **ACC-1.1**: Accessibility features ship without implicit state mutation
- [ ] **ACC-1.2**: Interrupt, pause, resume, and cancel semantics are explicit
- [ ] **ACC-1.3**: Multi-agent / MCP control paths exist
- [ ] **ACC-1.4**: No engine-level logic depends on global mutable state
- [ ] **ACC-1.5**: v2.6 behavior is fully regression-tested

### Gate Rule

```
IF any checkbox is unchecked THEN
    DO NOT start v2.7
    RETURN to v2.6 and fix
END
```

### Verification Script

```bash
# Run v2.6 verification suite
pytest tests/v26_entry_criteria/ -v --tb=short
```

### Evidence Required

- [ ] CI passing on main branch
- [ ] Regression test report attached
- [ ] Accessibility audit report attached

---

## 🧱 Issue #2: Registrar Scope Definition

**Labels**: `priority/P0`, `type/design`, `phase/1-scope`  
**Blocks**: Issues #3-#12  
**Depends**: Issue #1

### Description

Define firm boundaries for what the Registrar owns vs. does not own. No ambiguity allowed.

### Registrar WILL Own

- [ ] **SCOPE-2.1**: Audio stream lifecycle state
- [ ] **SCOPE-2.2**: Ownership (agent / session)
- [ ] **SCOPE-2.3**: Interrupt & rollback arbitration
- [ ] **SCOPE-2.4**: Accessibility overrides that affect playback
- [ ] **SCOPE-2.5**: Commit / rollback boundaries
- [ ] **SCOPE-2.6**: Plugin-induced state changes

### Registrar WILL NOT Own

- [ ] **SCOPE-2.7**: PCM buffers (documented exclusion)
- [ ] **SCOPE-2.8**: DSP execution (documented exclusion)
- [ ] **SCOPE-2.9**: Scheduling / threading (documented exclusion)
- [ ] **SCOPE-2.10**: Business policy (documented exclusion)
- [ ] **SCOPE-2.11**: Backend-internal state (documented exclusion)

### Acceptance Criteria

- [ ] **ACC-2.1**: Scope document written and reviewed
- [ ] **ACC-2.2**: No ambiguity remains (tech lead sign-off)
- [ ] **ACC-2.3**: Exclusions documented with rationale
- [ ] **ACC-2.4**: Scope freeze announcement sent

### Deliverables

- `docs/architecture/REGISTRAR_SCOPE.md`
- Tech lead approval comment on PR

### Gate Rule

```
IF any scope item is ambiguous THEN
    RESOLVE before implementation
    DO NOT proceed to Phase 2
END
```

---

## 🧠 Issue #3: Audio Stream State Model

**Labels**: `priority/P0`, `type/implementation`, `phase/2-state`  
**Blocks**: Issues #5, #6  
**Depends**: Issue #2

### Description

Define explicit state machine for audio stream lifecycle. Currently implicit in runtime.

### State Enumeration

All states must be registered:

- [ ] **STATE-3.1**: `IDLE` - No active stream
- [ ] **STATE-3.2**: `COMPILING` - Graph compilation in progress
- [ ] **STATE-3.3**: `SYNTHESIZING` - Audio synthesis in progress
- [ ] **STATE-3.4**: `PLAYING` - Audio playback active
- [ ] **STATE-3.5**: `INTERRUPTING` - Interrupt in progress
- [ ] **STATE-3.6**: `STOPPED` - Stream terminated normally
- [ ] **STATE-3.7**: `FAILED` - Stream terminated with error

### State Machine Diagram

```
     ┌─────────────────────────────────────┐
     │                                     │
     ▼                                     │
   IDLE                                    │
     │                                     │
     │ request:start                       │
     ▼                                     │
 COMPILING ──────────────────────────────► FAILED
     │                                     ▲
     │ compiled                            │
     ▼                                     │
SYNTHESIZING ─────────────────────────────►│
     │                                     │
     │ ready                               │
     ▼                                     │
  PLAYING ────────────────────────────────►│
     │                                     │
     │ request:interrupt                   │
     ▼                                     │
INTERRUPTING ─────────────────────────────►│
     │                                     │
     │ completed                           │
     ▼                                     │
  STOPPED                                  │
     │                                     │
     └─────────────────────────────────────┘
           (restart)
```

### Acceptance Criteria

- [ ] **ACC-3.1**: `StreamState` enum defined in `registrar/states.py`
- [ ] **ACC-3.2**: All transitions documented
- [ ] **ACC-3.3**: Invalid transitions raise `InvalidTransitionError`
- [ ] **ACC-3.4**: State queryable via `registrar.get_stream_state(stream_id)`
- [ ] **ACC-3.5**: Unit tests for all state transitions

### API Specification

```python
from voice_soundboard.runtime.registrar import StreamState

class StreamState(Enum):
    IDLE = "idle"
    COMPILING = "compiling"
    SYNTHESIZING = "synthesizing"
    PLAYING = "playing"
    INTERRUPTING = "interrupting"
    STOPPED = "stopped"
    FAILED = "failed"
```

### Test Requirements

```python
def test_valid_transition_idle_to_compiling():
    """IDLE → COMPILING is valid"""

def test_invalid_transition_idle_to_playing():
    """IDLE → PLAYING is invalid (must compile first)"""

def test_failed_is_terminal():
    """FAILED cannot transition to any state except IDLE (restart)"""
```

---

## 👤 Issue #4: Session/Ownership State Model

**Labels**: `priority/P0`, `type/implementation`, `phase/2-state`  
**Blocks**: Issues #5, #6  
**Depends**: Issue #2

### Description

Every stream must have explicit ownership and session binding.

### Ownership Properties

- [ ] **OWN-4.1**: `stream_id` - Unique stream identifier
- [ ] **OWN-4.2**: `session_id` - Session that owns stream
- [ ] **OWN-4.3**: `agent_id` - Agent that initiated stream
- [ ] **OWN-4.4**: `priority` - Priority level (1-10)
- [ ] **OWN-4.5**: `interruptible` - Can be interrupted by others

### Ownership Rules

- [ ] **RULE-4.1**: Exactly one owner per active stream
- [ ] **RULE-4.2**: Ownership required for interrupt
- [ ] **RULE-4.3**: Priority determines conflict resolution
- [ ] **RULE-4.4**: Accessibility override may supersede ownership

### Acceptance Criteria

- [ ] **ACC-4.1**: `StreamOwnership` dataclass defined
- [ ] **ACC-4.2**: Ownership assigned at stream creation
- [ ] **ACC-4.3**: Ownership transfer requires explicit request
- [ ] **ACC-4.4**: Orphan streams are auto-reclaimed
- [ ] **ACC-4.5**: Ownership violations raise `OwnershipError`

### API Specification

```python
@dataclass(frozen=True)
class StreamOwnership:
    stream_id: str
    session_id: str
    agent_id: str
    priority: int  # 1-10, higher wins
    interruptible: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
```

---

## ♿ Issue #5: Accessibility State Model

**Labels**: `priority/P0`, `type/implementation`, `phase/2-state`, `accessibility`  
**Blocks**: Issue #8  
**Depends**: Issues #3, #4

### Description

Accessibility is not a modifier — it is authoritative state. This is why v2.7 exists.

### Accessibility State Properties

- [ ] **A11Y-5.1**: `speech_rate_override` - Forced speech rate
- [ ] **A11Y-5.2**: `pause_amplification` - Extended pause durations
- [ ] **A11Y-5.3**: `forced_captions` - Captioning always on
- [ ] **A11Y-5.4**: `override_scope` - Session or user level

### Override Hierarchy

```
User Override > Session Override > Agent Intent > Default
```

### Acceptance Criteria

- [ ] **ACC-5.1**: `AccessibilityState` dataclass defined
- [ ] **ACC-5.2**: Overrides are scoped (session / user)
- [ ] **ACC-5.3**: Override activation is auditable
- [ ] **ACC-5.4**: Override removal is auditable
- [ ] **ACC-5.5**: Conflicts resolved by explicit precedence

### Critical Rule

> **Accessibility transitions must be registrable and auditable.**  
> If accessibility logic bypasses registrar → **fail the build**.

### API Specification

```python
@dataclass
class AccessibilityState:
    speech_rate_override: float | None = None
    pause_amplification: float | None = None
    forced_captions: bool = False
    override_scope: Literal["session", "user"] = "session"
    
    def applies_to(self, session: StreamOwnership) -> bool:
        """Check if this override applies to given session."""
```

---

## 🔄 Issue #6: Centralized State Transitions

**Labels**: `priority/P0`, `type/implementation`, `phase/3-central`  
**Blocks**: Issue #7  
**Depends**: Issues #3, #4

### Description

No ad-hoc mutation. All state changes are requests to registrar.

### Transition Requirements

- [ ] **TRANS-6.1**: All state changes expressed as requests
- [ ] **TRANS-6.2**: No `set_state()` outside registrar
- [ ] **TRANS-6.3**: No implicit transitions in runtime
- [ ] **TRANS-6.4**: All transitions validated against invariants
- [ ] **TRANS-6.5**: All transitions produce attestations

### Acceptance Criteria

- [ ] **ACC-6.1**: `registrar.request()` is only state mutation path
- [ ] **ACC-6.2**: Runtime code has zero direct state writes
- [ ] **ACC-6.3**: Grep for forbidden patterns passes CI
- [ ] **ACC-6.4**: Transition requests return `Decision` objects

### Request API

```python
@dataclass
class StateRequest:
    action: str  # "start", "interrupt", "stop", etc.
    actor: str   # Agent or system ID
    target: str  # Stream ID
    reason: str  # Human-readable reason
    meta: dict = field(default_factory=dict)

@dataclass
class Decision:
    allowed: bool
    reason: str
    effects: list[Effect]
    attestation_id: str
    timestamp: datetime
```

### Example Flow

```python
# Before v2.7 (WRONG - direct mutation)
runtime.interrupt(stream_id)

# After v2.7 (CORRECT - request-based)
decision = registrar.request(
    action="interrupt",
    actor=agent_id,
    target=stream_id,
    reason="accessibility_override"
)

if decision.allowed:
    runtime.apply(decision.effects)
else:
    log.info(f"Interrupt denied: {decision.reason}")
```

### CI Enforcement

```bash
# Forbidden pattern check
grep -rn "\.set_state\|\.state\s*=" voice_soundboard/runtime/ \
    --include="*.py" \
    | grep -v "registrar" \
    && exit 1 || exit 0
```

---

## 🧷 Issue #7: Invariant Definition & Enforcement

**Labels**: `priority/P0`, `type/implementation`, `phase/4-invariants`  
**Blocks**: Issues #8, #9, #10  
**Depends**: Issue #6

### Description

Invariants must exist before wiring execution. Each invariant is non-negotiable.

### Required Invariants

| ID | Name | Description | Failure Mode |
|----|------|-------------|--------------|
| INV-1 | Single Owner | Only one active owner per stream | Reject request |
| INV-2 | No Dead Interrupt | Cannot interrupt a stopped stream | Reject request |
| INV-3 | Commit Boundary | Cannot rollback past commit | Reject request |
| INV-4 | A11Y Supremacy | Accessibility overrides cannot be ignored | Fail assertion |
| INV-5 | Plugin Immutability | Plugins cannot mutate committed graphs | Reject request |
| INV-6 | Determinism | Registrar decisions are deterministic | N/A (property) |

### Acceptance Criteria

For each invariant:

- [ ] **INV-x.1**: Name defined
- [ ] **INV-x.2**: Description documented
- [ ] **INV-x.3**: Test case exists
- [ ] **INV-x.4**: Failure mode specified

Checklist:

- [ ] **ACC-7.1**: INV-1 (Single Owner) implemented & tested
- [ ] **ACC-7.2**: INV-2 (No Dead Interrupt) implemented & tested
- [ ] **ACC-7.3**: INV-3 (Commit Boundary) implemented & tested
- [ ] **ACC-7.4**: INV-4 (A11Y Supremacy) implemented & tested
- [ ] **ACC-7.5**: INV-5 (Plugin Immutability) implemented & tested
- [ ] **ACC-7.6**: INV-6 (Determinism) verified via replay tests

### Invariant Implementation

```python
class Invariant(Protocol):
    name: str
    description: str
    
    def check(self, state: RegistrarState, request: StateRequest) -> bool:
        """Return True if invariant holds, False if violated."""
    
    def on_violation(self, state: RegistrarState, request: StateRequest) -> Decision:
        """Return denial decision for invariant violation."""

# Example implementation
class SingleOwnerInvariant(Invariant):
    name = "single_owner"
    description = "Only one active owner per stream"
    
    def check(self, state, request):
        if request.action != "claim_ownership":
            return True
        stream = state.get_stream(request.target)
        return stream.owner is None or stream.owner == request.actor
```

---

## 🧾 Issue #8: Attestation & Audit Trail

**Labels**: `priority/P0`, `type/implementation`, `phase/5-audit`  
**Blocks**: Issues #10, #11  
**Depends**: Issues #5, #7

### Description

Registrum-style attestations are mandatory. Every decision is recorded.

### Attestation Requirements

- [ ] **ATT-8.1**: Every request produces a decision
- [ ] **ATT-8.2**: Every decision has unique attestation ID
- [ ] **ATT-8.3**: Attestations include: actor, action, target, allowed/denied, reason
- [ ] **ATT-8.4**: Attestations are immutable once created
- [ ] **ATT-8.5**: Attestations are replayable
- [ ] **ATT-8.6**: Accessibility-driven decisions are explicitly marked

### Acceptance Criteria

- [ ] **ACC-8.1**: `Attestation` dataclass defined
- [ ] **ACC-8.2**: Attestation storage backend implemented
- [ ] **ACC-8.3**: Query API for attestation retrieval
- [ ] **ACC-8.4**: Replay capability from attestation log
- [ ] **ACC-8.5**: Attestation immutability enforced

### Critical Rule

> **Denials are valid outcomes, not errors.**

A denied interrupt is:
- ✅ Logged as attestation
- ✅ Returned to caller
- ❌ NOT an exception
- ❌ NOT a warning

### Attestation Schema

```python
@dataclass(frozen=True)
class Attestation:
    id: str  # UUID
    timestamp: datetime
    actor: str
    action: str
    target: str | None
    decision: Literal["allowed", "denied"]
    reason: str
    invariants_checked: list[str]
    accessibility_driven: bool = False
    meta: dict = field(default_factory=dict)
```

### Storage Interface

```python
class AttestationStore(Protocol):
    def record(self, attestation: Attestation) -> None:
        """Immutably record attestation."""
    
    def query(
        self,
        actor: str | None = None,
        action: str | None = None,
        target: str | None = None,
        since: datetime | None = None,
    ) -> list[Attestation]:
        """Query attestations by criteria."""
    
    def replay(self, attestations: list[Attestation]) -> RegistrarState:
        """Reconstruct state from attestation log."""
```

---

## 🔐 Issue #9: Accessibility Guarantees

**Labels**: `priority/P0`, `type/implementation`, `phase/6-safety`, `accessibility`  
**Blocks**: Issue #12  
**Depends**: Issue #7

### Description

Registrar must enforce accessibility correctness. This is the primary reason for v2.7.

### Safety Requirements

- [ ] **SAFE-9.1**: Accessibility overrides always win over agent intent
- [ ] **SAFE-9.2**: Overrides are scoped (session / user)
- [ ] **SAFE-9.3**: Overrides are reversible
- [ ] **SAFE-9.4**: No override silently alters engine behavior
- [ ] **SAFE-9.5**: All override transitions are attested

### Acceptance Criteria

- [ ] **ACC-9.1**: Override precedence enforced in registrar
- [ ] **ACC-9.2**: Override bypass detection implemented
- [ ] **ACC-9.3**: Override attestations marked with `accessibility_driven=True`
- [ ] **ACC-9.4**: Test for accessibility supremacy invariant
- [ ] **ACC-9.5**: Documentation for accessibility guarantees

### Critical Rule

> **If accessibility logic bypasses registrar → fail.**

This is enforced at:
1. Code review (linting rule)
2. CI (pattern grep)
3. Runtime (assertion)

### Test Specification

```python
def test_accessibility_override_beats_agent():
    """Agent intent cannot override accessibility settings."""
    registrar.request(
        action="set_accessibility_override",
        actor="user",
        target="session_1",
        meta={"speech_rate": 0.5}
    )
    
    decision = registrar.request(
        action="set_speech_rate",
        actor="agent_1",
        target="stream_1",
        meta={"speech_rate": 2.0}  # Agent wants faster
    )
    
    assert decision.allowed == False
    assert "accessibility override active" in decision.reason


def test_accessibility_bypass_detected():
    """Direct accessibility mutation is caught."""
    with pytest.raises(AccessibilityBypassError):
        stream.speech_rate = 2.0  # Direct mutation
```

---

## 🔌 Issue #10: MCP ↔ Registrar Integration

**Labels**: `priority/P0`, `type/implementation`, `phase/7-mcp`  
**Blocks**: Issue #11  
**Depends**: Issues #7, #8

### Description

MCP must never bypass the registrar. All MCP actions are requests, not commands.

### Integration Requirements

- [ ] **MCP-10.1**: MCP tools submit requests, not commands
- [ ] **MCP-10.2**: Registrar arbitrates all MCP actions
- [ ] **MCP-10.3**: MCP receives structured decision responses
- [ ] **MCP-10.4**: Ownership & priority enforced consistently
- [ ] **MCP-10.5**: MCP concurrency tested under load

### Acceptance Criteria

- [ ] **ACC-10.1**: MCP tools refactored to use registrar
- [ ] **ACC-10.2**: No direct runtime calls from MCP
- [ ] **ACC-10.3**: Decision responses include attestation ID
- [ ] **ACC-10.4**: Concurrent MCP tests pass at 100 req/s
- [ ] **ACC-10.5**: Priority arbitration documented

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        MCP Layer                            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ speak() │  │ stop()  │  │ pause() │  │ resume()│        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │              │
│       └────────────┴──────┬─────┴────────────┘              │
│                           │                                 │
│                    ┌──────▼──────┐                          │
│                    │  Registrar  │                          │
│                    │   Request   │                          │
│                    └──────┬──────┘                          │
│                           │                                 │
└───────────────────────────┼─────────────────────────────────┘
                            │
                     ┌──────▼──────┐
                     │  Registrar  │
                     │  (decides)  │
                     └──────┬──────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
       ┌──────▼──────┐             ┌──────▼──────┐
       │  Allowed    │             │   Denied    │
       │  (execute)  │             │  (return)   │
       └──────┬──────┘             └─────────────┘
              │
       ┌──────▼──────┐
       │   Runtime   │
       │  (effects)  │
       └─────────────┘
```

### MCP Tool Refactoring

```python
# Before v2.7 (WRONG)
@mcp_tool
def speak(text: str, voice: str) -> AudioResult:
    return engine.speak(text, voice=voice)  # Direct call

# After v2.7 (CORRECT)
@mcp_tool
def speak(text: str, voice: str, context: MCPContext) -> MCPResponse:
    decision = registrar.request(
        action="speak",
        actor=context.agent_id,
        target=None,  # New stream
        meta={"text": text, "voice": voice}
    )
    
    if not decision.allowed:
        return MCPResponse(
            success=False,
            reason=decision.reason,
            attestation_id=decision.attestation_id
        )
    
    result = runtime.apply(decision.effects)
    return MCPResponse(
        success=True,
        data=result,
        attestation_id=decision.attestation_id
    )
```

---

## 🧪 Issue #11: Deterministic Test Suite

**Labels**: `priority/P0`, `type/testing`, `phase/8-testing`  
**Blocks**: Issue #12  
**Depends**: Issues #8, #10

### Description

If a bug cannot be reproduced via replay, the system is incomplete.

### Required Test Classes

- [ ] **TEST-11.1**: Unit tests for registrar transitions
- [ ] **TEST-11.2**: Invariant violation tests
- [ ] **TEST-11.3**: Concurrent request arbitration tests
- [ ] **TEST-11.4**: Accessibility override tests
- [ ] **TEST-11.5**: Replay / rehydration tests
- [ ] **TEST-11.6**: MCP + registrar integration tests

### Acceptance Criteria

- [ ] **ACC-11.1**: 100% coverage on registrar module
- [ ] **ACC-11.2**: All invariants have violation tests
- [ ] **ACC-11.3**: Race condition tests with 10 concurrent agents
- [ ] **ACC-11.4**: Replay tests reconstruct state exactly
- [ ] **ACC-11.5**: Flaky test rate < 0.1%

### Test Matrix

| Category | Count | Status |
|----------|-------|--------|
| State transition tests | 20+ | 🔲 |
| Invariant tests | 6+ | 🔲 |
| Concurrency tests | 10+ | 🔲 |
| Accessibility tests | 15+ | 🔲 |
| Replay tests | 5+ | 🔲 |
| MCP integration tests | 10+ | 🔲 |
| **Total** | **66+** | 🔲 |

### Critical Test: Replay Consistency

```python
def test_replay_produces_identical_state():
    """Replaying attestations produces identical final state."""
    # Execute a sequence of operations
    registrar.request(action="start", actor="agent_1", target="stream_1")
    registrar.request(action="play", actor="agent_1", target="stream_1")
    registrar.request(action="interrupt", actor="agent_2", target="stream_1")
    
    original_state = registrar.snapshot()
    attestations = registrar.attestation_store.query()
    
    # Replay from scratch
    new_registrar = Registrar()
    replayed_state = new_registrar.replay(attestations)
    
    assert replayed_state == original_state
```

---

## ⚙️ Issue #12: Performance & Release Gate

**Labels**: `priority/P0`, `type/gate`, `phase/9-release`  
**Blocks**: Ship  
**Depends**: Issues #9, #10, #11

### Performance Constraints

Registrar must not become a bottleneck.

- [ ] **PERF-12.1**: Registrar decisions < 1ms (p95)
- [ ] **PERF-12.2**: No blocking I/O in registrar path
- [ ] **PERF-12.3**: Attestation logging is async
- [ ] **PERF-12.4**: High-frequency paths optimized
- [ ] **PERF-12.5**: Real-time audio path unaffected

### Failure Mode Requirements

- [ ] **FAIL-12.1**: Registrar denial fails closed (no action)
- [ ] **FAIL-12.2**: Registrar crash leaves engine in safe state
- [ ] **FAIL-12.3**: Partial failures do not corrupt state
- [ ] **FAIL-12.4**: Clear error surfaces to MCP / callers

### Release Gate Checklist

v2.7 can ship **only if ALL boxes are checked**:

| Gate | Criteria | Verified |
|------|----------|----------|
| G1 | All meaningful state transitions go through registrar | ⬜ |
| G2 | Invariants are enforced, tested, and documented | ⬜ |
| G3 | Accessibility is provably respected | ⬜ |
| G4 | MCP cannot bypass state authority | ⬜ |
| G5 | Replay can explain every major behavior | ⬜ |
| G6 | No engine performance regressions | ⬜ |

### Gate Enforcement

```bash
#!/bin/bash
# .github/scripts/release-gate.sh

set -e

echo "=== v2.7 Release Gate Check ==="

# G1: State transitions
echo "G1: Checking state transition centralization..."
./scripts/verify-state-centralization.py || exit 1

# G2: Invariants
echo "G2: Running invariant tests..."
pytest tests/registrar/test_invariants.py -v || exit 1

# G3: Accessibility
echo "G3: Running accessibility guarantee tests..."
pytest tests/registrar/test_accessibility.py -v || exit 1

# G4: MCP isolation
echo "G4: Checking MCP bypass..."
./scripts/verify-mcp-isolation.py || exit 1

# G5: Replay
echo "G5: Running replay tests..."
pytest tests/registrar/test_replay.py -v || exit 1

# G6: Performance
echo "G6: Running performance benchmarks..."
pytest tests/registrar/test_performance.py -v || exit 1

echo "=== ALL GATES PASSED ==="
```

### Ship Decision Matrix

| Condition | Action |
|-----------|--------|
| All gates pass | ✅ Ship |
| Any G1-G5 fails | ❌ Do not ship, fix first |
| G6 fails < 5% regression | ⚠️ Tech lead decision |
| G6 fails ≥ 5% regression | ❌ Do not ship, optimize |

---

## 📁 Implementation Structure

### New Directory Structure

```
voice_soundboard/
  runtime/
    registrar/
      __init__.py        # Public exports
      registrar.py       # Core Registrar class
      states.py          # State enums and models
      transitions.py     # Transition validators
      invariants.py      # Invariant implementations
      attestations.py    # Attestation storage
      effects.py         # Effect executors
      errors.py          # Registrar-specific errors
```

### Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `registrar.py` | Request handling, decision making |
| `states.py` | `StreamState`, `StreamOwnership`, `AccessibilityState` |
| `transitions.py` | Valid transition definitions |
| `invariants.py` | Invariant protocol and implementations |
| `attestations.py` | `Attestation`, `AttestationStore` |
| `effects.py` | `Effect`, `EffectExecutor` |
| `errors.py` | Custom exceptions |

---

## 📅 Timeline

```
2027-02-15  v2.6.0 released
     │
     ▼
2027-02-22  Issue #1: Entry criteria verified
     │
     ▼
2027-03-01  Issue #2: Scope frozen
     │
     ▼
2027-03-15  Issues #3-5: State models complete
     │
     ▼
2027-04-01  Issue #6: Centralized transitions
     │
     ▼
2027-04-15  Issue #7: Invariants complete
     │
     ▼
2027-05-01  Issue #8: Attestation system
     │
     ▼
2027-05-15  Issue #9: Accessibility guarantees
     │
     ▼
2027-06-01  Issue #10: MCP integration
     │
     ▼
2027-06-15  Issue #11: Test suite complete
     │
     ▼
2027-07-01  Issue #12: Release gate
     │
     ▼
2027-07-15  v2.7.0 release
```

---

## 🚫 Explicitly NOT in v2.7

These remain out of scope:

- ❌ New public APIs
- ❌ PCM buffer management
- ❌ DSP execution changes
- ❌ Scheduling / threading changes
- ❌ Business logic / policy
- ❌ Breaking changes of any kind

---

## 📋 Full Checklist (CI-Integrated)

This checklist blocks merges when used in PR template:

```markdown
## v2.7 Merge Checklist

### Entry Criteria
- [ ] v2.6 prerequisites verified (Issue #1)

### Scope
- [ ] Change is within registrar scope (Issue #2)
- [ ] No scope creep introduced

### Implementation
- [ ] State changes go through registrar
- [ ] No direct state mutation
- [ ] Invariants checked for new transitions
- [ ] Attestations produced for decisions

### Accessibility
- [ ] Accessibility overrides respected
- [ ] No accessibility bypass introduced

### Testing
- [ ] Unit tests added/updated
- [ ] Invariant tests pass
- [ ] Replay test covers new behavior

### Documentation
- [ ] API docs updated
- [ ] Attestation format documented
```

---

## 🔄 Migration from v2.6

### For Library Users

**No action required.** v2.7 is completely backwards compatible.

```python
# v2.6 code (still works in v2.7)
engine = VoiceEngine()
result = engine.speak("Hello!")
```

### For Internal Development

All runtime code must migrate to registrar-gated mutations:

```python
# v2.6 (legacy, will be removed)
self._state = StreamState.PLAYING

# v2.7 (required)
decision = self._registrar.request(
    action="play",
    actor=self._session_id,
    target=self._stream_id,
)
if decision.allowed:
    self._apply_effects(decision.effects)
```

---

## 🧭 Final Framing

> **v2.7 is not a feature release. It is a correctness release.**

### If Done Right

- ✅ v3 becomes dramatically simpler
- ✅ Audio bugs become explainable
- ✅ Accessibility becomes enforceable
- ✅ Agent coordination becomes safe by default

### If Skipped or Rushed

- ❌ v3 will inherit invisible state debt
- ❌ DSP bugs will be misattributed
- ❌ Safety issues will surface late
- ❌ Accessibility guarantees will be hollow

---

*Last updated: 2027-02-07*
