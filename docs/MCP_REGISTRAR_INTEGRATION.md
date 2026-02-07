# MCP + Registrar Integration (v2.9)

**Version**: 2.9.0 (FROZEN)  
**Status**: Authoritative Reference  
**Last Updated**: 2026-02-07

> ⚠️ **FROZEN**: The MCP ↔ Registrar contract is frozen at v2.9.
> Changes require RFC approval.

---

## Executive Summary

MCP (Model Context Protocol) tools in Voice Soundboard **must** route all state-changing operations through the Audio Registrar. This document specifies the integration contract, flow diagrams, and error handling.

---

## 1. Integration Principles

### 1.1 Core Rules

| Rule | Description |
|------|-------------|
| **No Bypass** | MCP tools cannot directly mutate audio state |
| **Registrar Mediation** | All state changes go through `registrar.request()` |
| **Structured Errors** | Denials return structured error responses |
| **Attestation** | All MCP actions are attested |

### 1.2 MCP ↔ Registrar Contract

```
┌─────────────────────────────────────────────────────────────────────┐
│                           MCP LAYER                                  │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  speak_tool  │  │interrupt_tool│  │ query_tool   │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│         └─────────────────┼─────────────────┘                       │
│                           │                                         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    REGISTRAR GATEWAY                          │  │
│  │   All MCP tools route through registrar.request()            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           │                                         │
└───────────────────────────┼─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AUDIO REGISTRAR                                 │
│                                                                      │
│  Domain Invariants → Registrum Validation → Attestation            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Flow Diagrams

### 2.1 Speak Tool Flow (Success)

```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐     ┌─────────┐
│  Agent  │     │MCP Tool │     │Registrar │     │ Runtime │     │ Audio   │
│         │     │ speak   │     │          │     │         │     │ Output  │
└────┬────┘     └────┬────┘     └────┬─────┘     └────┬────┘     └────┬────┘
     │               │               │               │               │
     │ speak("Hi")   │               │               │               │
     │──────────────►│               │               │               │
     │               │               │               │               │
     │               │ request(START)│               │               │
     │               │──────────────►│               │               │
     │               │               │               │               │
     │               │    allowed    │               │               │
     │               │◄──────────────│               │               │
     │               │               │               │               │
     │               │               │  compile()    │               │
     │               │──────────────────────────────►│               │
     │               │               │               │               │
     │               │ request(COMPILE)              │               │
     │               │──────────────►│               │               │
     │               │    allowed    │               │               │
     │               │◄──────────────│               │               │
     │               │               │               │               │
     │               │               │ synthesize()  │               │
     │               │──────────────────────────────►│               │
     │               │               │               │               │
     │               │ request(PLAY) │               │               │
     │               │──────────────►│               │               │
     │               │    allowed    │               │               │
     │               │◄──────────────│               │               │
     │               │               │               │               │
     │               │               │    play()     │               │
     │               │──────────────────────────────►│──────────────►│
     │               │               │               │    🔊 Audio   │
     │   success     │               │               │               │
     │◄──────────────│               │               │               │
     │               │               │               │               │
```

### 2.2 Interrupt Tool Flow (Ownership Allowed)

```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐
│ Agent A │     │MCP Tool │     │Registrar │     │ Runtime │
│ (owner) │     │interrupt│     │          │     │         │
└────┬────┘     └────┬────┘     └────┬─────┘     └────┬────┘
     │               │               │               │
     │ interrupt()   │               │               │
     │──────────────►│               │               │
     │               │               │               │
     │               │request(INTERRUPT)             │
     │               │  actor=A      │               │
     │               │──────────────►│               │
     │               │               │               │
     │               │ ┌─────────────────────────┐   │
     │               │ │ Check: Is A the owner? │   │
     │               │ │ Result: YES            │   │
     │               │ └─────────────────────────┘   │
     │               │               │               │
     │               │    allowed    │               │
     │               │◄──────────────│               │
     │               │               │               │
     │               │               │  stop_audio() │
     │               │──────────────────────────────►│
     │               │               │               │
     │   success     │               │               │
     │◄──────────────│               │               │
     │               │               │               │
```

### 2.3 Interrupt Tool Flow (Ownership Denied)

```
┌─────────┐     ┌─────────┐     ┌──────────┐
│ Agent B │     │MCP Tool │     │Registrar │
│(not own)│     │interrupt│     │          │
└────┬────┘     └────┬────┘     └────┬─────┘
     │               │               │
     │ interrupt()   │               │
     │──────────────►│               │
     │               │               │
     │               │request(INTERRUPT)
     │               │  actor=B      │
     │               │──────────────►│
     │               │               │
     │               │ ┌─────────────────────────────────┐
     │               │ │ Check: Is B the owner?         │
     │               │ │ Result: NO (owner is A)        │
     │               │ │                                │
     │               │ │ Check: Accessibility override? │
     │               │ │ Result: NO                     │
     │               │ └─────────────────────────────────┘
     │               │               │
     │               │    DENIED     │
     │               │  "Not owner"  │
     │               │◄──────────────│
     │               │               │
     │   error:      │               │
     │ {denied: true,│               │
     │  reason: ".."}│               │
     │◄──────────────│               │
     │               │               │
```

### 2.4 Interrupt Tool Flow (Accessibility Override)

```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌─────────┐
│  User   │     │MCP Tool │     │Registrar │     │ Agent A │
│         │     │interrupt│     │          │     │ (owner) │
└────┬────┘     └────┬────┘     └────┬─────┘     └────┬────┘
     │               │               │               │
     │ [User enabled │               │               │
     │  accessibility│               │               │
     │  override]    │               │               │
     │               │               │               │
     │ interrupt()   │               │               │
     │──────────────►│               │               │
     │               │               │               │
     │               │request(INTERRUPT)             │
     │               │  actor=user   │               │
     │               │──────────────►│               │
     │               │               │               │
     │               │ ┌─────────────────────────────────┐
     │               │ │ Check: Accessibility override? │
     │               │ │ Result: YES                    │
     │               │ │ → Override wins over ownership │
     │               │ └─────────────────────────────────┘
     │               │               │               │
     │               │    allowed    │               │
     │               │ (a11y_driven) │               │
     │               │◄──────────────│               │
     │               │               │               │
     │   success     │               │               │
     │◄──────────────│               │               │
     │               │               │               │
     │               │               │ [Agent A's    │
     │               │               │  audio stops] │
     │               │               │───────────────►
     │               │               │               │
```

### 2.5 Query State Flow

```
┌─────────┐     ┌─────────┐     ┌──────────┐
│  Agent  │     │MCP Tool │     │Registrar │
│         │     │ query   │     │          │
└────┬────┘     └────┬────┘     └────┬─────┘
     │               │               │
     │ query_state() │               │
     │──────────────►│               │
     │               │               │
     │               │ get_state()   │
     │               │──────────────►│
     │               │               │
     │               │  AudioState   │
     │               │◄──────────────│
     │               │               │
     │  {state: ..., │               │
     │   owner: ..., │               │
     │   ...}        │               │
     │◄──────────────│               │
     │               │               │

Note: Query operations are read-only
      and don't require registrar mediation
```

---

## 3. MCP Tool Schemas (Frozen)

### 3.1 speak Tool

```json
{
  "name": "speak",
  "description": "Synthesize and play audio from text",
  "parameters": {
    "text": {
      "type": "string",
      "required": true,
      "description": "Text to synthesize"
    },
    "voice": {
      "type": "string",
      "required": false,
      "description": "Voice ID to use"
    },
    "interrupt": {
      "type": "boolean",
      "required": false,
      "default": false,
      "description": "Whether to interrupt current audio"
    }
  },
  "returns": {
    "stream_id": "string",
    "duration": "number"
  },
  "registrar_actions": ["START", "COMPILE", "SYNTHESIZE", "PLAY"]
}
```

### 3.2 interrupt Tool

```json
{
  "name": "interrupt",
  "description": "Interrupt current audio playback",
  "parameters": {
    "stream_id": {
      "type": "string",
      "required": false,
      "description": "Specific stream to interrupt (default: current)"
    }
  },
  "returns": {
    "interrupted": "boolean",
    "stream_id": "string"
  },
  "registrar_actions": ["INTERRUPT"]
}
```

### 3.3 query_state Tool

```json
{
  "name": "query_state",
  "description": "Query the current state of an audio stream",
  "parameters": {
    "stream_id": {
      "type": "string",
      "required": true,
      "description": "Stream ID to query"
    }
  },
  "returns": {
    "state": "string",
    "owner": "string",
    "accessibility_override": "boolean"
  },
  "registrar_actions": []
}
```

---

## 4. Error Response Format

### 4.1 Structured Error Schema

```json
{
  "error": true,
  "code": "REGISTRAR_DENIED",
  "reason": "Not owner of stream stream_abc123",
  "details": {
    "action": "interrupt",
    "actor": "agent_b",
    "target": "stream_abc123",
    "owner": "agent_a",
    "invariant_violated": "audio.ownership.required_for_interrupt"
  }
}
```

### 4.2 Error Codes

| Code | Description | Recovery |
|------|-------------|----------|
| `REGISTRAR_DENIED` | Invariant violation | Fix and retry |
| `INVALID_ACTION` | Unknown action | Check action name |
| `INVALID_TARGET` | Stream not found | Check stream ID |
| `INVALID_STATE` | Action not valid for state | Wait or use different action |
| `ACCESSIBILITY_OVERRIDE` | User override active | Wait for user |

### 4.3 Denial Response Example

```python
# MCP tool returns denial as structured error
async def interrupt_tool(stream_id: str, context: MCPContext) -> MCPResult:
    result = registrar.request(
        action=TransitionAction.INTERRUPT,
        actor=context.agent_id,
        target=stream_id,
    )
    
    if not result.allowed:
        return MCPResult(
            error=True,
            code="REGISTRAR_DENIED",
            reason=result.reason,
            details={
                "action": "interrupt",
                "actor": context.agent_id,
                "target": stream_id,
                "invariant_violated": result.violations[0].invariant_id if result.violations else None,
            }
        )
    
    # ... handle success
```

---

## 5. Implementation Guidelines

### 5.1 MCP Tool Template

```python
from voice_soundboard.runtime.registrar import (
    AudioRegistrar,
    TransitionAction,
    TransitionResult,
)
from voice_soundboard.mcp import MCPTool, MCPResult, MCPContext


class SpeakTool(MCPTool):
    """MCP tool for text-to-speech synthesis."""
    
    name = "speak"
    
    def __init__(self, registrar: AudioRegistrar, runtime: AudioRuntime):
        self.registrar = registrar
        self.runtime = runtime
    
    async def execute(
        self,
        text: str,
        voice: str | None = None,
        interrupt: bool = False,
        context: MCPContext,
    ) -> MCPResult:
        # 1. Request stream creation via registrar
        start_result = self.registrar.request(
            action=TransitionAction.START,
            actor=context.agent_id,
            metadata={"text": text, "voice": voice},
        )
        
        if not start_result.allowed:
            return self._denial_response(start_result)
        
        stream_id = start_result.effects[0].new_state.stream_id
        
        # 2. Compile (via registrar)
        compile_result = self.registrar.request(
            action=TransitionAction.COMPILE,
            actor=context.agent_id,
            target=stream_id,
        )
        
        if not compile_result.allowed:
            return self._denial_response(compile_result)
        
        # 3. Synthesize (actual work)
        audio = await self.runtime.synthesize(stream_id, text, voice)
        
        # 4. Request play via registrar
        play_result = self.registrar.request(
            action=TransitionAction.PLAY,
            actor=context.agent_id,
            target=stream_id,
        )
        
        if not play_result.allowed:
            return self._denial_response(play_result)
        
        # 5. Play audio
        await self.runtime.play(stream_id, audio)
        
        return MCPResult(
            stream_id=stream_id,
            duration=audio.duration,
        )
    
    def _denial_response(self, result: TransitionResult) -> MCPResult:
        return MCPResult(
            error=True,
            code="REGISTRAR_DENIED",
            reason=result.reason,
            details={
                "invariant_violated": result.violations[0].invariant_id if result.violations else None,
            }
        )
```

### 5.2 Interrupt Tool Template

```python
class InterruptTool(MCPTool):
    """MCP tool for interrupting audio playback."""
    
    name = "interrupt"
    
    async def execute(
        self,
        stream_id: str | None = None,
        context: MCPContext,
    ) -> MCPResult:
        # Find target stream
        if stream_id is None:
            stream_id = self._find_active_stream(context.agent_id)
            if stream_id is None:
                return MCPResult(
                    error=True,
                    code="NO_ACTIVE_STREAM",
                    reason="No active audio stream to interrupt",
                )
        
        # Request interrupt via registrar
        result = self.registrar.request(
            action=TransitionAction.INTERRUPT,
            actor=context.agent_id,
            target=stream_id,
        )
        
        if not result.allowed:
            return MCPResult(
                error=True,
                code="REGISTRAR_DENIED",
                reason=result.reason,
                details={
                    "action": "interrupt",
                    "actor": context.agent_id,
                    "target": stream_id,
                    "invariant_violated": result.violations[0].invariant_id if result.violations else None,
                }
            )
        
        # Execute interrupt
        await self.runtime.stop(stream_id)
        
        return MCPResult(
            interrupted=True,
            stream_id=stream_id,
        )
```

---

## 6. Testing Contracts

### 6.1 Required Test Cases

```python
class TestMCPRegistrarIntegration:
    """Tests for MCP ↔ Registrar contract."""
    
    def test_speak_routes_through_registrar(self):
        """Speak tool must route START through registrar."""
        ...
    
    def test_interrupt_respects_ownership(self):
        """Interrupt denied if not owner (no override)."""
        ...
    
    def test_interrupt_allowed_with_accessibility(self):
        """Interrupt allowed if accessibility override active."""
        ...
    
    def test_denial_returns_structured_error(self):
        """Denial produces structured error response."""
        ...
    
    def test_all_actions_attested(self):
        """All MCP actions produce attestations."""
        ...
```

### 6.2 Contract Verification

```python
def verify_mcp_registrar_contract(tool: MCPTool):
    """Verify tool follows MCP ↔ Registrar contract."""
    
    # 1. Check tool has registrar reference
    assert hasattr(tool, 'registrar'), "Tool must have registrar"
    
    # 2. Check tool routes state changes through registrar
    # (done via testing, not static analysis)
    
    # 3. Check error responses are structured
    # (done via response validation)
```

---

## 7. Version Compatibility

### 7.1 MCP Schema Version

```python
MCP_SCHEMA_VERSION = "2.9.0"
MCP_SCHEMA_FROZEN = True
```

### 7.2 Compatibility Matrix

| MCP Version | Registrar Version | Compatible |
|-------------|-------------------|------------|
| 2.6.x | 2.6.x | ✅ |
| 2.7.x | 2.7.x | ✅ |
| 2.8.x | 2.8.x | ✅ |
| 2.9.x | 2.9.x | ✅ |
| 2.9.x | 3.0.x | ✅ (forward compatible) |
| 3.0.x | 2.9.x | ⚠️ (may have new features) |

### 7.3 v3 Promise

v3 will **not** break:
- Existing MCP tool signatures
- Registrar request() API
- Error response format
- Attestation format

v3 **may** add:
- New MCP tools
- New optional parameters
- New error codes
- New metadata fields

---

## Appendix A: Complete Flow Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              AGENT REQUEST                                  │
│                          "Say 'Hello World'"                               │
└─────────────────────────────────┬──────────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                              MCP LAYER                                      │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                         speak_tool                                  │   │
│  │  1. Parse parameters                                               │   │
│  │  2. Route to registrar                                             │   │
│  └────────────────────────────────┬───────────────────────────────────┘   │
└───────────────────────────────────┼────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           AUDIO REGISTRAR                                   │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  request(START, actor="agent_1")                                   │   │
│  │                                                                     │   │
│  │  ┌────────────────────────────────────────────────────────────┐   │   │
│  │  │              DOMAIN INVARIANT CHECK                        │   │   │
│  │  │  ✓ ownership.single_owner                                  │   │   │
│  │  │  ✓ accessibility.supremacy                                 │   │   │
│  │  │  ✓ lifecycle.valid_transition                              │   │   │
│  │  └────────────────────────────────────────────────────────────┘   │   │
│  │                            │                                       │   │
│  │                            ▼                                       │   │
│  │  ┌────────────────────────────────────────────────────────────┐   │   │
│  │  │              REGISTRUM VALIDATION                          │   │   │
│  │  │  ✓ identity invariants (3)                                 │   │   │
│  │  │  ✓ lineage invariants (4)                                  │   │   │
│  │  │  ✓ ordering invariants (4)                                 │   │   │
│  │  └────────────────────────────────────────────────────────────┘   │   │
│  │                            │                                       │   │
│  │                            ▼                                       │   │
│  │  ┌────────────────────────────────────────────────────────────┐   │   │
│  │  │              DECISION: ALLOWED                             │   │   │
│  │  │  - Create attestation                                      │   │   │
│  │  │  - Update state: IDLE → COMPILING                         │   │   │
│  │  │  - Return TransitionResult                                 │   │   │
│  │  └────────────────────────────────────────────────────────────┘   │   │
│  └────────────────────────────────┬───────────────────────────────────┘   │
└───────────────────────────────────┼────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           AUDIO RUNTIME                                     │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  1. Compile text to graph                                          │   │
│  │  2. registrar.request(COMPILE) → ALLOWED                          │   │
│  │  3. Synthesize audio                                               │   │
│  │  4. registrar.request(PLAY) → ALLOWED                             │   │
│  │  5. Play audio through output                                      │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┼────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                              🔊 AUDIO OUTPUT                                │
│                            "Hello World"                                    │
└────────────────────────────────────────────────────────────────────────────┘
```

---

*This document is the authoritative reference for MCP ↔ Registrar integration in Voice Soundboard v2.9.*
*Changes require RFC approval. See ROADMAP_v2.9.md for change process.*
