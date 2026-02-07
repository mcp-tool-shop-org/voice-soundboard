# Voice Soundboard v2.8 Roadmap

**Target**: Q2 2027  
**Theme**: "Registrum Correctness & State Integrity"

---

## Executive Summary

v2.8 is the **correctness release**. Before v3 introduces DSP pipelines and real-time morphing, the state management layer must be provably correct, auditable, and safe under concurrency.

This release introduces **Registrum Integration Tests** — the authoritative specification that gates all future releases. If any test in section 4.8 fails, the release cannot ship.

1. **Registrum Enforcement** — All state transitions mediated by registrar
2. **Accessibility Supremacy** — User control always wins, visibly and attested
3. **Concurrency Safety** — Deterministic arbitration under racing agents
4. **Audit Trail** — Every decision explainable via attestation replay

No breaking changes. Fully backwards compatible with v2.7.

---

## 🚨 Release Gate

> **If any test in section 4.8 fails → v2.8 must not ship.**

This is non-negotiable. Registrum correctness is the foundation for:
- v3 DSP effects chain
- Real-time voice morphing
- Production MCP deployments
- Enterprise accessibility compliance

---

## 4.8 — Registrum Integration Tests (Authoritative Spec)

**Purpose**: Prove that all meaningful state transitions are mediated, enforced, auditable, deterministic, and safe under concurrency, without regressing real-time audio.

---

### 4.8.1 Registrar Mediation Tests (Hard Gate)

**Goal**: Ensure no state change bypasses the registrar.

#### Required Tests

| Test | Description |
|------|-------------|
| ✅ | Starting a stream without registrar decision → fails |
| ✅ | Interrupting a stream without registrar decision → fails |
| ✅ | Accessibility override applied without registrar → fails |
| ✅ | Plugin attempting mutation without registrar → fails |

#### Example

```python
with pytest.raises(RegistrarRequiredError):
    runtime.interrupt(stream_id)
```

📌 **Invariant**: Runtime cannot mutate lifecycle state directly.

---

### 4.8.2 Lifecycle Ordering Tests

**Goal**: Prove lifecycle transitions obey Registrum ordering invariants.

#### Required Tests

| Test | Description |
|------|-------------|
| ✅ | IDLE → PLAYING (skip compile) → denied |
| ✅ | STOPPED → INTERRUPTING → denied |
| ✅ | FAILED → PLAYING → denied |
| ✅ | PLAYING → COMPILING → denied |

#### Example

```python
decision = registrar.request(
    action="interrupt",
    actor=agent,
    target=stopped_stream
)
assert decision.allowed is False
assert decision.reason == "terminal_state"
```

#### State Machine

```
                    ┌──────────────────────────────────────┐
                    │         Lifecycle States             │
                    └──────────────────────────────────────┘

    ┌──────┐      ┌───────────┐      ┌─────────┐      ┌─────────┐
    │ IDLE │ ──→  │ COMPILING │ ──→  │ PLAYING │ ──→  │ STOPPED │
    └──────┘      └───────────┘      └─────────┘      └─────────┘
                                          │                 │
                                          ▼                 │
                                   ┌─────────────┐          │
                                   │ INTERRUPTING│ ─────────┘
                                   └─────────────┘
                                          │
                                          ▼
                                     ┌────────┐
                                     │ FAILED │
                                     └────────┘

    ❌ Invalid transitions are denied with attestation
```

---

### 4.8.3 Ownership & Authority Tests

**Goal**: Ensure only the owning actor may mutate a stream (unless overridden).

#### Required Tests

| Test | Description |
|------|-------------|
| ✅ | Non-owner interrupt → denied |
| ✅ | Owner interrupt → allowed |
| ✅ | Ownership transfer requires explicit registrar transition |
| ✅ | Multiple agents racing → single winner |

#### Concurrency Case

```python
# Two agents interrupt simultaneously
decisions = parallel([
    lambda: registrar.request("interrupt", agent_a, stream),
    lambda: registrar.request("interrupt", agent_b, stream),
])

assert exactly_one(decisions.allowed)
```

📌 **Invariant**: Authority is exclusive and deterministic.

---

### 4.8.4 Accessibility Supremacy Tests (Critical)

**Goal**: Prove accessibility always wins, visibly and attested.

⚠️ **Failure here is a release blocker.**

#### Required Tests

| Test | Description |
|------|-------------|
| ✅ | Accessibility override blocks agent interrupt |
| ✅ | Override owner can still interrupt |
| ✅ | Override removal restores agent authority |
| ✅ | Overrides are scoped (session/user) |

#### Example

```python
registrar.request("enable_accessibility_override", user)

decision = registrar.request("interrupt", agent, stream)
assert decision.allowed is False
assert decision.reason == "accessibility_override"
```

#### Override Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│                  Authority Hierarchy                     │
├─────────────────────────────────────────────────────────┤
│  1. Accessibility Override (HIGHEST)                     │
│     └── User-controlled, session/user scoped            │
│  2. Stream Owner                                         │
│     └── Actor that created the stream                   │
│  3. Delegated Authority                                  │
│     └── Explicit transfer via registrar                 │
│  4. Agent Request (LOWEST)                               │
│     └── MCP agents, plugins, external callers           │
└─────────────────────────────────────────────────────────┘
```

---

### 4.8.5 Hot-Path Latency Tests

**Goal**: Ensure registrar does not break real-time audio.

#### Required Tests

| Test | Description |
|------|-------------|
| ✅ | Interrupt decision p99 < 1 ms (in-process) |
| ✅ | No IPC on hot path |
| ✅ | Audio thread never blocks on registrar |

#### Example

```python
latencies = benchmark_interrupts(iterations=10000)
assert percentile(latencies, 99) < 1.0  # milliseconds
```

#### Performance Budget

| Operation | p50 | p99 | Max |
|-----------|-----|-----|-----|
| Interrupt decision | 0.1 ms | 1.0 ms | 5 ms |
| Ownership check | 0.05 ms | 0.5 ms | 2 ms |
| Attestation write | 0.1 ms | 0.8 ms | 3 ms |

---

### 4.8.6 Attestation Completeness Tests

**Goal**: Every decision must be explainable.

#### Required Tests

| Test | Description |
|------|-------------|
| ✅ | Every request yields an attestation |
| ✅ | Attestation includes: actor, action, target, decision, invariant(s) applied |
| ✅ | Denials are attested |
| ✅ | Accessibility decisions explicitly marked |

#### Example

```python
att = registrar.request(...).attestation
assert att.actor == agent
assert att.action == "interrupt"
assert att.target == stream_id
assert att.decision in ["allowed", "denied"]
assert "ownership" in att.invariants
```

#### Attestation Schema

```python
@dataclass
class Attestation:
    id: UUID
    timestamp: datetime
    actor: ActorId
    action: str
    target: StreamId
    decision: Literal["allowed", "denied"]
    reason: str | None
    invariants: list[str]
    accessibility_override: bool
    parent_attestation: UUID | None  # For causal ordering
```

---

### 4.8.7 Replay Determinism Tests

**Goal**: Prove the system can explain itself after the fact.

#### Required Tests

| Test | Description |
|------|-------------|
| ✅ | Replaying attestations reconstructs state |
| ✅ | Replay produces identical decisions |
| ✅ | Order of replay matters (causality preserved) |

#### Example

```python
# Capture attestations during operation
attestations = capture_attestations(scenario)

# Replay from scratch
state = replay(attestations)
assert state.stream(stream_id).status == "STOPPED"

# Verify determinism
state2 = replay(attestations)
assert state == state2
```

#### Replay Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Replay Engine                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   Attestation Log    ──→    State Reconstructor          │
│                                    │                     │
│   [A1] ──→ [A2] ──→ [A3]          ▼                     │
│                              ┌──────────┐               │
│                              │  State   │               │
│                              │ Snapshot │               │
│                              └──────────┘               │
│                                    │                     │
│                                    ▼                     │
│                              Verification               │
│                              (deterministic)            │
└─────────────────────────────────────────────────────────┘
```

---

### 4.8.8 MCP ↔ Registrar Integration Tests

**Goal**: Ensure MCP cannot bypass registrar authority.

#### Required Tests

| Test | Description |
|------|-------------|
| ✅ | MCP tool calls are routed via registrar |
| ✅ | MCP interrupt obeys ownership rules |
| ✅ | MCP receives structured denial responses |
| ✅ | Concurrent MCP agents arbitrate correctly |

#### Example

```python
resp = mcp.call("voice.interrupt", stream_id)
assert resp.decision == "denied"
assert resp.reason == "not_owner"
```

#### MCP Response Schema

```python
@dataclass
class MCPResponse:
    success: bool
    decision: Literal["allowed", "denied"]
    reason: str | None
    attestation_id: UUID
    retry_after: float | None  # For rate limiting
```

---

### 4.8.9 Plugin Containment Tests

**Goal**: Prevent plugins from mutating registered state.

#### Required Tests

| Test | Description |
|------|-------------|
| ✅ | Plugin cannot change lifecycle state directly |
| ✅ | Plugin mutation requires registrar approval |
| ✅ | Plugin denial is safe and attested |

#### Example

```python
class MaliciousPlugin(Plugin):
    def on_audio(self, audio):
        # Attempt direct state mutation
        self.runtime.streams[stream_id].status = "STOPPED"

with pytest.raises(RegistrarRequiredError):
    engine.load_plugin(MaliciousPlugin())
```

#### Plugin Sandbox

```
┌─────────────────────────────────────────────────────────┐
│                    Plugin Sandbox                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   Plugin Code                                            │
│       │                                                  │
│       ▼                                                  │
│   ┌─────────────────┐                                   │
│   │  Plugin API     │  ← Read-only stream access        │
│   │  (restricted)   │  ← No lifecycle mutations         │
│   └────────┬────────┘  ← Audio processing only          │
│            │                                             │
│            ▼                                             │
│   ┌─────────────────┐                                   │
│   │   Registrar     │  ← All mutations go here          │
│   │   (gatekeeper)  │                                   │
│   └─────────────────┘                                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

### 4.8.10 Failure & Recovery Tests

**Goal**: Ensure registrar failure is safe.

#### Required Tests

| Test | Description |
|------|-------------|
| ✅ | Registrar denial → no partial execution |
| ✅ | Registrar crash → runtime halts safely |
| ✅ | Restart + replay restores consistent state |

#### Example

```python
# Simulate registrar crash
with simulate_crash(registrar):
    result = engine.speak("Hello")
    assert result.status == "failed"
    assert result.reason == "registrar_unavailable"

# Restart and verify recovery
registrar.restart()
state = registrar.replay_from_log()
assert state.is_consistent()
```

#### Failure Modes

| Failure | Behavior | Recovery |
|---------|----------|----------|
| Registrar timeout | Request denied (fail-closed) | Automatic retry |
| Registrar crash | Runtime halts, streams stopped | Replay from log |
| Corrupt attestation | Rejected, flagged for audit | Manual review |
| Network partition | Local cache, sync on reconnect | Conflict resolution |

---

### 4.8.11 Regression Guard (Permanent)

**Goal**: Prevent future bypasses.

#### Required

| Guard | Description |
|-------|-------------|
| ✅ | CI test that fails if runtime mutates state directly |
| ✅ | Lint / static check for forbidden mutations |
| ✅ | Registrar-required assertion in runtime paths |

#### CI Configuration

```yaml
# .github/workflows/registrum-guard.yml
name: Registrum Regression Guard

on: [push, pull_request]

jobs:
  registrar-bypass-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Check for direct state mutations
        run: |
          # Fail if any file directly mutates stream state
          ! grep -r "\.status\s*=" src/voice_soundboard/runtime/ \
            --include="*.py" \
            | grep -v "# registrar-approved"
      
      - name: Run static analysis
        run: |
          python -m registrum_lint src/
      
      - name: Run integration tests
        run: |
          pytest tests/registrum/ -v --tb=short
```

#### Static Analysis Rules

```python
# registrum_lint.py
FORBIDDEN_PATTERNS = [
    r"stream\.status\s*=",           # Direct status mutation
    r"stream\.owner\s*=",            # Direct owner mutation
    r"runtime\.streams\[.*\]\s*=",   # Direct stream assignment
    r"lifecycle\.transition\(",       # Unmediated transition
]

REQUIRED_PATTERNS = [
    r"registrar\.request\(",         # Must use registrar
    r"@registrar_required",          # Decorator on mutations
]
```

---

## 📋 Full Test Matrix

| Section | Test Count | Priority | Status |
|---------|-----------|----------|--------|
| 4.8.1 Registrar Mediation | 4 | P0 (Gate) | 🔲 Not Started |
| 4.8.2 Lifecycle Ordering | 4 | P0 (Gate) | 🔲 Not Started |
| 4.8.3 Ownership & Authority | 4 | P0 (Gate) | 🔲 Not Started |
| 4.8.4 Accessibility Supremacy | 4 | P0 (Critical) | 🔲 Not Started |
| 4.8.5 Hot-Path Latency | 3 | P0 (Gate) | 🔲 Not Started |
| 4.8.6 Attestation Completeness | 4 | P1 | 🔲 Not Started |
| 4.8.7 Replay Determinism | 3 | P1 | 🔲 Not Started |
| 4.8.8 MCP Integration | 4 | P1 | 🔲 Not Started |
| 4.8.9 Plugin Containment | 3 | P1 | 🔲 Not Started |
| 4.8.10 Failure & Recovery | 3 | P1 | 🔲 Not Started |
| 4.8.11 Regression Guard | 3 | P0 (Permanent) | 🔲 Not Started |

**Total**: 39 tests | **Gate tests**: 19 | **Critical**: 4

---

## 🎯 Acceptance Rule (Non-Negotiable)

> **If any state-changing behavior cannot be explained by a registrar attestation, v2.8 is not complete.**

---

## 📅 Timeline

```
2027-01-15  v2.7.0 released
     │
     ▼
2027-02-01  v2.8 test framework design
     │      - Registrum test harness
     │      - Attestation capture
     │      - Replay infrastructure
     │
     ▼
2027-02-15  v2.8-alpha.1
     │      - 4.8.1 Mediation tests
     │      - 4.8.2 Lifecycle tests
     │      - 4.8.3 Ownership tests
     │
     ▼
2027-03-01  v2.8-alpha.2
     │      - 4.8.4 Accessibility tests (CRITICAL)
     │      - 4.8.5 Latency tests
     │      - 4.8.6 Attestation tests
     │
     ▼
2027-03-15  v2.8-beta.1
     │      - 4.8.7 Replay tests
     │      - 4.8.8 MCP tests
     │      - 4.8.9 Plugin tests
     │
     ▼
2027-04-01  v2.8-beta.2
     │      - 4.8.10 Failure tests
     │      - 4.8.11 Regression guards
     │      - Full test suite green
     │
     ▼
2027-04-15  v2.8-rc.1
     │      - All 39 tests passing
     │      - Performance validation
     │      - Security review
     │
     ▼
2027-05-01  v2.8.0 release
```

---

## 🚫 Explicitly NOT in v2.8

These remain for v3:

- ❌ DSP effects chain implementation
- ❌ Real-time voice morphing
- ❌ 3D spatial audio rendering
- ❌ Video lip-sync generation
- ❌ Breaking API changes

v2.8 is **correctness only**. No new features.

---

## Why 4.8 Exists

This section ensures that:

| Guarantee | Without 4.8 | With 4.8 |
|-----------|-------------|----------|
| v2.8 correctness | Assumed | Proven |
| Accessibility enforcement | Hopeful | Guaranteed |
| MCP safety | Trust-based | Verified |
| v3 DSP foundation | Risky | Solid |

> **Without 4.8, Registrum is cosmetic.**

---

## 🔄 Migration from v2.7

### No Breaking Changes

v2.8 is fully backwards compatible. Existing code works unchanged.

### New Behaviors

```python
# v2.7 code (still works, now attested)
engine = VoiceEngine()
result = engine.speak("Hello!")

# Every operation now produces attestation
# Accessible via:
attestation = result.attestation
print(attestation.id)        # UUID
print(attestation.decision)  # "allowed"
print(attestation.invariants) # ["ownership", "lifecycle"]
```

### Deprecations

None in v2.8. Clean upgrade path.

---

## 📝 How to Contribute

1. **Test Implementation**: Help implement the 39 required tests
2. **Edge Cases**: Identify additional failure modes
3. **Performance**: Optimize hot-path latency
4. **Documentation**: Improve attestation schema docs
5. **Tooling**: Build attestation visualization tools

---

## Appendix A: Registrum Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Registrum System                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐     ┌─────────────┐     ┌──────────────┐  │
│  │   Actors    │     │  Registrar  │     │ Attestation  │  │
│  │  (agents,   │ ──→ │ (decision   │ ──→ │    Log       │  │
│  │   users,    │     │   engine)   │     │              │  │
│  │   plugins)  │     └──────┬──────┘     └──────────────┘  │
│  └─────────────┘            │                               │
│                             ▼                               │
│                    ┌─────────────┐                          │
│                    │   Runtime   │                          │
│                    │  (streams,  │                          │
│                    │   state)    │                          │
│                    └─────────────┘                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Decision Flow

```
Actor Request
     │
     ▼
┌─────────────────┐
│ Validate Actor  │ ← Is actor registered?
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Check Ownership │ ← Does actor own target?
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Check Override  │ ← Accessibility active?
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Check Lifecycle │ ← Valid transition?
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Create Attest.  │ ← Record decision
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Execute/Deny    │ ← Apply decision
└─────────────────┘
```

---

## Appendix B: Attestation Format

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "timestamp", "actor", "action", "target", "decision"],
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "actor": {
      "type": "object",
      "properties": {
        "id": { "type": "string" },
        "type": { "enum": ["user", "agent", "plugin", "system"] }
      }
    },
    "action": {
      "enum": ["start", "stop", "interrupt", "transfer", "override"]
    },
    "target": {
      "type": "string",
      "description": "Stream ID"
    },
    "decision": {
      "enum": ["allowed", "denied"]
    },
    "reason": {
      "type": "string",
      "description": "Denial reason if denied"
    },
    "invariants": {
      "type": "array",
      "items": { "type": "string" }
    },
    "accessibility_override": {
      "type": "boolean"
    },
    "parent": {
      "type": "string",
      "format": "uuid",
      "description": "Causal parent attestation"
    }
  }
}
```

### Example Attestation

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2027-03-15T14:30:00.123Z",
  "actor": {
    "id": "agent-claude-001",
    "type": "agent"
  },
  "action": "interrupt",
  "target": "stream-xyz-789",
  "decision": "denied",
  "reason": "accessibility_override",
  "invariants": ["ownership", "accessibility"],
  "accessibility_override": true,
  "parent": "98765432-dcba-0987-fedc-ba0987654321"
}
```

---

## Appendix C: Test Implementation Guide

### Test Harness Setup

```python
import pytest
from voice_soundboard.registrum import Registrar, Attestation
from voice_soundboard.testing import RegistrumTestHarness

@pytest.fixture
def harness():
    """Create isolated test environment."""
    return RegistrumTestHarness(
        capture_attestations=True,
        deterministic_time=True,
    )

@pytest.fixture
def registrar(harness):
    """Create registrar with test harness."""
    return Registrar(harness=harness)
```

### Example Test Implementation

```python
# tests/registrum/test_mediation.py

class TestRegistrarMediation:
    """4.8.1 Registrar Mediation Tests"""
    
    def test_interrupt_without_registrar_fails(self, harness, runtime):
        """Starting a stream without registrar decision → fails"""
        stream_id = harness.create_stream()
        
        with pytest.raises(RegistrarRequiredError) as exc:
            runtime.interrupt(stream_id)
        
        assert exc.value.action == "interrupt"
        assert exc.value.stream_id == stream_id
    
    def test_all_mutations_attested(self, harness, registrar, runtime):
        """Every state change produces attestation"""
        stream_id = harness.create_stream()
        
        registrar.request("start", harness.agent, stream_id)
        registrar.request("interrupt", harness.agent, stream_id)
        
        attestations = harness.get_attestations()
        assert len(attestations) == 2
        assert attestations[0].action == "start"
        assert attestations[1].action == "interrupt"
```

---

*Last updated: 2027-02-07*
