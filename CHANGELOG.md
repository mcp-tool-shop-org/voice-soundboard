# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
