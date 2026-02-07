# Audio Events Specification

This document defines the authoritative specification for audio event assets.
Audio events are pre-recorded WAV files inserted into the speech stream for
paralinguistic sounds like `[laugh]`, `[sigh]`, `[breath]`, etc.

## Design Principles

Audio-event WAVs must:
- Integrate cleanly into streamed PCM
- Never require rewinding or resynthesis
- Preserve speech intelligibility
- Be deterministic (testable)

**Critical constraint**: Audio events are **timeline inserts**, not overlays.
Overlapping speech + event WAVs causes phase issues and intelligibility loss.

---

## Timing Rules (Authoritative)

### Rule 1 — Events Are Inserted at Boundaries Only

An audio event may only occur:
- **Before** a token
- **After** a token  
- **Replacing** a pause

It may **never** overlap token audio.

```
✅ Valid:
[laugh] hello        # before
hello [sigh]         # after
hello ... [laugh] ... world   # replacing pause

❌ Invalid:
he[laugh]llo         # mid-token overlap
```

The compiler enforces this; the adapter assumes it.

### Rule 2 — Event Time Is Owned by the Event

When a WAV event is rendered:
- Its **full duration** is played
- Speech following it is **delayed** accordingly
- **No time compression or overlap** occurs

```
timeline_time += event.wav_duration
```

Speech resumes after the event completes.

### Rule 3 — Silence Is Explicit and Accounted For

If the graph contains:
- A `ParalinguisticEvent`
- Followed by a pause or silence

Then:
- The event **replaces** the pause
- The pause is **not** additionally rendered

This avoids double gaps.

### Rule 4 — Sample Rate Must Match Output

All event WAVs must be:
- Pre-resampled to the backend's output sample rate
- OR resampled once at adapter load time

At runtime:
- **No resampling**
- **No time-stretching**

This keeps streaming cheap and glitch-free.

### Rule 5 — Events Do Not Affect Prosody Automatically

If you want:
- Pitch rise after laugh
- Energy drop after sigh

That must already be present in the `ControlGraph` prosody tracks.

The WAV adapter:
- **Plays audio**
- **Does not** modify pitch/energy curves

### Rule 6 — Events Are Atomic PCM Blocks

Once playback starts:
- The **full WAV** is emitted
- **No cancellation**
- **No mid-event truncation**

This guarantees deterministic streaming and simple buffering.

---

## Reference Streaming Algorithm

```python
for item in lowered_timeline:
    if isinstance(item, AudioEvent):
        pcm = audio_event_adapter.render(item)
        output_pcm(pcm)
    elif isinstance(item, Silence):
        output_silence(item.duration)
    else:  # speech PCM from engine
        output_pcm(item)
```

No mixing, no ducking, no overlap.

---

## Asset Directory Layout

```
assets/audio_events/
├── manifest.json
├── laugh/
│   ├── soft.wav
│   ├── medium.wav
│   └── hard.wav
├── sigh/
│   ├── short.wav
│   └── long.wav
├── breath/
│   └── neutral.wav
└── ...
```

No magic filenames. Everything is declared in the manifest.

---

## WAV File Requirements

Each WAV file must satisfy:

| Property | Requirement |
|----------|-------------|
| Format | PCM WAV |
| Channels | Mono |
| Sample rate | Backend output rate (e.g., 24000 Hz) |
| Bit depth | 16-bit |
| Leading silence | ≤ 10 ms |
| Trailing silence | ≤ 20 ms |
| Peak | ≤ −1 dBFS |

This avoids pops, lag, and clipping.

---

## Manifest Format

`manifest.json` is the contract, not the code:

```json
{
  "sample_rate": 24000,
  "events": {
    "laugh": {
      "variants": [
        {
          "id": "soft",
          "file": "laugh/soft.wav",
          "intensity_range": [0.0, 0.4],
          "duration": 0.18
        },
        {
          "id": "medium",
          "file": "laugh/medium.wav",
          "intensity_range": [0.4, 0.7],
          "duration": 0.25
        },
        {
          "id": "hard",
          "file": "laugh/hard.wav",
          "intensity_range": [0.7, 1.0],
          "duration": 0.35
        }
      ]
    }
  }
}
```

### Variant Selection Rules (Deterministic)

Given: `ParalinguisticEvent(type="laugh", intensity=0.65)`

Selection algorithm:
1. Find event type in manifest
2. Find variant where `intensity ∈ intensity_range`
3. If multiple match → pick **narrowest range**
4. If none match → pick **closest range**
5. If still none → skip event

**No randomness. Ever.**

---

## Validation

The adapter validates all assets at load time:

```python
adapter = AudioEventAdapter.from_manifest("assets/audio_events/manifest.json")
# Raises ValueError if validation fails
```

Checked:
- All WAV files exist
- Channels = 1 (mono)
- Sample rate matches manifest
- Bit depth = 16
- Duration matches (within 50ms tolerance)

Duration mismatches are treated as **asset bugs**, not runtime problems.

---

## Integration Example

```python
from voice_soundboard.adapters.audio_events import (
    AudioEventAdapter,
    render_timeline_with_events,
)

# Load adapter (validates assets)
adapter = AudioEventAdapter.try_load("assets/audio_events/manifest.json")

# Compile graph with events
graph = compile_request("[laugh] That's hilarious!")

# Synthesize speech
speech_pcm = engine.synthesize(graph)

# Insert events into timeline
final_pcm = render_timeline_with_events(
    graph, speech_pcm, adapter, engine.sample_rate
)
```

---

## Why This Spec Works

- **Deterministic timing** — testable math
- **No engine coupling** — adapter is independent
- **Simple streaming** — no mixing or ducking
- **Easy validation** — CI can check assets
- **Production-grade** — same pattern as game VO + Foley

---

## Adding New Events

1. Create WAV files meeting the spec
2. Add entries to `manifest.json`
3. Run validation: `AudioEventAdapter.from_manifest(...)`
4. Test: event renders, duration matches

The manifest is the source of truth.
