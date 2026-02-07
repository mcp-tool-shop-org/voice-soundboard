# Ducking System (v2 Limited)

Ducking in v2 provides the *perception* of audio mixing without actually overlapping audio streams. This preserves all timeline invariants while adding expressiveness.

## Core Insight

**Ducking is a gain envelope, not an overlap permission.**

You do not overlap audio in time. You apply gain shaping to speech following an event.

## How It Works

```
Event with ducking:
[laugh duck=0.5 fade_out=50ms fade_in=150ms]
```

Means:
1. Play the laugh event at full volume
2. Start next speech at 50% volume
3. Fade volume back to 100% over 150ms

**Speech is still sequential, not overlapped.**

## API

```python
from voice_soundboard.runtime import (
    DuckingEnvelope,
    DuckingProcessor,
    DUCKING_STANDARD,
)

# Define envelope
envelope = DuckingEnvelope(
    gain=0.5,        # Target gain (0.0-1.0)
    fade_out_ms=50,  # Not used in current implementation
    fade_in_ms=150,  # Ramp back to 1.0 over this duration
)

# Process timeline
processor = DuckingProcessor(sample_rate=24000)

for item in timeline:
    if is_event(item) and item.ducking:
        processor.set_ducking(item.ducking)
        output(item.pcm)
    elif is_speech(item):
        ducked_pcm = processor.process_speech(item.pcm)
        output(ducked_pcm)
```

## Presets

```python
from voice_soundboard.runtime import (
    DUCKING_SUBTLE,    # gain=0.8, fade_in=100ms
    DUCKING_STANDARD,  # gain=0.5, fade_in=150ms
    DUCKING_DRAMATIC,  # gain=0.3, fade_in=250ms
    DUCKING_PODCAST,   # gain=0.6, fade_in=200ms
)
```

## Invariants Preserved

| Invariant | Status |
|-----------|--------|
| No overlap | ✅ Audio is sequential |
| Deterministic | ✅ Same input → same output |
| Engine untouched | ✅ Adapter-level only |
| Event atomicity | ✅ Events are not modified |
| Duration unchanged | ✅ Gain doesn't change timing |

## What This Deliberately Does NOT Do

❌ Overlap WAV + speech
❌ Real-time sidechain compression
❌ Cross-backend DSP complexity

Those belong in a v3 audio engine, not here.

## Example Use Case

```python
from voice_soundboard.runtime import (
    Event, Token, stream_timeline,
    DuckingProcessor, DuckingEnvelope,
)

# Create timeline
timeline = [
    Event("laugh", duration=0.25),
    Token("That was funny!", duration=0.8),
]

# Stream with ducking
processor = DuckingProcessor(sample_rate=24000)
ducking = DuckingEnvelope(gain=0.5, fade_in_ms=200)

# Render
for item in stream_timeline(timeline):
    if item.kind == "event":
        processor.set_ducking(ducking)
        play(render_event(item))
    else:
        pcm = render_speech(item)
        pcm = processor.process_speech(pcm)
        play(pcm)
```

The listener perceives the speech "emerging" from behind the laugh, even though they're strictly sequential.

## Limitations (v2)

1. **Single-shot**: Ducking applies to the next speech item only
2. **No overlap**: Events and speech never play simultaneously
3. **No sidechain**: No automatic gain reduction based on event loudness
4. **No cross-fade**: Fade is one-way (in), not bidirectional

For true audio mixing, see [DEFERRED_FEATURES.md](DEFERRED_FEATURES.md).
