# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.5.0-alpha.1] - 2026-XX-XX

### Overview

**MCP Integration & Agent Interoperability** - The agent bridge release.

v2.5 makes Voice Soundboard a first-class, agent-native capability through Model Context
Protocol (MCP) integration. This release completes the control plane, enabling v3 to focus
purely on audio capabilities. No breaking changes from v2.4.

### Added

#### MCP Server & Tooling (P0)
- **MCPServer** - Embedded MCP-compliant server
  - Tool registration and discovery
  - WebSocket transport support
  - Configurable concurrency limits
  - Request timeout handling
- **Core Tools** - Standardized agent interfaces
  - `voice.speak` - Synthesize speech with emotion support
  - `voice.stream` - Incremental streaming synthesis
  - `voice.interrupt` - Stop/rollback active audio
  - `voice.list_voices` - Enumerate available voices
  - `voice.status` - Engine health and capabilities
- **ToolRegistry** - Tool management and discovery
  - Schema-driven inputs/outputs
  - Category-based organization

#### Agent-Aware Sessions (P0)
- **MCPSession** - Session-scoped synthesis
  - Agent ownership of streams
  - Conversation ID tracking
  - Stream registration and lifecycle
- **SessionManager** - Session lifecycle management
  - Automatic expiration cleanup
  - Per-agent session tracking
  - Priority-based interruption rules
- **SessionConfig** - Configurable session behavior
  - Timeout settings
  - Concurrent stream limits
  - Priority levels

#### Streaming & Interrupt Semantics (P1)
- **InterruptHandler** - Explicit interrupt handling
  - Structured interrupt reasons (user_spoke, context_change, timeout, etc.)
  - Graceful fade-out support
  - Rollback point tracking
- **InterruptEvent** - Structured interrupt events
  - Audio played/remaining metrics
  - Interrupt acknowledgements
- **InterruptReason** - Standardized reason codes
  - USER_SPOKE, CONTEXT_CHANGE, TIMEOUT, MANUAL, PRIORITY, ERROR

#### Observability for Agents (P1)
- **SynthesisMetadata** - Structured output metadata
  - Synthesis latency
  - Audio duration
  - Voice and backend info
  - Applied emotion
  - Cost estimates
  - Cache hit status
- **MetadataCollector** - Metadata tracking
  - Per-operation tracking
  - Cost estimation with backend pricing
  - Aggregate statistics
- **BackendPricing** - Cost tracking for cloud backends

#### Permissions & Safety (P2)
- **MCPPolicy** - Agent permission configuration
  - Tool-level access control
  - Rate limiting (requests, characters, streams)
  - Backend restrictions
  - Text length limits
- **PolicyEnforcer** - Policy enforcement
  - Tool, voice, and backend access checks
  - Rate limit enforcement
  - Violation tracking
- **CapabilityFlags** - Fine-grained capability control
  - SPEAK, STREAM, INTERRUPT, LIST_VOICES, STATUS
  - EXTERNAL_BACKENDS, EMOTION_DETECTION, VOICE_CLONING
  - Preset levels (BASIC, STANDARD, FULL, ALL)

#### MCP Testing (P2)
- **MCPMock** - Mock MCP client for testing
  - Response configuration
  - Call recording
  - Assertion helpers (assert_called, assert_called_with)
- **MCPTestHarness** - Deterministic test harness
  - Trace recording
  - Trace replay
  - File serialization

### Dependencies

New optional dependencies (`mcp-server` extra):
- `mcp>=1.0.0` - Model Context Protocol
- `pydantic>=2.0.0` - Schema validation
- `fastapi>=0.109.0` - API framework (optional)
- `uvicorn>=0.27.0` - ASGI server (optional)

### Migration

No breaking changes. MCP is fully opt-in:

```python
# Existing code works unchanged
engine = VoiceEngine()
result = engine.speak("Hello!")

# Opt-in to MCP
from voice_soundboard.mcp import create_mcp_server
server = create_mcp_server(engine)
await server.run()
```

---

## [2.4.0-alpha.1] - 2026-XX-XX

### Overview

**Production Scale & Audio Intelligence** - The final bridge release before v3.

v2.4 adds enterprise-grade security, cloud deployment infrastructure, audio intelligence
features, and production observability tools. No breaking changes from v2.3.

### Added

#### Security (P0)
- **Plugin Sandbox** - RestrictedPython-based isolation for plugin execution
  - Resource monitoring (memory, CPU limits)
  - Restricted globals (no file I/O, network, or os access)
  - Configurable timeout protection
- **Input Validation** - SSML injection prevention
  - Tag whitelisting (break, prosody, say-as, phoneme, etc.)
  - Attribute validation
  - Text length limits
- **Audit Logging** - Security event tracking
  - Structured events with context
  - File and custom backends
  - Tamper detection
- **Rate Limiting** - Token bucket and sliding window algorithms
  - Per-user, per-IP, per-API-key limiting
  - Redis or in-memory backends
- **Secret Management** - Secure API key handling
  - Environment variable backend
  - Memory-only storage option

#### Audio Intelligence (P1)
- **Emotion Detection** - Text emotion analysis
  - Transformer-based detection (optional)
  - Keyword-based fallback
  - Six emotion categories with prosody mapping
- **Adaptive Pacing** - Content-aware speed adjustment
  - Different rates for titles, code, definitions, stories
  - Automatic content type detection
- **Smart Silence** - Semantic pause insertion
  - Paragraph, sentence, clause, emphasis pauses
  - Configurable duration ranges

#### Deployment Infrastructure (P0)
- **Serverless Handlers** - Cloud function deployment
  - AWS Lambda with S3 and CloudWatch integration
  - GCP Cloud Functions with GCS integration
  - Azure Functions with Blob Storage and App Insights
  - Provider-agnostic base handler
- **Distributed Synthesis** - Horizontal scaling
  - `SynthesisCluster` with load balancing (round-robin, least-loaded, random)
  - Health checking and automatic failover
  - `ModelShard` for multi-GPU model distribution
  - `SynthesisQueue` with Redis or in-memory backends

#### Analytics (P3)
- **Usage Tracking** - Request and usage analytics
  - Per-voice, per-client, per-backend metrics
  - Prometheus export support
  - Latency percentiles (p50, p95, p99)
- **Quality Monitoring** - Voice quality tracking
  - Pronunciation, naturalness, timing scores
  - Regression detection
  - Alert notifications
- **Cost Attribution** - Backend cost tracking
  - Per-character pricing by backend
  - Client cost attribution
  - Usage forecasting

#### Advanced Audio (P2)
- **Scene Composition** - Multi-layer audio scenes
  - Speech, music, ambiance, effect layers
  - Per-layer volume, pan, timing, fades
  - `SceneBuilder` fluent API for podcasts/audiobooks
  - `SceneMixer` with music ducking
- **Procedural Ambiance** - Background audio generation
  - 18+ presets (rain, cafe, office, forest, etc.)
  - Noise types: white, pink, brown, blue
  - Volume modulation and seamless looping
- **Spatial Audio** - 3D positioning
  - HRTF-based spatialization (ITD/ILD)
  - Distance attenuation models
  - `SpatialScene` for multi-source positioning
  - Animation keyframes for moving sources

#### Backend Ecosystem (P2)
- **ElevenLabs Backend** - Premium cloud TTS
  - Ultra-realistic voice synthesis
  - Voice cloning support
  - Emotion/style control via stability/similarity
  - Streaming support
- **Azure Neural TTS Backend** - Microsoft Azure integration
  - Neural TTS with 50+ voices
  - SSML with speaking styles
  - Style selection (cheerful, sad, angry, etc.)

#### Developer Tools (P3)
- **Testing Utilities** - Test helpers
  - `VoiceMock` - Configurable mock backend
  - `AudioAssertions` - Audio quality assertions
  - `AudioBuilder` - Fluent test audio creation
  - Sample texts and fixtures

### Changed
- Version bumped to 2.4.0-alpha.1
- Added optional dependencies: elevenlabs, azure-cognitiveservices-speech, 
  restrictedpython, redis, grpcio, prometheus-client, transformers, torch

### Unchanged (Public API Compatibility)
- `VoiceEngine.speak()` - same signature
- `SpeechResult` - same fields
- All v2.3 features remain fully compatible

---

## [2.0.0] - 2026-02-07

### Overview

**Architectural refactor with identical public API semantics.**

v2 is a complete internal rewrite that separates compilation (intent) from synthesis (execution).
The public API (`VoiceEngine.speak()`) is unchanged. If your v1 code works, it works in v2.

### Added

- **Compiler/Engine Architecture**
  - `ControlGraph` intermediate representation (frozen as v1, ABI-stable)
  - Compiler transforms text + emotion + style into graph (all features here)
  - Engine transforms graph into PCM (no feature knowledge)

- **Piper Backend**
  - 30+ voices across English, German, French, Spanish
  - CPU-only operation (no GPU required)
  - 22050 Hz sample rate
  - Kokoro voice compatibility shims

- **Paralinguistic Events**
  - Timeline-based non-speech events (laugh, sigh, breath, etc.)
  - Events are timeline inserts, not overlays
  - Deterministic timing guarantees

- **Audio Event Adapter**
  - WAV asset insertion for paralinguistics
  - Manifest-driven asset management
  - Sample rate matching and validation

- **Incremental Compiler**
  - Streaming text input with commit boundaries
  - Sentence-level graph emission
  - Deterministic output (identical input → identical graphs)

- **Ducking System**
  - Gain envelope processing for speech following events
  - Preserves timeline invariants (no overlap)
  - Optional, adapter-level feature

- **Property-Based Testing**
  - Hypothesis-based random timeline testing
  - Golden tests with exact millisecond expectations
  - 208 tests covering timing invariants

- **CI Pipeline**
  - Architecture invariant enforcement
  - Audio asset validation
  - Multi-Python version testing (3.10, 3.11, 3.12)

### Changed

- Internal module structure completely reorganized:
  - `voice_soundboard/compiler/` - all feature logic
  - `voice_soundboard/engine/` - pure synthesis
  - `voice_soundboard/graph/` - canonical IR
  - `voice_soundboard/runtime/` - streaming, ducking
  - `voice_soundboard/adapters/` - API, CLI

- Speed semantics standardized:
  - All backends: `speed > 1.0` = faster
  - Piper internally inverts to `length_scale`

### Unchanged (Public API Compatibility)

- `VoiceEngine.speak()` - same signature, same return type
- `SpeechResult` - same fields
- `Config` - same options
- `quick_speak()` - same behavior
- Voice IDs - same names work
- Return types - bytes/generator/stream

### Architecture Invariants (Enforced)

These rules are tested and cannot be violated:

1. `engine/` never imports from `compiler/`
2. `engine/` never imports from `adapters/`
3. Compiler emits only `ControlGraph`
4. Backends perform all lowering
5. Engine never mixes PCM
6. Audio events handled only in `runtime/adapters`

### Backend Differences

| Property | Kokoro | Piper |
|----------|--------|-------|
| Sample Rate | 24000 Hz | 22050 Hz |
| GPU Support | Yes | No |
| Speed Control | Direct multiplier | `length_scale` (inverted) |
| Voice Count | ~10 | 30+ |
| Paralinguistics | Lossy fallback | Lossy fallback |

### Explicitly Deferred to v2.x/v3

These features are **not** in v2.0.0 and will not be added without a version bump:

- ⏳ Incremental text streaming (word-by-word speculative synthesis)
- ⏳ Native paralinguistics in all backends
- ⏳ True PCM mixing / sidechain compression
- ⏳ Real-time voice cloning
- ⏳ DSP-heavy effects

### Migration

See [MIGRATION_v1_to_v2.md](docs/MIGRATION_v1_to_v2.md) for detailed migration guide.

**TL;DR**: If you only use the public API, no changes required.

## [1.x] - Previous

See the v1 branch for historical changelog.
