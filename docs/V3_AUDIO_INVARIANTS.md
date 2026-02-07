# v3 Audio Invariants

**Status**: DRAFT — Must be finalized before any v3 code  
**Version**: 3.0  
**Last Updated**: 2026-02-07

---

## Purpose

This document defines the invariants that **must hold** for all v3 audio operations. Violations of these invariants are bugs, not features.

> **Write tests for every invariant before writing implementation code.**

---

## 1. Output Safety Invariants

### 1.1 No Unintended Clipping

```
∀ output: peak(output) ≤ 0 dBFS unless explicitly saturated
```

**Meaning**: Audio output never clips unless the user explicitly requests saturation/distortion.

**Implementation**:
- Master limiter is always active (can be bypassed explicitly)
- Gain staging prevents internal clipping
- Warnings emitted if pre-limiter peaks exceed threshold

**Test**:
```python
def test_no_unintended_clipping():
    graph = AudioGraph()
    # Add maximum volume content
    for i in range(10):
        track = graph.add_track(f"track_{i}", volume=1.0)
        track.add_segment(full_scale_sine())
    
    output = graph.render()
    assert max(abs(output)) <= 1.0
```

### 1.2 No Overlapping PCM Unless Mixed

```
∀ track1, track2: overlapping_time(track1, track2) → mixed_output
```

**Meaning**: Raw PCM streams never collide without explicit mixing. If two tracks play simultaneously, they must be combined through a MixBus.

**Implementation**:
- AudioGraph validates track timing
- Overlapping segments require shared Bus
- Error raised for unresolved overlaps

**Test**:
```python
def test_no_raw_overlap():
    graph = AudioGraph()
    track1 = graph.add_track("a")
    track2 = graph.add_track("b")
    
    # Same time, same output → must be mixed
    track1.add_segment(audio_a, start=0)
    track2.add_segment(audio_b, start=0)
    
    # This must not produce corrupted audio
    output = graph.render()
    assert is_valid_mix(output, audio_a, audio_b)
```

---

## 2. DSP Invariants

### 2.1 DSP Chains Are Deterministic

```
∀ input, effects: apply(effects, input) = apply(effects, input)
```

**Meaning**: Same input + same effects = same output. Always. No randomness unless explicitly seeded.

**Implementation**:
- Effects have no hidden state between calls (or state is resettable)
- Random effects require explicit seed parameter
- Effects report if they are stateful

**Test**:
```python
def test_dsp_determinism():
    effects = [Reverb(room_size=0.3), EQ(high_shelf_db=-2)]
    input_audio = load_test_audio()
    
    output1 = apply_effects(effects, input_audio)
    output2 = apply_effects(effects, input_audio)
    
    assert np.array_equal(output1, output2)
```

### 2.2 DSP Does Not Introduce External State

```
∀ effect ∈ dsp_chain: state(effect) ⊆ AudioGraph
```

**Meaning**: Effects cannot introduce state outside the AudioGraph. No global variables, no file I/O, no network calls.

**Implementation**:
- Effect interface enforces pure processing
- Effects receive all state via parameters
- Stateful effects must declare state explicitly

**Test**:
```python
def test_dsp_no_external_state():
    graph1 = AudioGraph()
    graph2 = AudioGraph()
    
    # Same effects, same input
    graph1.master_bus.add_effect(Reverb())
    graph2.master_bus.add_effect(Reverb())
    
    graph1.add_track("a").add_segment(test_audio)
    graph2.add_track("a").add_segment(test_audio)
    
    # Must be identical
    assert np.array_equal(graph1.render(), graph2.render())
```

### 2.3 Effect Order Is Explicit

```
∀ chain: render_order(chain) = declaration_order(chain)
```

**Meaning**: Effects apply in the order they are added. No implicit reordering.

**Test**:
```python
def test_effect_order():
    # Order matters: compression before reverb ≠ reverb before compression
    chain_a = [Compressor(), Reverb()]
    chain_b = [Reverb(), Compressor()]
    
    output_a = apply_effects(chain_a, test_audio)
    output_b = apply_effects(chain_b, test_audio)
    
    assert not np.array_equal(output_a, output_b)
```

---

## 3. Spatial Invariants

### 3.1 Spatialization Cannot Reorder Audio

```
∀ track: temporal_order(track.segments) = temporal_order(spatialized(track).segments)
```

**Meaning**: Spatial processing affects position, not sequence. Audio plays in the same order regardless of 3D position.

**Implementation**:
- Spatial processing operates on rendered PCM
- No segment reordering during spatialization
- Latency compensation is uniform

**Test**:
```python
def test_spatial_preserves_order():
    graph = AudioGraph()
    track = graph.add_track("dialogue")
    track.add_segment(segment_a, start=0)
    track.add_segment(segment_b, start=1000)
    track.set_position(Position(x=2, y=0, z=1))
    
    output = SpatialMixer().render(graph)
    
    # segment_a must still precede segment_b
    assert find_segment_start(output, segment_a) < find_segment_start(output, segment_b)
```

### 3.2 Spatial Position Is Bounded

```
∀ position: |position| < MAX_DISTANCE
```

**Meaning**: Positions cannot be infinite or NaN. Invalid positions are rejected.

**Test**:
```python
def test_spatial_bounds():
    with pytest.raises(ValueError):
        Position(x=float('inf'), y=0, z=0)
    
    with pytest.raises(ValueError):
        Position(x=float('nan'), y=0, z=0)
```

### 3.3 Binaural Output Is Stereo

```
∀ binaural_output: channels(binaural_output) = 2
```

**Meaning**: Binaural rendering always produces stereo output.

**Test**:
```python
def test_binaural_is_stereo():
    mixer = SpatialMixer(mode="binaural")
    output = mixer.render(graph)
    
    assert output.shape[1] == 2  # Stereo
```

---

## 4. Cloning Invariants

### 4.1 Cloned Voices Are Auditable

```
∀ clone_operation: ∃ audit_record(clone_operation)
```

**Meaning**: Every cloning operation has a corresponding audit entry. No silent cloning.

**Implementation**:
- CloningProvider writes to audit log before returning
- Audit log is append-only
- Audit includes: timestamp, voice_id, consent_token, hash of reference audio

**Test**:
```python
def test_cloning_audited():
    audit_before = audit_log.count()
    
    provider.clone(
        reference_audio=sample,
        target_text="Test",
        consent_token=valid_token,
    )
    
    assert audit_log.count() == audit_before + 1
    assert audit_log.last().operation == "clone"
```

### 4.2 Cloning Requires Valid Consent

```
∀ clone_operation: valid_consent(clone_operation.consent_token)
```

**Meaning**: Cloning fails without valid consent token. No bypass.

**Test**:
```python
def test_cloning_requires_consent():
    with pytest.raises(ConsentError):
        provider.clone(
            reference_audio=sample,
            target_text="Test",
            consent_token=None,
        )
    
    with pytest.raises(ConsentError):
        provider.clone(
            reference_audio=sample,
            target_text="Test",
            consent_token="invalid",
        )
```

### 4.3 Cloning Is Revocable

```
∀ consent_token: can_revoke(consent_token)
```

**Meaning**: Any granted consent can be revoked, which prevents future use.

**Test**:
```python
def test_cloning_revocable():
    token = grant_consent(voice_id="user_123")
    
    # Works before revocation
    result = provider.clone(audio, "Test", consent_token=token)
    assert result is not None
    
    # Revoke
    revoke_consent(token)
    
    # Fails after revocation
    with pytest.raises(ConsentRevokedError):
        provider.clone(audio, "Test", consent_token=token)
```

---

## 5. Ownership Invariants

### 5.1 Tracks Respect Registrar Ownership

```
∀ track: track.owner = registrar.get_owner(track.session_id)
```

**Meaning**: Track operations require ownership verification through the registrar.

**Implementation**:
- Track creation registers with Registrar
- Mutations check ownership
- Cross-session track access denied

**Test**:
```python
def test_track_ownership():
    session_a = registrar.create_session(actor="agent_a")
    session_b = registrar.create_session(actor="agent_b")
    
    track = graph.add_track("dialogue", session=session_a)
    
    # Owner can modify
    track.set_volume(0.5, actor="agent_a")  # OK
    
    # Non-owner cannot
    with pytest.raises(OwnershipError):
        track.set_volume(0.5, actor="agent_b")
```

### 5.2 Accessibility Overrides Track Ownership

```
∀ accessibility_event: accessibility_event > track_ownership
```

**Meaning**: Accessibility announcements can interrupt any track, regardless of ownership.

**Implementation**:
- Accessibility flag bypasses ownership check for interrupts
- Inherited from v2.9 registrar semantics
- Audit log records override events

**Test**:
```python
def test_accessibility_override():
    track = graph.add_track("music", session=session_a, volume=1.0)
    track.play()
    
    # Accessibility interrupt works regardless of ownership
    graph.accessibility_interrupt("Screen reader announcement", actor="screen_reader")
    
    # Music is ducked
    assert track.effective_volume < 1.0
```

---

## 6. Mixing Invariants

### 6.1 Mix Operations Are Commutative (Simple Mixing)

```
∀ A, B with equal gain: mix(A, B) = mix(B, A)
```

**Meaning**: For simple gain mixing, order doesn't matter. The result is the same.

**Note**: Order-dependent operations (sidechaining, ducking) are NOT commutative and must be explicit.

**Test**:
```python
def test_simple_mix_commutative():
    mix_ab = mix([track_a, track_b])
    mix_ba = mix([track_b, track_a])
    
    assert np.allclose(mix_ab, mix_ba)
```

### 6.2 Sidechaining Is Explicit

```
∀ sidechain: sidechain.source ≠ sidechain.target
```

**Meaning**: Sidechaining (e.g., ducking music for dialogue) must explicitly declare source and target. No implicit sidechaining.

**Test**:
```python
def test_sidechain_explicit():
    music = graph.add_track("music")
    dialogue = graph.add_track("dialogue")
    
    # Explicit sidechain declaration
    music.add_sidechain(
        source=dialogue,
        effect=Ducker(threshold_db=-20, ratio=3),
    )
    
    # This is NOT the same as:
    # dialogue.add_sidechain(source=music, ...)
```

---

## 7. Performance Invariants

### 7.1 Bounded Latency

```
∀ operation: latency(operation) < MAX_LATENCY
```

| Operation | Max Latency |
|-----------|-------------|
| Track creation | 1ms |
| Segment addition | 5ms |
| DSP chain (4 effects) | 5ms |
| Spatial render | 15ms |
| Full graph render (4 tracks) | 50ms |

**Test**:
```python
@pytest.mark.benchmark
def test_track_creation_latency():
    start = time.perf_counter()
    graph.add_track("test")
    elapsed = time.perf_counter() - start
    
    assert elapsed < 0.001  # 1ms
```

### 7.2 Memory Bounded

```
∀ session: memory(session) < MAX_SESSION_MEMORY
```

**Meaning**: A session cannot consume unbounded memory. Limits are enforced.

**Test**:
```python
def test_memory_bounded():
    graph = AudioGraph(max_memory_mb=100)
    
    # Should fail before consuming excessive memory
    with pytest.raises(MemoryLimitError):
        for i in range(1000):
            track = graph.add_track(f"track_{i}")
            track.add_segment(large_audio)  # 10MB each
```

---

## Enforcement

### Pre-Commit Hooks

All PRs must include:
1. Tests for any new invariant
2. No regressions on existing invariant tests

### CI Gate

```yaml
invariant-tests:
  runs-on: ubuntu-latest
  steps:
    - run: pytest tests/invariants/ -v --strict
```

### Runtime Assertions

Invariants are checked at runtime in debug builds:

```python
if __debug__:
    assert peak(output) <= 1.0, "Invariant 1.1 violated: clipping detected"
```

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-07 | Initial draft |

---

*This document must be reviewed and approved before v3.0-alpha begins.*
