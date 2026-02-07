# 🧭 Voice Soundboard v2.9 — v3 Preflight Release

**Target**: Q1 2027  
**Theme**: "Freeze, Prove, and Prepare"  
**Purpose**: Eliminate unknowns before v3  
**Breaking Changes**: ❌ None  
**Rule**: No new capabilities, only guarantees

---

## Executive Intent

> **v2.9 exists to prove that the system's control plane, state authority, and invariants are complete and stable enough that v3 can focus exclusively on audio power.**

If v2.9 is skipped or rushed, v3 will inherit invisible debt.

---

## What v2.9 Is NOT

v2.9 explicitly does **not** add:

| ❌ Excluded | Reason |
|-------------|--------|
| New DSP features | Belongs in v3 |
| New backends | Belongs in v3 |
| New registrum concepts | Control plane is frozen |
| New MCP tools | Contract is frozen |
| New audio primitives | Audio plane is v3 territory |

**Those belong in v3.**

---

## 🎯 Core Objectives

### 1️⃣ Lock the Control Plane (P0)

**Status**: Not started  
**Effort**: Medium  
**Risk**: Low (if v2.8 is complete)

By v2.9:

- [ ] Registrar APIs are frozen
- [ ] State schema is versioned
- [ ] Invariants are finalized
- [ ] No new state types may be added
- [ ] No new transitions without explicit RFC

📌 **This is the last point to change control semantics before v3.**

#### Control Plane Freeze Specification

```python
# FROZEN: These types cannot change after v2.9

from voice_soundboard.runtime.registrar import (
    # State types (FROZEN)
    StreamState,      # IDLE, COMPILING, SYNTHESIZING, PLAYING, INTERRUPTING, STOPPED, FAILED
    StreamOwnership,  # agent_id, claimed_at, transferred_from
    
    # Action types (FROZEN)
    TransitionAction, # START, COMPILE, SYNTHESIZE, PLAY, INTERRUPT, STOP, FAIL, RESTART, etc.
    
    # Decision types (FROZEN)
    TransitionResult, # allowed, reason, attestation_id
    
    # Invariant types (FROZEN)
    InvariantLevel,   # INFO, WARN, DENY, HALT
)

# Version declaration
REGISTRAR_SCHEMA_VERSION = "2.9.0"
STATE_SCHEMA_FROZEN = True
```

#### RFC Process for Post-v2.9 Changes

Any control plane change after v2.9 requires:

1. **RFC Document** — Full justification with use cases
2. **Migration Plan** — How existing code adapts
3. **Test Coverage** — Must not break existing tests
4. **Sign-off** — Core maintainer approval

---

### 2️⃣ Prove Registrum Completeness (P0)

**Status**: Tests exist from v2.8, enforcement needed  
**Effort**: Medium  
**Risk**: Medium

v2.9 must **prove**, not assume:

- [ ] Every meaningful state transition is registered
- [ ] No runtime mutation bypass exists
- [ ] All denials are attested
- [ ] Replay can explain real production traces
- [ ] Accessibility supremacy is unbreakable

**This is where 4.8 tests become mandatory CI gates.**

#### Completeness Proof Matrix

| Claim | Test Section | CI Gate |
|-------|--------------|---------|
| All transitions registered | 4.8.1, 4.8.2 | ✅ Required |
| No bypass exists | 4.8.1, 4.8.9 | ✅ Required |
| All denials attested | 4.8.6 | ✅ Required |
| Replay explains traces | 4.8.7 | ✅ Required |
| Accessibility dominant | 4.8.4 (CRITICAL) | ✅ Required |

#### Production Trace Validation

```python
from voice_soundboard.testing import TraceValidator

# Load real production traces
validator = TraceValidator()
traces = validator.load_traces("production/2027-01/")

# Prove replay explains them
for trace in traces:
    result = validator.replay_and_verify(trace)
    assert result.explained, f"Unexplained behavior in {trace.id}"
    assert result.deterministic, f"Non-deterministic replay in {trace.id}"
```

---

### 3️⃣ v3 Compatibility Audit (P0)

**Status**: Not started  
**Effort**: Large  
**Risk**: High (if issues found)

v2.9 must explicitly answer:

> **"If we add mixing, DSP, spatial audio, and cloning tomorrow — will anything break structurally?"**

#### Required Audits

| Audit | Question | Status |
|-------|----------|--------|
| Engine boundary | Is output pure PCM + metadata? | 🔲 Not started |
| Graph extensibility | Can DSP annotations be added safely? | 🔲 Not started |
| Scene/multi-speaker | Is multi-speaker composition ready? | 🔲 Not started |
| Registrar multi-track | Can registrar manage multiple tracks? | 🔲 Not started |
| Single-stream assumption | Are we assuming "single voice, single stream"? | 🔲 Not started |

**If the answer is "maybe" → v2.9 is not done.**

#### Engine Boundary Audit

```python
# REQUIRED: Engine output must be pure PCM + metadata
# No side effects, no state mutations, no registrar calls

class EngineOutput:
    """v2.9 FROZEN: Engine output contract"""
    
    audio: bytes           # Raw PCM data
    sample_rate: int       # e.g., 24000
    channels: int          # 1 (mono) or 2 (stereo)
    format: str            # "pcm_s16le", "pcm_f32le"
    
    # Metadata (extensible for v3)
    metadata: dict         # Phonemes, timing, visemes, etc.
    
    # NO state mutations
    # NO registrar interactions
    # NO side effects
```

#### Graph Extensibility Audit

```python
# REQUIRED: Graph must accept future DSP annotations

@dataclass
class GraphNode:
    """v2.9 FROZEN: Graph node contract"""
    
    node_type: str         # "text", "ssml", "audio", "silence", etc.
    content: Any           # Node-specific content
    
    # Extensible annotations (v3 can add DSP here)
    annotations: dict      # {"dsp": {...}, "spatial": {...}, etc.}
    
    # Timing information
    start_time: float
    duration: float
    
    # NO hardcoded assumptions about single-stream
```

#### Multi-Track Readiness Check

```python
# AUDIT: Registrar must not assume single stream per session

def audit_multi_track_readiness():
    """Check registrar supports multiple concurrent streams"""
    
    registrar = AudioRegistrar()
    
    # Create multiple streams
    stream_a = registrar.create_stream(agent_id="agent_1")
    stream_b = registrar.create_stream(agent_id="agent_1")
    stream_c = registrar.create_stream(agent_id="agent_2")
    
    # All should coexist
    assert registrar.get_state(stream_a) is not None
    assert registrar.get_state(stream_b) is not None
    assert registrar.get_state(stream_c) is not None
    
    # Independent lifecycle
    registrar.advance(stream_a, StreamState.PLAYING)
    registrar.advance(stream_b, StreamState.SYNTHESIZING)
    
    assert registrar.get_state(stream_a).state == StreamState.PLAYING
    assert registrar.get_state(stream_b).state == StreamState.SYNTHESIZING
```

---

### 4️⃣ Performance & Latency Proof (P1)

**Status**: Baseline from v2.8, proof needed  
**Effort**: Medium  
**Risk**: Medium

v2.9 must prove real-time safety:

- [ ] Registrar hot-path p99 < 1 ms
- [ ] No IPC on audio hot path
- [ ] Streaming uninterrupted under load
- [ ] Interrupt latency bounded and consistent
- [ ] No new jitter introduced by registrum

**This is the last chance to fix control-plane latency before DSP multiplies costs.**

#### Performance Budget

| Metric | Budget | Measured | Status |
|--------|--------|----------|--------|
| Registrar request p50 | < 100 µs | TBD | 🔲 |
| Registrar request p99 | < 1 ms | TBD | 🔲 |
| Attestation write p99 | < 500 µs | TBD | 🔲 |
| Interrupt latency p99 | < 5 ms | TBD | 🔲 |
| State lookup p99 | < 50 µs | TBD | 🔲 |

#### Hot-Path Verification

```python
from voice_soundboard.testing import PerformanceHarness

harness = PerformanceHarness()

# Verify no IPC on hot path
with harness.trace_syscalls() as trace:
    registrar.request(
        action=TransitionAction.INTERRUPT,
        actor="agent_1",
        target="stream_1",
    )

assert "socket" not in trace.syscalls
assert "pipe" not in trace.syscalls
assert "futex" not in trace.syscalls or trace.futex_count < 2

# Verify consistent jitter
results = harness.benchmark_n(registrar.request, n=10000, args=...)
assert harness.percentile(results, 99) < 1.0  # ms
assert harness.std_dev(results) < 0.1  # ms (low jitter)
```

#### Load Test Requirements

```python
# v2.9 REQUIRED: Streaming under load

def test_streaming_under_load():
    """Audio streaming must not stutter under registrar load"""
    
    # Start audio stream
    stream = engine.stream("Long text for streaming test...")
    
    # Hammer registrar concurrently
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [
            pool.submit(registrar.request, ...)
            for _ in range(1000)
        ]
    
    # Stream must complete without gaps
    audio = stream.collect()
    gaps = analyze_audio_gaps(audio)
    
    assert len(gaps) == 0, f"Audio gaps detected: {gaps}"
```

---

### 5️⃣ Failure Semantics Finalization (P1)

**Status**: Partially defined in v2.8  
**Effort**: Medium  
**Risk**: Low

v2.9 defines how the system fails — **permanently**.

- [ ] Registrar failure modes documented
- [ ] Runtime safe behavior under registrar denial
- [ ] Partial failure recovery proven
- [ ] No "undefined behavior" states remain

**v3 must never need to ask: "What happens if X fails?"**

#### Failure Mode Catalog

| Failure | Behavior | Recovery |
|---------|----------|----------|
| Registrar denial | No state change, denial attested | Retry with correct authority |
| Registrar crash | Safe halt, no partial state | Replay from attestations |
| Invalid transition | Denied, state unchanged | Request valid transition |
| Ownership violation | Denied, violation logged | Request with correct owner |
| Accessibility override | Agent blocked, user notified | User disables override |
| Attestation write failure | Request retried or denied | Retry with backoff |

#### Undefined Behavior Elimination

```python
# v2.9 REQUIRED: No undefined states

DEFINED_STATES = {
    StreamState.IDLE,
    StreamState.COMPILING,
    StreamState.SYNTHESIZING,
    StreamState.PLAYING,
    StreamState.INTERRUPTING,
    StreamState.STOPPED,
    StreamState.FAILED,
}

def test_no_undefined_states():
    """Every stream must be in a defined state"""
    
    registrar = AudioRegistrar()
    
    # Fuzz test: random operations
    for _ in range(10000):
        stream = registrar.create_stream(agent_id=random_agent())
        
        for _ in range(100):
            action = random_action()
            registrar.request(action=action, ...)
        
        # State must always be defined
        state = registrar.get_state(stream)
        assert state.state in DEFINED_STATES
```

#### Safe Halt Specification

```python
# v2.9 FROZEN: Safe halt contract

class SafeHalt:
    """
    When the system cannot proceed safely, it halts.
    
    Guarantees:
    - No partial state changes
    - All in-flight operations rolled back
    - Attestation of halt reason
    - Recovery path documented
    """
    
    def __init__(self, reason: str, context: dict):
        self.reason = reason
        self.context = context
        self.timestamp = time.time()
        
    def recover(self) -> AudioRegistrar:
        """Recover from safe halt via replay"""
        attestations = self.context.get("last_known_attestations", [])
        return AudioRegistrar.replay(attestations)
```

---

### 6️⃣ Developer & Agent Contract Freeze (P1)

**Status**: Not started  
**Effort**: Small  
**Risk**: Low

By v2.9:

- [ ] MCP schemas frozen
- [ ] Decision/attestation formats frozen
- [ ] Observability fields stable
- [ ] No behavioral surprises for agents
- [ ] Clear version negotiation strategy

**This protects the ecosystem before v3 breaking changes.**

#### MCP Schema Freeze

```json
{
  "$schema": "https://voice-soundboard.io/schemas/mcp/v2.9.json",
  "version": "2.9.0",
  "frozen": true,
  
  "tools": {
    "speak": {
      "description": "Synthesize and play audio",
      "parameters": {
        "text": { "type": "string", "required": true },
        "voice": { "type": "string", "required": false },
        "interrupt": { "type": "boolean", "required": false }
      }
    },
    "interrupt": {
      "description": "Interrupt current audio",
      "parameters": {
        "stream_id": { "type": "string", "required": false }
      }
    },
    "query_state": {
      "description": "Query stream state",
      "parameters": {
        "stream_id": { "type": "string", "required": true }
      }
    }
  }
}
```

#### Attestation Format Freeze

```python
# v2.9 FROZEN: Attestation format

@dataclass
class Attestation:
    """Frozen attestation format for v2.9+"""
    
    # Identity (required)
    id: str                    # Unique attestation ID
    timestamp: float           # Unix timestamp
    
    # Action (required)
    action: str                # TransitionAction name
    actor: str                 # Who requested
    target: str                # Stream ID
    
    # Decision (required)
    decision: str              # "allowed" or "denied"
    reason: str                # Human-readable explanation
    
    # Context (optional, extensible)
    parameters: dict           # Action parameters
    invariants_checked: list   # Which invariants were evaluated
    
    # Extensible metadata (v3 can add fields here)
    metadata: dict             # Future-proof extension point
```

#### Version Negotiation

```python
# v2.9: Clear version negotiation

class VersionNegotiator:
    """
    Agents can query supported versions and negotiate.
    
    v2.9 supports: 2.6, 2.7, 2.8, 2.9
    v3.0 will support: 2.9, 3.0 (2.8 and earlier deprecated)
    """
    
    SUPPORTED_VERSIONS = ["2.6", "2.7", "2.8", "2.9"]
    CURRENT_VERSION = "2.9"
    
    @classmethod
    def negotiate(cls, requested: str) -> str:
        """Return best compatible version"""
        if requested in cls.SUPPORTED_VERSIONS:
            return requested
        # Fall back to current
        return cls.CURRENT_VERSION
```

---

## 🧪 Required v2.9 Test Additions

v2.9 does not add many new tests, but it **enforces** them.

### Mandatory Test Gates

| Test Suite | Requirement | Failure Action |
|------------|-------------|----------------|
| 4.8 Registrum integration | All passing | Block release |
| Long-running soak tests | 8 hours stable | Block release |
| Concurrency stress tests | No races | Block release |
| Replay correctness | Real traces explained | Block release |
| Accessibility regression | Zero bypasses | Block release |

**If a test flakes → v2.9 blocks.**

### Soak Test Specification

```python
# v2.9 REQUIRED: 8-hour soak test

def test_long_running_soak():
    """System must run 8 hours without degradation"""
    
    engine = VoiceEngine()
    registrar = engine.registrar
    
    start = time.time()
    duration = 8 * 60 * 60  # 8 hours
    
    metrics = {
        "requests": 0,
        "errors": 0,
        "latency_samples": [],
        "memory_samples": [],
    }
    
    while time.time() - start < duration:
        # Continuous operation
        stream = registrar.create_stream(agent_id="soak_agent")
        
        start_req = time.time()
        result = registrar.request(...)
        metrics["latency_samples"].append(time.time() - start_req)
        
        metrics["requests"] += 1
        if not result.allowed:
            metrics["errors"] += 1
        
        # Memory check every minute
        if metrics["requests"] % 1000 == 0:
            metrics["memory_samples"].append(get_memory_usage())
        
        time.sleep(0.01)  # ~100 requests/second
    
    # Verify no degradation
    assert metrics["errors"] / metrics["requests"] < 0.001  # <0.1% error rate
    assert not is_memory_leaking(metrics["memory_samples"])
    assert not is_latency_degrading(metrics["latency_samples"])
```

### Concurrency Stress Test

```python
# v2.9 REQUIRED: Stress test with race detection

def test_concurrency_stress():
    """No races under concurrent load"""
    
    registrar = AudioRegistrar()
    errors = []
    
    def worker(worker_id):
        for _ in range(1000):
            stream = registrar.create_stream(agent_id=f"worker_{worker_id}")
            
            # Race condition scenario
            results = parallel(
                lambda: registrar.request(action=TransitionAction.START, ...),
                lambda: registrar.request(action=TransitionAction.CLAIM, ...),
                lambda: registrar.request(action=TransitionAction.INTERRUPT, ...),
            )
            
            # State must be consistent
            state = registrar.get_state(stream)
            if state.state not in DEFINED_STATES:
                errors.append(f"Invalid state: {state}")
    
    # 20 concurrent workers
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(worker, i) for i in range(20)]
        wait(futures)
    
    assert len(errors) == 0, f"Race conditions detected: {errors}"
```

---

## 📦 Documentation Deliverables (Non-Optional)

v2.9 must ship with:

| Document | Description | Status |
|----------|-------------|--------|
| State Model & Invariants | Complete reference | 🔲 Not started |
| Registrar Architecture | Design document | 🔲 Not started |
| MCP + Registrar Flow | Sequence diagrams | 🔲 Not started |
| v3 Readiness Declaration | Audit results | 🔲 Not started |
| v3 Breaking Changes List | What v3 can break | 🔲 Not started |

**This is not marketing — it's engineering continuity.**

### State Model & Invariants Reference

```markdown
# State Model & Invariants Reference (v2.9)

## States

| State | Description | Valid Transitions |
|-------|-------------|-------------------|
| IDLE | Stream created, not started | START |
| COMPILING | Text being compiled | SYNTHESIZE, FAIL |
| SYNTHESIZING | Audio being generated | PLAY, FAIL |
| PLAYING | Audio playing | INTERRUPT, STOP, FAIL |
| INTERRUPTING | Interrupt in progress | STOPPED |
| STOPPED | Playback complete | RESTART, RELEASE |
| FAILED | Error occurred | RESTART, RELEASE |

## Invariants

| Invariant | Level | Description |
|-----------|-------|-------------|
| SingleOwnerInvariant | DENY | One owner per stream |
| OwnershipRequiredInvariant | DENY | Actions require ownership |
| AccessibilitySupremacyInvariant | HALT | User override beats all |
| AccessibilityAuditableInvariant | WARN | Override must be logged |

## Transitions

[Full transition matrix...]
```

### v3 Breaking Changes List

```markdown
# v3 Allowed Breaking Changes

v3 MAY break:

1. **Audio output format** — May change from PCM to other formats
2. **Graph internal structure** — May add DSP nodes
3. **Engine parameters** — May add required parameters
4. **Performance characteristics** — May change latency profile

v3 MUST NOT break:

1. **Registrar semantics** — Control plane frozen at v2.9
2. **Attestation format** — Audit trail must be compatible
3. **MCP tool signatures** — Existing tools work unchanged
4. **State model** — States and transitions unchanged
```

---

## 🚦 v2.9 Release Gate (Hard)

v2.9 ships **only if all are true**:

| Gate | Requirement | Status |
|------|-------------|--------|
| State authority | Centralized and enforced | 🔲 |
| Bypass prevention | Registrum cannot be bypassed | 🔲 |
| Accessibility | Provably dominant | 🔲 |
| Replay | Explains production behavior | 🔲 |
| Performance | Unchanged from v2.6 | 🔲 |
| v3 compatibility | No control-plane changes needed | 🔲 |

**If even one is false → v2.9 slips.**

### Release Checklist

```markdown
## v2.9 Release Checklist

### P0 Gates (Must Pass)

- [ ] All 4.8 tests passing in CI
- [ ] Control plane freeze verified
- [ ] Registrum completeness proven
- [ ] v3 compatibility audit complete
- [ ] No "maybe" answers in audit

### P1 Gates (Should Pass)

- [ ] Performance budget met
- [ ] Failure semantics documented
- [ ] Developer contracts frozen
- [ ] 8-hour soak test passed

### Documentation

- [ ] State Model & Invariants published
- [ ] Registrar Architecture published
- [ ] MCP flow diagrams published
- [ ] v3 readiness declaration signed

### Sign-off

- [ ] Core maintainer approval
- [ ] No open P0 issues
- [ ] Changelog complete
```

---

## 📅 Timeline

```
2026-11-01  v2.8.0 released
     │
     ▼
2026-11-15  v2.9 planning begins
     │      - Identify audit scope
     │      - Assign documentation owners
     │
     ▼
2026-12-01  v2.9-alpha.1
     │      - Control plane freeze implemented
     │      - Audit tooling ready
     │
     ▼
2027-01-01  v2.9-alpha.2
     │      - v3 compatibility audits complete
     │      - Performance proof collected
     │
     ▼
2027-01-15  v2.9-beta.1
     │      - All documentation complete
     │      - Soak tests passing
     │
     ▼
2027-02-01  v2.9-rc.1
     │      - Release gates verified
     │      - Final sign-off
     │
     ▼
2027-02-15  v2.9.0 release
     │
     ▼
2027-03-01  v3.0 development begins
```

---

## Why v2.9 Matters More Than It Looks

v2.9 is the release that determines whether:

✅ **v3 is a clean leap forward**

or

❌ **v3 becomes a multi-release cleanup effort**

Teams that skip this step pay for it later — every time.

---

## The One-Line Answer

> **v2.9 should be the "nothing new, everything proven" release that freezes the control plane so v3 can safely explode the audio plane.**

---

*Last updated: 2026-02-07*
