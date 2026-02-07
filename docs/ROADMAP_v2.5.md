# Voice Soundboard v2.5 Roadmap

**Target**: Q1 2027  
**Theme**: "MCP Integration & Agent Interoperability"

---

## Executive Summary

v2.5 makes Voice Soundboard a first-class, agent-native capability by introducing Model Context Protocol (MCP) integration.

This release does not introduce new audio primitives or DSP features.
Instead, it focuses on:

- **Agent interoperability** — standardized tool interfaces for speech
- **Control surfaces** — interruption, streaming, session ownership
- **Observability for agents** — structured metadata, not logs
- **Safety & permissions** — clear boundaries for agent-driven audio

v2.5 completes the control plane so that v3 can focus purely on audio capabilities.

---

## 🎯 Primary Goals

### 1. MCP Server & Tooling (P0)

**Goal**: Expose Voice Soundboard as an MCP-compliant tool provider.

#### Scope

- Embedded MCP server
- Tool registration and discovery
- Streaming-compatible tools
- Schema-driven inputs and outputs

#### Core Tools

| Tool | Purpose |
|------|---------|
| `voice.speak` | Synthesize speech |
| `voice.stream` | Incremental/streaming synthesis |
| `voice.interrupt` | Stop or rollback active audio |
| `voice.list_voices` | Enumerate available voices |
| `voice.status` | Engine health & capabilities |

#### Example Usage

```python
from voice_soundboard.mcp import create_mcp_server

# Create MCP server
server = create_mcp_server(engine)
await server.run()

# Agent calls tool
result = await server.call("voice.speak", {"text": "Hello!"})
```

---

### 2. Agent-Aware Audio Sessions (P0)

**Goal**: Allow agents to reason about ownership, intent, and lifecycle of audio.

#### Capabilities

- Session-scoped synthesis
- Conversation IDs
- Agent ownership of streams
- Priority rules for interruption

```python
from voice_soundboard.mcp import MCPSession, SessionManager

manager = SessionManager()
session = manager.create_session(agent_id="planner")

# Synthesize with session context
result = await server.call(
    "voice.stream",
    {"text": "Let me explain..."},
    session_id=session.session_id,
)
```

#### Invariants

- Only the owning agent can interrupt its audio
- Sessions are isolated
- Deterministic behavior under concurrency

---

### 3. Streaming & Interrupt Semantics (P1)

**Goal**: Make interruption and rollback explicit and predictable.

#### Features

- Interrupt reasons (`user_spoke`, `context_change`, `timeout`)
- Graceful fade-out or rollback
- Structured interrupt acknowledgements

```python
from voice_soundboard.mcp import InterruptReason

# Interrupt with structured reason
result = await server.call("voice.interrupt", {
    "reason": "user_spoke",
    "fade_out_ms": 50,
})

# Response:
# {
#   "event": "voice.interrupted",
#   "reason": "user_spoke",
#   "audio_ms_played": 420
# }
```

---

### 4. Observability for Agents (P1)

**Goal**: Let agents understand audio results, not just trigger them.

#### Returned Metadata

- Synthesis latency
- Audio duration
- Voice + backend used
- Emotion applied
- Cost estimate (if applicable)
- Cache hits

```python
# Result includes structured metadata:
{
    "latency_ms": 138,
    "duration_ms": 1240,
    "voice": "af_bella",
    "backend": "kokoro",
    "emotion": "joy",
    "cost_estimate": 0.0,
    "cache_hit": False,
}
```

**Note**: This is structured output, not debug logs.

---

## 🔧 Secondary Goals

### 5. Permissions & Safety Model (P2)

**Goal**: Prevent agent misuse without hard-coding policy.

#### Features

- Tool-level permissions
- Rate limits per agent
- Capability flags: external backends, emotion detection, analytics

```python
from voice_soundboard.mcp import MCPPolicy, CapabilityFlags

policy = MCPPolicy(
    allow_tools=["voice.speak", "voice.stream"],
    capabilities=CapabilityFlags.STANDARD,
    rate_limit=RateLimitConfig(
        requests_per_minute=60,
        characters_per_minute=10000,
    ),
    allow_external_backends=False,
)
```

This builds on v2.4 security foundations.

---

### 6. MCP ↔ Existing Adapters Parity (P2)

**Goal**: Ensure MCP offers parity with REST/WebSocket adapters.

- Streaming behavior identical
- Same interrupt semantics
- Same audio guarantees
- Same performance characteristics

MCP is a control interface, not a special execution path.

---

### 7. MCP Testing & Simulation (P2)

**Goal**: Make MCP-driven behavior testable.

#### Additions

- Mock MCP clients
- Deterministic test harness
- Replayable agent traces

```python
from voice_soundboard.mcp import MCPMock

with MCPMock() as mcp:
    mcp.on("voice.speak").returns({"audio_path": "/tmp/test.wav"})
    
    # Test your agent
    result = await my_agent.speak("Hello")
    
    mcp.assert_called("voice.speak")
    mcp.assert_called_with("voice.speak", {"text": "Hello"})
```

---

### 8. Documentation & Examples (P3)

#### Deliverables

- "Using Voice Soundboard via MCP" guide
- Agent examples (planner / executor / narrator)
- Interrupt & rollback patterns
- Cost-aware agent examples

---

## 🧱 Relationship to v3

### What v2.5 Enables (But Does Not Ship)

| v3 Feature | v2.5 Preparation |
|------------|------------------|
| True audio mixing | Agent session control |
| Spatial scenes | Agent-driven orchestration |
| Voice cloning | Permission & safety model |
| DSP effects | Control-plane readiness |

v2.5 ensures v3 can expose powerful audio features safely to agents.

---

## 🚫 Explicitly NOT in v2.5

Deferred to v3:

- ❌ New DSP features
- ❌ True PCM mixing
- ❌ Spatial audio rendering
- ❌ Production voice cloning
- ❌ Breaking API changes

---

## 🎯 Success Criteria

### Agent Integration

- MCP tools usable without custom glue
- Streaming + interrupt semantics reliable
- Deterministic behavior under concurrency

### Safety

- No privilege escalation via MCP
- Clear ownership of audio streams

### Developer Experience

- MCP setup < 10 minutes
- Clear schemas and examples
- Easy local testing

---

## 🔄 Migration from v2.4

- ✅ No breaking changes
- ✅ MCP fully opt-in
- ✅ Existing adapters unaffected

```python
# v2.4 code (still works)
engine = VoiceEngine()
result = engine.speak("Hello!")

# v2.5 enhancements (opt-in)
from voice_soundboard.mcp import create_mcp_server

server = create_mcp_server(engine)
await server.run()
```

---

## 📋 Full Feature Matrix

| Feature | Priority | Effort | Status |
|---------|----------|--------|--------|
| MCP Server | P0 | Medium | ✅ Implemented |
| Tool definitions | P0 | Medium | ✅ Implemented |
| Agent sessions | P0 | Medium | ✅ Implemented |
| Interrupt semantics | P1 | Medium | ✅ Implemented |
| Observability metadata | P1 | Small | ✅ Implemented |
| Permissions/policy | P2 | Medium | ✅ Implemented |
| MCP testing utilities | P2 | Small | ✅ Implemented |
| Documentation | P3 | Medium | 🔲 Planned |

---

## 📝 Summary

v2.5 is the "agent bridge" release.

It completes the control plane so that v3 can focus entirely on expressive audio and synthesis power, without revisiting safety, orchestration, or integration concerns.

---

*Last updated: 2026-02-07*
