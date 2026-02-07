# Voice Soundboard v2.1 Roadmap

**Target**: Q2 2026  
**Theme**: "Streaming & Developer Experience"

---

## Executive Summary

v2.1 focuses on two pillars:
1. **Incremental text streaming** — The most requested feature
2. **Developer experience** — Tooling, debugging, observability

No breaking changes. Fully backwards compatible with v2.0.0.

---

## 🎯 Primary Goals

### 1. Incremental Text Streaming (P0)

**Status**: Design phase  
**Effort**: Large  
**Risk**: Medium

The current streaming model waits for sentence boundaries. v2.1 adds true word-by-word streaming with speculative execution.

#### Architecture

```
LLM output: "The quick brown fox..."
                ↓
         IncrementalCompiler
                ↓
    SpeculativeGraph (partial)
                ↓
         Engine.synthesize()
                ↓
    Audio chunk (immediate)
                ↓
    [If correction needed: rollback + re-synthesize]
```

#### Key Components

| Component | Description | Status |
|-----------|-------------|--------|
| `IncrementalCompiler.feed_word()` | Word-level graph emission | 🔲 Design |
| `SpeculativeGraph` | Partial graph with rollback markers | 🔲 Design |
| `StreamBuffer` | Audio buffer with rollback support | 🔲 Design |
| `CorrectionDetector` | Detects when LLM corrects itself | 🔲 Design |

#### API (Proposed)

```python
from voice_soundboard.streaming import IncrementalSynthesizer

synth = IncrementalSynthesizer(backend)

# Feed words as they arrive from LLM
for word in llm_stream():
    for audio_chunk in synth.feed(word):
        play(audio_chunk)

# Finalize
for audio_chunk in synth.finalize():
    play(audio_chunk)
```

#### Success Criteria

- [ ] First audio chunk within 100ms of first word
- [ ] Rollback latency < 50ms
- [ ] No audio glitches on correction
- [ ] Deterministic (same input → same output)

#### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Rollback causes audio pop | High | Crossfade buffer |
| Speculative execution too aggressive | Medium | Conservative commit boundaries |
| Memory growth from buffering | Low | Ring buffer with max size |

---

### 2. Developer Experience (P1)

#### 2.1 Debug Mode

```python
engine = VoiceEngine(Config(debug=True))
result = engine.speak("Hello!")

print(result.debug_info)
# {
#   "compile_time_ms": 2.3,
#   "synth_time_ms": 145.2,
#   "graph_tokens": 3,
#   "graph_events": 0,
#   "backend": "kokoro",
#   "cache_hit": False,
# }
```

#### 2.2 Graph Visualization

```python
from voice_soundboard.debug import visualize_graph

graph = compile_request("Hello, [laugh] world!")
visualize_graph(graph)  # Opens browser with timeline view
```

#### 2.3 Timing Profiler

```python
from voice_soundboard.debug import profile_synthesis

with profile_synthesis() as prof:
    engine.speak("Long text here...")

prof.report()
# Tokenization:  2.1ms
# Compilation:   3.4ms
# Lowering:      0.8ms
# Synthesis:   142.3ms
# I/O:          12.1ms
# Total:       160.7ms
```

#### 2.4 Graph Diff Tool

```python
from voice_soundboard.debug import diff_graphs

g1 = compile_request("Hello", emotion="happy")
g2 = compile_request("Hello", emotion="sad")

diff_graphs(g1, g2)
# Differences:
#   tokens[0].pitch_scale: 1.1 → 0.9
#   tokens[0].energy_scale: 1.2 → 0.8
```

---

## 🔧 Secondary Goals

### 3. Additional Backends (P2)

#### 3.1 Coqui TTS Backend

**Status**: Research  
**Effort**: Medium

```python
engine = VoiceEngine(Config(backend="coqui"))
```

- Open source, good quality
- VITS and YourTTS models
- Voice cloning capable

#### 3.2 OpenAI TTS Backend

**Status**: Research  
**Effort**: Small

```python
engine = VoiceEngine(Config(backend="openai"))
result = engine.speak("Hello!", voice="alloy")
```

- Cloud-based, requires API key
- High quality
- Simple integration

---

### 4. Voice Cloning Infrastructure (P2)

**Goal**: Lay groundwork for v3 voice cloning without implementing full feature.

#### 4.1 Embedding Extraction

```python
from voice_soundboard.cloning import extract_embedding

# Extract speaker embedding from reference audio
embedding = extract_embedding("reference.wav")

# Use in synthesis
graph = compile_request("Hello!", speaker=SpeakerRef.from_embedding(embedding))
```

**Scope for v2.1**:
- ✅ Embedding extraction API
- ✅ Embedding storage format
- ✅ Integration with `SpeakerRef.from_embedding()`
- ❌ Quality guarantees (experimental)
- ❌ Production-ready cloning

#### 4.2 Speaker Database

```python
from voice_soundboard.speakers import SpeakerDB

db = SpeakerDB("./speakers")
db.add("customer_alice", "alice_reference.wav")

# Later
engine.speak("Hello Alice!", speaker=db.get("customer_alice"))
```

---

### 5. Performance Improvements (P2)

#### 5.1 Graph Caching

```python
# Automatic caching of compiled graphs
engine = VoiceEngine(Config(cache_graphs=True))

# First call: compiles and caches
engine.speak("Welcome to the show!")

# Second call: cache hit, skips compilation
engine.speak("Welcome to the show!")
```

#### 5.2 Batch Synthesis

```python
from voice_soundboard import batch_synthesize

texts = ["Hello", "World", "How are you?"]
results = batch_synthesize(texts, voice="af_bella")

# Parallel compilation, batched synthesis
```

#### 5.3 Memory Optimization

- Lazy model loading (already done in v2.0)
- Model unloading after timeout
- Streaming memory limits

---

### 6. Audio Event Assets (P3)

#### 6.1 Official Asset Pack

Curated, high-quality WAV files for:
- `laugh` (soft, medium, hard)
- `sigh` (short, long)
- `breath` (inhale, exhale)
- `gasp`
- `hmm` (thinking)
- `uh` (hesitation)

**Format**: All assets at 24kHz and 22kHz for backend compatibility.

#### 6.2 Asset Validation CLI

```bash
voice-soundboard validate-assets ./my-assets/
# ✅ laugh/soft.wav: mono, 16-bit, 24000Hz, 0.23s
# ✅ laugh/medium.wav: mono, 16-bit, 24000Hz, 0.31s
# ❌ sigh/long.wav: stereo (must be mono)
```

---

### 7. Documentation & Examples (P3)

#### 7.1 Cookbook

- "Integrate with LangChain"
- "Build a voice assistant"
- "Add custom emotions"
- "Create custom backends"

#### 7.2 Interactive Playground

Web-based playground for testing:
- Text input
- Voice selection
- Emotion sliders
- Real-time audio preview

#### 7.3 Architecture Deep Dive

- Compiler internals explained
- How to write a backend
- Graph schema reference
- Timing model explained

---

## 📅 Timeline

```
2026-02-07  v2.0.0 released
     │
     ▼
2026-02-21  v2.1 design review
     │      - Incremental streaming RFC
     │      - Debug tooling spec
     │
     ▼
2026-03-15  v2.1-alpha.1
     │      - Incremental streaming (experimental)
     │      - Debug mode
     │
     ▼
2026-04-01  v2.1-alpha.2
     │      - Graph visualization
     │      - Coqui backend (experimental)
     │
     ▼
2026-04-15  v2.1-beta.1
     │      - Feature freeze
     │      - Performance tuning
     │      - Documentation
     │
     ▼
2026-05-01  v2.1-rc.1
     │      - Bug fixes only
     │      - Final testing
     │
     ▼
2026-05-15  v2.1.0 release
```

---

## 📋 Full Feature Matrix

| Feature | Priority | Effort | Status |
|---------|----------|--------|--------|
| Incremental text streaming | P0 | Large | 🔲 Design |
| Debug mode | P1 | Small | 🔲 Not started |
| Graph visualization | P1 | Medium | 🔲 Not started |
| Timing profiler | P1 | Small | 🔲 Not started |
| Graph diff tool | P1 | Small | 🔲 Not started |
| Coqui TTS backend | P2 | Medium | 🔲 Research |
| OpenAI TTS backend | P2 | Small | 🔲 Research |
| Embedding extraction | P2 | Medium | 🔲 Not started |
| Speaker database | P2 | Small | 🔲 Not started |
| Graph caching | P2 | Small | 🔲 Not started |
| Batch synthesis | P2 | Medium | 🔲 Not started |
| Official asset pack | P3 | Medium | 🔲 Not started |
| Asset validation CLI | P3 | Small | 🔲 Not started |
| Cookbook docs | P3 | Medium | 🔲 Not started |
| Interactive playground | P3 | Large | 🔲 Not started |

---

## 🚫 Explicitly NOT in v2.1

These remain deferred to v3:

- ❌ True PCM mixing / sidechain compression
- ❌ Native paralinguistics in all backends
- ❌ Production-ready voice cloning
- ❌ DSP effects (reverb, EQ, etc.)
- ❌ Breaking API changes

---

## 🎯 Success Metrics

### Streaming
- First audio latency: < 100ms from first word
- Rollback latency: < 50ms
- Zero audio glitches in normal operation

### Performance
- Graph cache hit rate: > 80% in typical apps
- Memory usage: < 500MB for single backend

### Developer Experience
- Time to first working code: < 5 minutes
- Debug cycle time: < 10 seconds

### Quality
- Test coverage: > 90%
- Property tests: All timing invariants hold
- No regressions in v2.0 functionality

---

## 📝 How to Contribute

1. **Feature Requests**: Open an issue with `[v2.1]` prefix
2. **RFCs**: For large features, submit a design doc
3. **Code**: PRs welcome after design approval
4. **Docs**: Cookbook contributions especially welcome

---

## Appendix: Incremental Streaming RFC

### Problem Statement

Current streaming waits for sentence boundaries:
```
"Hello, how are you?"
       ^sentence boundary → graph emitted
```

This adds 200-500ms latency for short sentences.

### Proposed Solution

Speculative word-level emission with rollback:
```
"Hello" → emit graph, synthesize, play
", "    → continue
"how"   → emit graph, synthesize, play
...
```

If the LLM corrects itself:
```
"Hello, how ar—" [correction] "Hello, I'm fine!"
                              ^rollback to "Hello, "
```

### Key Decisions

1. **Commit boundaries**: Where do we commit (can't rollback)?
   - Proposal: Commit at punctuation (`. , ; : ? !`)
   
2. **Buffer size**: How much audio to buffer before playing?
   - Proposal: 50-100ms (1-2 words)
   
3. **Rollback strategy**: How to handle mid-word corrections?
   - Proposal: Crossfade to silence, re-synthesize from last commit

### Open Questions

- How to handle languages without clear word boundaries?
- What's the maximum speculative depth before forced commit?
- How to expose rollback events to applications?

---

*Last updated: 2026-02-07*
