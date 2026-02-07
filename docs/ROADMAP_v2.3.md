# Voice Soundboard v2.3 Roadmap

**Positioning**: Bridge release between v2.1 (Streaming & DX) and v3 (Major Audio + Cloning Capabilities)  
**Compatibility**: Fully backwards compatible with v2.x  
**Breaking Changes**: ❌ None  
**Focus**: Real-time readiness, production hardening, extensibility

---

## 🧾 Executive Summary

v2.3 is a **foundational release**.

It does not ship v3 features (true PCM mixing, production cloning, full DSP), but it removes the remaining architectural blockers that prevent those features from being added cleanly in v3.

Where v2.1 focused on latency and developer experience, v2.3 focuses on:

- **Real-time execution guarantees**
- **Production reliability**
- **Extensibility via plugins**
- **Audio pipeline correctness**
- **Multi-speaker and conversational structure**

Think of v2.3 as **"engine hardening + future-proofing."**

---

## 🎯 Primary Goals

### 🚀 P0 — Real-Time Audio Pipeline

**Goal**: Make Voice Soundboard safe for interactive, low-latency, user-facing systems (assistants, games, agents).

#### Capabilities

- Low-latency audio path (<20ms internal buffering)
- Explicit real-time vs batch synthesis modes
- Deterministic scheduling under load
- Bounded memory guarantees

#### Key Additions

```python
engine = VoiceEngine(
    Config(
        realtime=True,
        max_latency_ms=50,
        drop_policy="graceful"
    )
)
```

#### Scope (v2.3)

- ✅ Real-time execution mode
- ✅ Strict buffering contracts
- ✅ Backpressure handling
- ❌ True PCM mixing (v3)
- ❌ Sidechain compression (v3)

---

### 🛡️ P1 — Production Reliability & Observability

**Goal**: Make the system diagnosable, debuggable, and safe in production environments.

#### Features

##### Health & Readiness

```python
engine.health()
# {
#   "backend": "piper",
#   "model_loaded": True,
#   "memory_mb": 312,
#   "queue_depth": 3,
#   "status": "healthy"
# }
```

##### Structured Logging

- Graph lifecycle logs
- Backend execution logs
- Streaming rollback logs

##### Error Recovery

- Backend fallback strategies
- Graceful degradation (events → silence → text)
- Explicit failure modes (no silent corruption)

---

### 🧩 P1 — Plugin / Extension Architecture

**Goal**: Allow advanced users to extend the system without forking core.

#### Plugin Targets

| Layer | Examples |
|-------|----------|
| Compiler | Custom transforms, new markup |
| Runtime | Scheduling, buffering, prioritization |
| Audio | Ducking policies, normalization |
| Backends | Experimental TTS engines |

#### Example

```python
@voice_soundboard.plugin
class WhisperTimingPlugin:
    def on_graph(self, graph):
        ...
```

#### Scope (v2.3)

- ✅ Stable plugin hooks
- ✅ Plugin discovery & registration
- ❌ Plugin sandboxing (v3)

---

## 🔧 Secondary Goals

### 🔄 P2 — Advanced Streaming Control

**Goal**: Move beyond "fire-and-forget" streaming.

#### Features

- Interruptible synthesis
- Priority queues (system > assistant > background)
- Bidirectional streaming (input ↔ output coordination)
- Mid-stream cancellation

```python
synth.interrupt(reason="user_spoke")
```

This prepares the ground for conversational agents and assistants.

---

### 🔊 P2 — Audio Quality & Format Infrastructure

**Goal**: Improve audio correctness without introducing DSP effects yet.

#### Features

- Sample-rate conversion utilities
- Loudness normalization (LUFS targets)
- Output format negotiation (wav, pcm, mp3, opus)
- Explicit audio metadata propagation

```python
engine.speak(
    text,
    audio_format="opus",
    target_lufs=-16
)
```

❗ No reverb, EQ, or spatialization yet (v3).

---

### 🗣️ P2 — Multi-Speaker Conversations

**Goal**: First-class support for conversations, not just utterances.

#### Capabilities

- Multiple speakers per graph
- Turn-taking rules
- Speaker timelines
- Future diarization hooks

```python
conversation = Conversation([
    ("alice", "Hello!"),
    ("bob", "Hi there."),
])
engine.play(conversation)
```

This prepares v3 features like dialogue mixing and scene-based audio.

---

### 📊 P2 — Voice Quality Metrics

**Goal**: Make voice quality measurable and comparable.

#### Features

- Pronunciation scoring
- Timing deviation metrics
- A/B voice comparison utilities
- Regression detection across versions

```python
score = evaluate_pronunciation(audio, reference_text)
```

---

### 🔐 P3 — Security, Compliance & Safety

**Goal**: Enable enterprise and regulated use cases.

#### Features

- Optional audio watermarking
- Content filtering hooks
- Audit logging
- Metadata tagging for compliance

No policy enforcement in core — hooks only.

---

### 🚢 P3 — Deployment Helpers

**Goal**: Reduce friction in real deployments.

- Official Docker images
- Helm charts (K8s)
- Serverless examples
- Reference architectures

---

## 📋 Full Feature Matrix

| Feature | Priority | Effort | Status |
|---------|----------|--------|--------|
| Real-time audio pipeline | P0 | Large | 🔲 Design |
| Health & readiness endpoints | P1 | Small | 🔲 Not started |
| Structured logging | P1 | Small | 🔲 Not started |
| Error recovery & fallbacks | P1 | Medium | 🔲 Not started |
| Plugin architecture | P1 | Medium | 🔲 Design |
| Plugin discovery & registration | P1 | Small | 🔲 Not started |
| Advanced streaming control | P2 | Medium | 🔲 Not started |
| Interruptible synthesis | P2 | Medium | 🔲 Not started |
| Audio format infrastructure | P2 | Medium | 🔲 Not started |
| Loudness normalization | P2 | Small | 🔲 Not started |
| Multi-speaker conversations | P2 | Large | 🔲 Design |
| Voice quality metrics | P2 | Medium | 🔲 Not started |
| Security & compliance hooks | P3 | Small | 🔲 Not started |
| Deployment helpers (Docker/K8s) | P3 | Medium | 🔲 Not started |

---

## 🧱 Relationship to v3

### What v2.3 Enables (But Does Not Ship)

| v3 Feature | v2.3 Preparation |
|------------|------------------|
| True PCM mixing | Real-time pipeline + audio metadata |
| Sidechain compression | Ducking + gain envelopes |
| Native paralinguistics | Plugin + multi-speaker timelines |
| Production cloning | Speaker DB + metrics |
| DSP effects | Audio format & normalization layer |

**v2.3 ensures that v3 can focus on capability, not cleanup.**

---

## 🚫 Explicitly NOT in v2.3

Still deferred to v3:

- ❌ True PCM mixing / sidechain compression
- ❌ Full DSP effects (EQ, reverb, spatial audio)
- ❌ Production-grade voice cloning
- ❌ Breaking API changes

---

## 🎯 Success Criteria

- Real-time mode stable under load
- No regressions from v2.1 streaming
- Plugins usable without forking
- Multi-speaker graphs supported end-to-end
- Clear, measurable audio quality metrics

---

## 📅 Timeline

```
2026-05-15  v2.1.0 released
     │
     ▼
2026-06-01  v2.3 design review
     │      - Real-time pipeline RFC
     │      - Plugin architecture spec
     │
     ▼
2026-07-01  v2.3-alpha.1
     │      - Real-time mode (experimental)
     │      - Plugin hooks
     │
     ▼
2026-08-01  v2.3-alpha.2
     │      - Multi-speaker support
     │      - Advanced streaming control
     │
     ▼
2026-09-01  v2.3-beta.1
     │      - Feature freeze
     │      - Production reliability features
     │      - Documentation
     │
     ▼
2026-10-01  v2.3-rc.1
     │      - Bug fixes only
     │      - Final testing
     │
     ▼
2026-10-15  v2.3.0 release
```

---

## 📝 How to Contribute

1. **Feature Requests**: Open an issue with `[v2.3]` prefix
2. **RFCs**: For large features, submit a design doc
3. **Code**: PRs welcome after design approval
4. **Docs**: Plugin tutorials and deployment guides especially welcome

---

*Last updated: 2026-02-07*
