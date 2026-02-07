# Voice Soundboard v3 Roadmap

**Target**: 2027  
**Theme**: "Audio Power"

---

## Executive Summary

v3 is the audio capabilities release. Because v2.7–v2.9 established **state authority** and **control-plane stability**, v3 enjoys a rare luxury:

> **v3 can be unapologetically audio-first without re-litigating safety, state, or agents.**

This release introduces:

1. **Multi-Track Mixing** — Parallel audio streams, crossfades, layer composition
2. **DSP Effects Chain** — Graph-native reverb, EQ, compression, limiting
3. **3D Spatial Audio** — Binaural rendering, HRTF, speaker positioning
4. **Voice Cloning** — Production-grade, permission-gated cloning integration
5. **Streaming Enhancements** — Real-time synthesis improvements

**Breaking change policy**: v3 may break audio APIs but **must not break control semantics**.

---

## 🏛️ Foundational Principle

```
v2.7 = State Authority (Registrar owns truth)
v2.9 = Control Plane Freeze (No more control changes)
v3   = Audio Power (Build on stable foundation)
```

The registrar, MCP contracts, ownership model, and accessibility semantics are **inherited unchanged**.

---

## 🎯 Core Pillars

| Pillar | Priority | Phase | Notes |
|--------|----------|-------|-------|
| Multi-Track Mixing | P0 | Alpha | Foundation for everything else |
| DSP Effects Chain | P0 | Beta | Must be graph-native, not post-hoc |
| 3D Spatial Audio | P1 | RC | Binaural first; ambisonics in v3.x |
| Voice Cloning | P1 | RC | Production-grade but permission-gated |
| Streaming | P2 | Carry-forward | Enhance, don't redesign |

---

## 🏗️ Architecture Evolution

### v2.x Model (Single Stream)

```
Text → Engine → Audio (single stream)
```

### v3 Model (Multi-Track Graph)

```
Text → Engine → AudioGraph → MixBus → DSP → SpatialRenderer → Output
                    ↓
              [Track 1]──┐
              [Track 2]──┼──→ [Mix] → [Effects] → [Spatial] → Output
              [Track N]──┘
```

### Graph Model Strategy: Extend, Don't Replace

**What stays (v2 inheritance)**:
- `ControlGraph` (tokens, timing, events)
- Compiler → lowering pipeline
- Registrar mediation
- Session/ownership semantics

**What's new (v3 additions)**:
- `AudioGraph` — explicit Track, Bus, and Node concepts
- Multi-track lifecycle management
- DSP chain abstraction

```
ControlGraph  (what should happen)
     ↓
AudioGraph    (how audio is composed)
     ↓
Engine/DSP    (rendering)
```

This keeps:
- v2 graphs valid
- v3 graphs expressive
- Migration tractable

---

## 🔒 Breaking Change Policy

### Keep Stable (Must Not Break)

| Component | Reason |
|-----------|--------|
| Registrar APIs | State authority |
| MCP tool contracts | External integrations |
| Session/ownership semantics | Agent coordination |
| Accessibility override behavior | Safety-critical |
| Streaming interrupt semantics | Real-time correctness |

### Deprecate / Replace

| Old API | Issue | v3 Replacement |
|---------|-------|----------------|
| `engine.speak()` single-stream | Assumes one voice | `engine.synthesize()` → Track |
| Single PCM output | No mixing support | `AudioGraph.render()` |
| Ad-hoc audio overlays | Not graph-native | Track composition |

### Migration Strategy

```python
# v2 code (still works via compatibility shim)
result = engine.speak("Hello!")

# v3 native API
graph = AudioGraph()
track = graph.add_track("dialogue")
track.add_segment(engine.synthesize("Hello!"))
result = graph.render()
```

v2-style APIs become compatibility shims. New code should use v3 APIs.

---

## 📅 Phase Plan

### v3.0-alpha — Multi-Track Foundation

**Goal**: Prove parallel audio is real and safe.

**Target**: Q1 2027

#### Must Ship

| Feature | Description | Status |
|---------|-------------|--------|
| `AudioGraph` | Core abstraction for multi-track composition | 🔲 Design |
| `Track` | Independent audio stream with lifecycle | 🔲 Design |
| `MixBus` | Gain, mute, routing | 🔲 Design |
| Crossfade primitives | Smooth transitions between tracks | 🔲 Design |
| Registrar track lifecycle | Multi-track state management | 🔲 Design |

#### Must NOT Ship

- DSP beyond gain/pan
- Spatialization
- Cloning

#### Gate

> **If alpha doesn't mix cleanly, stop here.**

#### API Preview

```python
from voice_soundboard.v3 import AudioGraph, Track

graph = AudioGraph()

# Create tracks
dialogue = graph.add_track("dialogue")
music = graph.add_track("music", volume=0.3)

# Add content
dialogue.add_segment(engine.synthesize("Welcome to the show!"))
music.add_segment(load_audio("intro_music.wav"))

# Crossfade
graph.crossfade(music, dialogue, duration_ms=500)

# Render
output = graph.render()
```

---

### v3.0-beta — DSP Effects Chain

**Goal**: Make audio sound better, not just mix.

**Target**: Q2 2027

#### Must Ship

| Feature | Description | Status |
|---------|-------------|--------|
| Ordered DSP chain | Per-track and per-bus effects | 🔲 Design |
| Reverb | Room simulation | 🔲 Research |
| EQ | Frequency shaping | 🔲 Design |
| Compression | Dynamic range control | 🔲 Design |
| Limiter | Peak protection | 🔲 Design |
| Real-time safe processing | No blocking, bounded latency | 🔲 Design |

#### Key Invariant

> **DSP must not introduce state outside the AudioGraph.**

Effects are pure transforms. No hidden side effects.

#### API Preview

```python
from voice_soundboard.v3.dsp import Reverb, EQ, Compressor, Limiter

# Per-track effects
dialogue.add_effect(EQ(low_cut_hz=80, presence_boost_db=2))
dialogue.add_effect(Compressor(threshold_db=-12, ratio=4))

# Per-bus effects (applied to mix)
graph.master_bus.add_effect(Reverb(room_size=0.3, wet=0.15))
graph.master_bus.add_effect(Limiter(ceiling_db=-1))
```

---

### v3.0-rc — Spatial + Cloning (Gated)

**Goal**: Add power without destabilization.

**Target**: Q3 2027

#### Spatial Audio

| Feature | Description | v3.0 | v3.x |
|---------|-------------|------|------|
| Binaural stereo | HRTF-based, headphone-first | ✅ | — |
| Speaker positioning | 3D coordinates | ✅ | — |
| Listener-centric | Head tracking support | ✅ | — |
| Ambisonics (FOA/HOA) | Full sphere encoding | ❌ | ✅ |
| Room modeling | Acoustic simulation | ❌ | ✅ |
| Speaker array rendering | Multi-speaker output | ❌ | ✅ |

```python
from voice_soundboard.v3.spatial import SpatialMixer, Position

mixer = SpatialMixer(mode="binaural")

# Position speakers in 3D space
alice = Position(x=-1.0, y=0, z=2.0)  # Front-left
bob = Position(x=1.0, y=0, z=2.0)     # Front-right

graph.set_track_position(dialogue_alice, alice)
graph.set_track_position(dialogue_bob, bob)

output = mixer.render(graph)
```

#### Voice Cloning

**Strategy**: Integrate first, abstract always.

| Aspect | Decision |
|--------|----------|
| Architecture | Integrate proven systems (RVC-like, diffusion-based) |
| Abstraction | `CloningProvider` interface |
| Permissions | Registrar-mediated at call time |
| Audit | All cloning operations logged |

**Cloning must be**:
- Opt-in (explicit consent)
- Logged (full audit trail)
- Revocable (can be disabled)

```python
from voice_soundboard.v3.cloning import CloningProvider

# Register a cloning provider
provider = CloningProvider.load("rvc-v2")

# Clone requires explicit permission
with registrar.cloning_permission(voice_id="user_123", consent_token=token):
    cloned_voice = provider.clone(
        reference_audio="sample.wav",
        target_text="Hello, this is my cloned voice."
    )
    
# Audit trail automatically recorded
```

---

### v3.0 — Production Release

**Goal**: Make it boring.

**Target**: Q4 2027

#### Focus Areas

| Area | Work |
|------|------|
| Performance | Latency optimization, memory profiling |
| Stability | 8-hour soak tests, stress tests |
| Migration | v2 → v3 migration guide |
| Compatibility | v2 shim validation |
| Documentation | Complete API reference |

**No new features in this phase.**

---

## 📋 Full Feature Matrix

| Feature | Priority | Phase | Effort | Status |
|---------|----------|-------|--------|--------|
| AudioGraph abstraction | P0 | Alpha | Large | 🔲 Design |
| Track lifecycle | P0 | Alpha | Medium | 🔲 Design |
| MixBus | P0 | Alpha | Medium | 🔲 Design |
| Crossfade primitives | P0 | Alpha | Small | 🔲 Design |
| Registrar multi-track | P0 | Alpha | Large | 🔲 Design |
| DSP chain | P0 | Beta | Large | 🔲 Design |
| Reverb | P0 | Beta | Medium | 🔲 Research |
| EQ | P0 | Beta | Small | 🔲 Design |
| Compression | P0 | Beta | Medium | 🔲 Design |
| Limiter | P0 | Beta | Small | 🔲 Design |
| Binaural spatial | P1 | RC | Large | 🔲 Research |
| HRTF rendering | P1 | RC | Large | 🔲 Research |
| Cloning integration | P1 | RC | Large | 🔲 Research |
| Cloning permissions | P1 | RC | Medium | 🔲 Design |
| v2 compatibility shims | P1 | Prod | Medium | 🔲 Design |
| Ambisonics | P2 | v3.x | Large | 🔲 Deferred |
| Room modeling | P2 | v3.x | Large | 🔲 Deferred |

---

## 🚫 Explicitly NOT in v3.0

Deferred to v3.x or later:

- ❌ Ambisonics (FOA/HOA)
- ❌ Acoustic room modeling
- ❌ Speaker array rendering
- ❌ Novel cloning architecture (integrate existing only)
- ❌ Video lip-sync
- ❌ Control plane changes (frozen since v2.9)

---

## 📜 v3 Audio Invariants (CRITICAL)

**Write this document before any v3 code.**

These invariants must hold for all v3 audio operations:

### 1. No Unintended Clipping

```
∀ output: peak(output) ≤ 0 dBFS unless explicitly saturated
```

### 2. No Overlapping PCM Unless Mixed

```
∀ track1, track2: overlapping_time(track1, track2) → mixed_output
```

Raw PCM streams never collide without explicit mixing.

### 3. DSP Chains Are Deterministic

```
∀ input, effects: apply(effects, input) = apply(effects, input)
```

Same input + same effects = same output. Always.

### 4. Spatialization Cannot Reorder Audio

```
∀ track: temporal_order(track.segments) = temporal_order(spatialized(track).segments)
```

Spatial processing affects position, not sequence.

### 5. Cloned Voices Are Auditable

```
∀ clone_operation: ∃ audit_record(clone_operation)
```

Every cloning operation has a corresponding audit entry.

### 6. Tracks Respect Registrar Ownership

```
∀ track: track.owner = registrar.get_owner(track.id)
```

Track operations require ownership verification.

### 7. Mix Operations Are Commutative (Where Expected)

```
mix(A, B) = mix(B, A) (for simple gain mixing)
```

Order-dependent operations (like sidechaining) must be explicit.

---

## ✅ Prerequisites (What Must Be Complete)

### Required Before v3 Alpha

| Prerequisite | Source | Status |
|--------------|--------|--------|
| Registrar correctness | v2.7 | ✅ Complete |
| State model completeness | v2.8 | ✅ Complete |
| Accessibility enforcement | v2.9 | ✅ Complete |
| Control plane freeze | v2.9 | ✅ Complete |

### Can Evolve During v3.x

| Component | Notes |
|-----------|-------|
| Production security | Must be sufficient to gate cloning & DSP |
| Deployment infrastructure | Must support real-time workloads |
| Backend ecosystem | 2–3 backends sufficient |

---

## 🎯 Success Metrics

### Alpha (Multi-Track)

- [ ] 4 simultaneous tracks without glitches
- [ ] Crossfade latency < 10ms
- [ ] Track creation < 1ms
- [ ] Zero registrar state corruption under concurrent track ops

### Beta (DSP)

- [ ] DSP chain latency < 5ms for 4 effects
- [ ] No clipping on normalized input
- [ ] Memory stable over 1-hour session
- [ ] Effects are bit-exact reproducible

### RC (Spatial + Cloning)

- [ ] Binaural rendering latency < 15ms
- [ ] Spatial positioning audibly correct (user study)
- [ ] Cloning permission flow tested
- [ ] Audit log captures 100% of clone operations

### Production

- [ ] 8-hour soak test passes
- [ ] v2 compatibility shims work for all v2 tests
- [ ] Migration guide reviewed by 3+ beta users
- [ ] Zero P0 bugs in 30-day beta

---

## 🔄 Migration from v2

### Compatibility Approach

```python
# v2 code continues to work
from voice_soundboard import VoiceEngine
engine = VoiceEngine()
result = engine.speak("Hello!")  # Uses compatibility shim

# v3 native code
from voice_soundboard.v3 import AudioGraph
graph = AudioGraph()
# ... full multi-track API
```

### Migration Path

1. **Phase 1**: Run existing code unchanged (shims handle translation)
2. **Phase 2**: Identify single-track bottlenecks
3. **Phase 3**: Migrate to `AudioGraph` for multi-track needs
4. **Phase 4**: Add DSP/spatial as needed

### Deprecation Timeline

| API | v3.0 | v3.1 | v3.2 |
|-----|------|------|------|
| `engine.speak()` | Shim (warning) | Shim (warning) | Removed |
| Single-stream assumptions | Shim | Shim | Removed |
| v2 `ControlGraph` direct use | Supported | Supported | Supported |

---

## 📝 How to Contribute

1. **Audio DSP**: Implementations of effects (reverb, EQ, etc.)
2. **Spatial Audio**: HRTF datasets, binaural algorithms
3. **Cloning Integration**: Wrappers for cloning backends
4. **Testing**: Multi-track stress tests, audio quality benchmarks
5. **Migration Guides**: Real-world v2 → v3 migration stories

---

## Appendix A: AudioGraph Node Types

```
AudioGraph
├── Track (audio source)
│   ├── Segment (PCM data)
│   ├── Effect[] (per-track DSP)
│   └── Position (spatial)
├── Bus (mixing point)
│   ├── Input[] (tracks or buses)
│   ├── Effect[] (per-bus DSP)
│   └── Gain/Pan
└── Output (final render)
    ├── Format (sample rate, channels)
    └── Limiter (safety)
```

---

## Appendix B: DSP Effect Interface

```python
class Effect(Protocol):
    """Base interface for all DSP effects."""
    
    def process(self, samples: np.ndarray) -> np.ndarray:
        """Process audio samples. Must be deterministic."""
        ...
    
    def reset(self) -> None:
        """Reset internal state (if any)."""
        ...
    
    @property
    def latency_samples(self) -> int:
        """Report processing latency for compensation."""
        ...
```

---

## Appendix C: Cloning Provider Interface

```python
class CloningProvider(Protocol):
    """Interface for voice cloning backends."""
    
    def clone(
        self,
        reference_audio: bytes,
        target_text: str,
        *,
        consent_token: str,
    ) -> ClonedVoice:
        """Clone a voice from reference audio."""
        ...
    
    def verify_consent(self, consent_token: str) -> bool:
        """Verify consent token is valid."""
        ...
    
    @property
    def supported_languages(self) -> list[str]:
        """Languages this provider supports."""
        ...
```

---

*Last updated: 2026-02-07*
*Predecessor: ROADMAP_v2.9.md (Control Plane Freeze)*
