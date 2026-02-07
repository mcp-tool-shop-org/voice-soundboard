# Voice Soundboard v3.1 Roadmap

**Target**: Q1 2028  
**Theme**: "Operational Audio Power"  
**Position**: First post-v3 production hardening release  
**Breaking Changes**: ❌ None

---

## Executive Summary

> **v3.1 turns v3's audio primitives into a stable, extensible, and operationally safe platform for real applications.**

If v3.0 proves "Audio Power is possible",  
v3.1 proves "Audio Power is usable at scale."

---

## 🚫 What v3.1 Is NOT

v3.1 explicitly does **not**:

| Locked by v3.0 | Status |
|----------------|--------|
| Redesign AudioGraph | ❌ Frozen |
| Change ControlGraph or Registrar semantics | ❌ Frozen |
| Introduce new DSP categories | ❌ Frozen |
| Add ambisonics | ❌ Deferred to v3.2 |
| Add new cloning model classes | ❌ Deferred |

**Rule**: v3.1 adds capability depth, not architectural breadth.

---

## 🧱 Core Goals

### 1️⃣ AudioGraph Hardening & Ergonomics (P0)

**Goal**: Make AudioGraph pleasant and safe to use.

v3.0 defined AudioGraph correctly. v3.1 makes it usable by humans, tools, and agents.

#### Features

| Feature | Description | Status |
|---------|-------------|--------|
| `graph.validate()` | Static graph checks (invariant preflight) | 🔲 Design |
| `graph.diff()` | Explicit graph diffing | 🔲 Design |
| `graph.visualize()` | Graph introspection tools | 🔲 Design |
| Validation API | Early failure with actionable errors | 🔲 Design |

#### API

```python
from voice_soundboard.v3 import AudioGraph

graph = AudioGraph()
# ... build graph ...

# Validate before render
errors = graph.validate(strict=True)
if errors:
    for err in errors:
        print(f"{err.location}: {err.message}")

# Compare graphs
diff = graph.diff(previous_graph)
for change in diff.changes:
    print(f"{change.type}: {change.path}")

# Visual inspection
graph.visualize(output="graph.svg")
```

#### Why This Matters

Complex graphs will be authored by:
- Humans (manual composition)
- Tools (automated pipelines)
- Agents (AI-driven mixing)

They must **fail early and explainably**.

---

### 2️⃣ Effect Chain Presets & Profiles (P0)

**Goal**: Make DSP composable and reusable.

v3.0 DSP primitives exist; v3.1 packages them for practical use.

#### Features

| Feature | Description | Status |
|---------|-------------|--------|
| Named DSP chains | Reusable effect configurations | 🔲 Design |
| Parameter snapshots | Save/restore effect state | 🔲 Design |
| Per-voice profiles | Voice-specific defaults | 🔲 Design |
| Per-scene profiles | Scene-level mixing presets | 🔲 Design |

#### API

```python
from voice_soundboard.v3.presets import PresetLibrary, Preset

# Define a preset
broadcast_clean = Preset(
    name="broadcast_clean",
    effects=[
        EQ(low_cut_hz=80, high_shelf_db=-2),
        Compressor(threshold_db=-18, ratio=3, makeup_db=2),
        Limiter(ceiling_db=-1),
    ],
    metadata={"use_case": "podcast", "author": "audio_team"},
)

# Register presets
library = PresetLibrary()
library.register(broadcast_clean)
library.register_from_file("presets/voice_profiles.yaml")

# Apply to track
engine.apply_preset(
    track="dialogue",
    preset="broadcast_clean",
)

# Per-voice profiles
engine.set_voice_profile("af_bella", preset="warm_female")
engine.set_voice_profile("am_adam", preset="broadcast_male")

# Scene-level defaults
scene.set_default_preset(AudioLayer.DIALOGUE, "broadcast_clean")
scene.set_default_preset(AudioLayer.MUSIC, "background_duck")
```

#### Benefits

- ✅ No duplicated DSP logic
- ✅ Consistent tuning across projects
- ✅ No copy-paste pipelines
- ✅ Version-controlled audio settings

---

### 3️⃣ AudioGraph Plugin Interface (P1)

**Goal**: Enable extensibility without compromising safety.

This is the right place for extensibility — not inside DSP core.

#### Plugin Capabilities

| Capability | Description | Status |
|------------|-------------|--------|
| Custom DSP nodes | User-defined effects | 🔲 Design |
| Custom analysis nodes | Loudness, emotion feedback, etc. | 🔲 Design |
| Graph transforms | Automated graph modifications | 🔲 Design |

#### Strict Rules

Plugins **must not**:
- Introduce external state
- Bypass registrar
- Block real-time processing
- Access filesystem/network directly

```python
from voice_soundboard.v3.plugins import AudioPlugin, PluginContext

class LoudnessAnalyzer(AudioPlugin):
    """Custom analysis node that measures LUFS."""
    
    name = "loudness_analyzer"
    category = "analysis"
    
    def process(self, samples: np.ndarray, ctx: PluginContext) -> np.ndarray:
        # Measure loudness
        lufs = self._calculate_lufs(samples)
        ctx.metrics.record("lufs", lufs)
        
        # Pass through unchanged (analysis only)
        return samples
    
    @property
    def has_external_state(self) -> bool:
        return False  # Required declaration

# Register plugin
graph.register_plugin(LoudnessAnalyzer())

# Use in graph
track.add_effect(LoudnessAnalyzer())
```

#### Alignment

This builds directly on existing plugin sandbox work from v2.4.

---

### 4️⃣ Operational Guarantees & Soak Testing (P1)

**Goal**: Prove audio power holds under stress.

This is where many audio systems fail. Doing it in v3.1 avoids v3.2 firefighting.

#### Required Work

| Test Category | Description | Target |
|---------------|-------------|--------|
| Long-running sessions | Hours of continuous audio | 8+ hours |
| Combined load | Streaming + mixing + effects | No degradation |
| Memory tracking | Growth monitoring | Bounded |
| Leak detection | Resource leak identification | Zero leaks |
| Registrar soak | Decision correctness under load | 100% correct |

#### Test Suite

```python
class TestOperationalSoak:
    """v3.1 operational guarantee tests."""
    
    @pytest.mark.soak
    def test_8_hour_audio_session(self):
        """System runs 8 hours with stable memory and latency."""
        graph = AudioGraph()
        metrics = SoakMetrics()
        
        start = time.time()
        while time.time() - start < 8 * 60 * 60:
            # Continuous audio operations
            self._run_audio_cycle(graph, metrics)
        
        assert metrics.memory_growth_percent < 10
        assert metrics.latency_p99_degradation_percent < 20
        assert metrics.error_count == 0
    
    @pytest.mark.soak
    def test_combined_streaming_mixing_effects(self):
        """Streaming + mixing + effects simultaneously."""
        graph = AudioGraph()
        
        # 4 tracks with full effect chains
        for i in range(4):
            track = graph.add_track(f"track_{i}")
            track.add_effect(EQ())
            track.add_effect(Compressor())
            track.add_effect(Reverb())
        
        # Stream for 1 hour while modifying
        for _ in range(3600):
            graph.render_chunk(duration_ms=1000)
            self._modify_graph_randomly(graph)
        
        assert graph.is_consistent()
```

---

### 5️⃣ Multi-Speaker Conversation Polishing (P1)

**Goal**: Make multi-track natural for conversation use cases.

v3.0 unlocked multi-track. v3.1 provides user-level leverage.

#### Features

| Feature | Description | Status |
|---------|-------------|--------|
| Turn-taking helpers | Automatic speaker sequencing | 🔲 Design |
| Automatic crossfades | Smooth transitions | 🔲 Design |
| Per-speaker defaults | Voice-specific settings | 🔲 Design |
| Scene-level mixing | Conversation-wide config | 🔲 Design |

#### API

```python
from voice_soundboard.v3.conversation import Conversation, Speaker

# Define speakers with defaults
alice = Speaker(
    name="Alice",
    voice="af_bella",
    position=Position(x=-0.5, y=0, z=1),
    defaults={"eq_preset": "female_voice"},
)

bob = Speaker(
    name="Bob", 
    voice="am_adam",
    position=Position(x=0.5, y=0, z=1),
    defaults={"eq_preset": "male_voice"},
)

# Create conversation with automatic features
conversation = Conversation(
    speakers=[alice, bob],
    defaults={
        "ducking": True,           # Auto-duck non-speaking
        "crossfade_ms": 100,       # Smooth transitions
        "turn_gap_ms": 200,        # Natural pause between turns
    },
)

# Add dialogue
conversation.add_turn("Alice", "Welcome to the podcast!")
conversation.add_turn("Bob", "Thanks for having me.")
conversation.add_turn("Alice", "Let's dive right in.")

# Render with all helpers active
audio = conversation.render(engine)
```

#### Turn-Taking Intelligence

```python
# Automatic overlap handling
conversation.add_turn("Alice", "So what do you think—")
conversation.add_turn("Bob", "Actually, I was just thinking...", 
                     overlap_ms=200)  # Bob interrupts slightly

# The system:
# - Crossfades appropriately
# - Ducks Alice during overlap
# - Maintains spatial positioning
```

---

### 6️⃣ Observability for Audio Quality (P2)

**Goal**: Make audio invariants visible and measurable.

v3.0 tracks invariants. v3.1 exposes them for production use.

#### Metrics

| Metric | Description | Use Case |
|--------|-------------|----------|
| Loudness (LUFS) | Integrated loudness | Broadcast compliance |
| Clipping events | Peak overages | Quality monitoring |
| Effect chain timing | Per-effect latency | Performance tuning |
| Spatial placement | Position accuracy | Debug spatial issues |
| Memory usage | Per-graph memory | Resource planning |

#### API

```python
from voice_soundboard.v3.observability import AudioMetrics, MetricsExporter

# Enable metrics collection
metrics = AudioMetrics(
    sample_rate=0.1,  # Sample 10% of renders
    metrics=[
        "loudness_lufs",
        "peak_dbfs",
        "clipping_events",
        "effect_latency_ms",
        "spatial_error_degrees",
    ],
)

graph.enable_metrics(metrics)

# Render with metrics
output = graph.render()

# Query metrics
report = metrics.report()
print(f"Loudness: {report.loudness_lufs} LUFS")
print(f"Peak: {report.peak_dbfs} dBFS")
print(f"Clipping events: {report.clipping_events}")

# Export to monitoring system
exporter = MetricsExporter(backend="prometheus")
exporter.export(report)

# Alerting
metrics.set_alert(
    metric="clipping_events",
    threshold=0,
    action="slack://audio-alerts",
)
```

#### Dashboards

v3.1 ships with:
- Grafana dashboard templates
- Prometheus metric definitions
- Alert rule examples

---

### 7️⃣ Migration Cleanup & Deprecation Progress (P2)

**Goal**: Make v2 → v3 migration boring and predictable.

#### By v3.1 Release

| Item | Status |
|------|--------|
| v2 compatibility shims stable | Required |
| Deprecation warnings actionable | Required |
| Migration docs complete | Required |
| No silent behavior differences | Required |
| Performance parity documented | Required |

#### Deprecation Timeline Update

| API | v3.0 | v3.1 | v3.2 |
|-----|------|------|------|
| `engine.speak()` | Shim (warning) | Shim (loud warning) | Removed |
| Single-stream assumptions | Shim | Shim (loud warning) | Removed |
| v2 `ControlGraph` direct use | Supported | Supported | Supported |

#### Migration Tooling

```python
from voice_soundboard.migration import MigrationChecker

# Analyze codebase for v2 patterns
checker = MigrationChecker()
report = checker.scan("./my_project")

for issue in report.issues:
    print(f"{issue.file}:{issue.line}: {issue.message}")
    print(f"  Suggestion: {issue.suggestion}")
    print(f"  Docs: {issue.docs_link}")
```

---

## 📋 Full Feature Matrix

| Feature | Priority | Effort | Status |
|---------|----------|--------|--------|
| `graph.validate()` | P0 | Medium | 🔲 Design |
| `graph.diff()` | P0 | Small | 🔲 Design |
| `graph.visualize()` | P0 | Medium | 🔲 Design |
| Named DSP presets | P0 | Medium | 🔲 Design |
| Per-voice profiles | P0 | Small | 🔲 Design |
| Per-scene profiles | P0 | Small | 🔲 Design |
| Plugin interface | P1 | Large | 🔲 Design |
| Custom DSP nodes | P1 | Large | 🔲 Design |
| Custom analysis nodes | P1 | Medium | 🔲 Design |
| 8-hour soak test | P1 | Medium | 🔲 Design |
| Combined load soak | P1 | Medium | 🔲 Design |
| Memory leak detection | P1 | Medium | 🔲 Design |
| Turn-taking helpers | P1 | Medium | 🔲 Design |
| Automatic crossfades | P1 | Small | 🔲 Design |
| Per-speaker defaults | P1 | Small | 🔲 Design |
| Loudness metrics | P2 | Small | 🔲 Design |
| Clipping counters | P2 | Small | 🔲 Design |
| Effect timing metrics | P2 | Small | 🔲 Design |
| Migration checker | P2 | Medium | 🔲 Design |
| Deprecation cleanup | P2 | Medium | 🔲 Design |

---

## 🧪 Test Expectations

v3.1 **expands**, not replaces, v3 tests.

### New Test Categories

| Category | Description |
|----------|-------------|
| Graph validation tests | Ensure `validate()` catches all invalid states |
| Preset consistency tests | Presets produce identical output |
| Plugin sandbox tests | Plugins cannot escape constraints |
| Long-run soak tests | 8+ hour stability |
| Audio invariant regression | All v3 invariants still hold |

### Test Gate

```yaml
v3.1-tests:
  runs-on: ubuntu-latest
  steps:
    - run: pytest tests/v3/ -v --strict
    - run: pytest tests/v31_hardening/ -v --strict
    - run: pytest tests/invariants/ -v --strict
```

### Critical Rule

> **If an invariant ever fails silently, v3.1 is not done.**

---

## 📦 v3.1 Deliverables Checklist

v3.1 ships **only if**:

- [ ] AudioGraph APIs are ergonomic and validated
- [ ] DSP chains are reusable and inspectable
- [ ] Plugins are possible without compromising safety
- [ ] Long-running audio is stable (8+ hours)
- [ ] Migration path is boring and predictable
- [ ] All v3 invariants pass under soak conditions
- [ ] Documentation is complete

---

## 🎯 Success Metrics

### Hardening

- [ ] `graph.validate()` catches 100% of invalid configurations
- [ ] Zero silent failures in graph construction
- [ ] Graph diff correctly identifies all changes

### Presets

- [ ] 10+ built-in presets for common use cases
- [ ] Preset application < 1ms
- [ ] Preset serialization round-trips perfectly

### Plugins

- [ ] Plugin sandbox prevents all escapes
- [ ] Custom DSP latency overhead < 1ms
- [ ] Plugin errors are isolated and recoverable

### Operational

- [ ] 8-hour soak: zero memory leaks
- [ ] 8-hour soak: latency p99 stable within 20%
- [ ] Combined load: streaming + 4 tracks + effects stable

### Migration

- [ ] 100% v2 test suite passes on shims
- [ ] Migration checker finds all deprecated usage
- [ ] Zero behavior differences vs v2 for compatible code

---

## 🔮 Relationship to Future Releases

v3.1 deliberately sets the stage for:

| Future Release | Enabled By v3.1 |
|----------------|-----------------|
| v3.2 | Ambisonics, room modeling |
| v3.3 | Adaptive DSP, ML-assisted mixing |
| v3.4 | Cross-device spatial audio |
| v4.0 | New control-plane features (if ever needed) |

---

## 📅 Timeline

```
2027-Q4  v3.0.0 released
    │
    ▼
2028-01  v3.1 design review
    │    - API ergonomics RFC
    │    - Plugin interface spec
    │    - Soak test plan
    │
    ▼
2028-02  v3.1-alpha.1
    │    - graph.validate()
    │    - Preset system
    │    - Initial soak tests
    │
    ▼
2028-03  v3.1-beta.1
    │    - Plugin interface
    │    - Conversation helpers
    │    - Full soak suite
    │
    ▼
2028-04  v3.1-rc.1
    │    - Observability
    │    - Migration tooling
    │    - Documentation
    │
    ▼
2028-05  v3.1.0 release
```

---

*Last updated: 2026-02-07*  
*Predecessor: ROADMAP_v3.md (Audio Power)*  
*Invariants: V3_AUDIO_INVARIANTS.md (still in effect)*
