# Migration Guide: v1 to v2

## Executive Summary

**If you only use the public API, no changes are required.**

v2 is an internal architectural rewrite. The public API (`VoiceEngine.speak()`) is unchanged.

```python
# This works identically in v1 and v2
from voice_soundboard import VoiceEngine

engine = VoiceEngine()
result = engine.speak("Hello world!", voice="af_bella", emotion="happy")
print(result.audio_path)
```

---

## What Changed Internally

### Architecture

v1:
```
speak() → emotion_logic → style_logic → engine.generate() → PCM
```

v2:
```
speak() → compile_request() → ControlGraph → engine.synthesize() → PCM
```

The key insight: **Features compile to data, not code paths.**

In v2, all feature logic (emotion, style, presets) runs at compile time, producing a `ControlGraph`. The engine knows nothing about emotions - it just synthesizes the graph.

### Module Structure

| v1 Location | v2 Location |
|-------------|-------------|
| `engine.py` | `adapters/api.py` |
| `emotions.py` | `compiler/emotion.py` |
| `interpreter.py` | `compiler/style.py` |
| `engines/kokoro.py` | `engine/backends/kokoro.py` |
| (none) | `graph/types.py` |

### New Concepts

1. **ControlGraph** - The canonical IR between compiler and engine
2. **GRAPH_VERSION** - Schema version for compatibility checking
3. **Backends** - Engine implementations (Kokoro, Piper, Mock)

---

## What Did NOT Change (Public API)

### VoiceEngine.speak()

Same signature, same return type:

```python
def speak(
    self,
    text: str,
    voice: str | None = None,
    preset: str | None = None,
    speed: float | None = None,
    style: str | None = None,
    emotion: str | None = None,
    save_as: str | None = None,
    normalize: bool = True,
) -> SpeechResult
```

### SpeechResult

Same fields:

```python
@dataclass
class SpeechResult:
    audio_path: Path
    duration_seconds: float
    generation_time: float
    voice_used: str
    sample_rate: int
    realtime_factor: float
    # v2 addition (optional, not breaking):
    graph: ControlGraph | None = None
```

### Config

Same options:

```python
@dataclass
class Config:
    output_dir: Path
    model_dir: Path
    device: str
    default_voice: str
    default_speed: float
    sample_rate: int
    backend: str
```

### quick_speak()

Same behavior:

```python
from voice_soundboard import quick_speak
path = quick_speak("Hello world!")
```

---

## Known Differences

### Sample Rate

- **Kokoro**: 24000 Hz (unchanged)
- **Piper**: 22050 Hz (new backend)

The sample rate is now **backend-dependent**. Use `result.sample_rate` to check.

### Speed Semantics

Unified in v2:
- `speed=2.0` means **twice as fast** in all backends
- Piper internally converts to `length_scale=0.5`

### Streaming

v1 streaming was engine-level. v2 streaming is graph-level:

```python
# v2 streaming
from voice_soundboard.compiler import compile_stream
from voice_soundboard.runtime import StreamingSynthesizer

backend = load_backend()
streamer = StreamingSynthesizer(backend)

for graph in compile_stream(text_iterator):
    for chunk in streamer.stream(graph):
        play(chunk)
```

This is **sentence-level streaming**, not word-by-word. True incremental streaming is deferred to v2.x.

---

## If You Imported Internals

If you imported from internal modules, here are the mappings:

### Emotions

```python
# v1
from voice_soundboard.emotions import get_emotion_params

# v2
from voice_soundboard.compiler.emotion import emotion_to_prosody
```

### Direct Engine Access

```python
# v1
from voice_soundboard.engines.kokoro import KokoroEngine
engine = KokoroEngine()
audio = engine.generate("Hello", voice="af_bella")

# v2
from voice_soundboard.engine import load_backend
from voice_soundboard.compiler import compile_request

backend = load_backend("kokoro")
graph = compile_request("Hello", voice="af_bella")
audio = backend.synthesize(graph)
```

### Voice Data

```python
# v1
from voice_soundboard.voices import VOICE_LIST

# v2
from voice_soundboard.compiler.voices import VOICES
```

---

## New Features (v2 Only)

### Piper Backend

```python
engine = VoiceEngine(Config(backend="piper"))
result = engine.speak("Hello!", voice="en_US_lessac_medium")
```

### Paralinguistic Events

```python
from voice_soundboard.graph import ControlGraph, ParalinguisticEvent, Paralinguistic

graph = compile_request("Ha ha, that's funny!")
graph.events.append(
    ParalinguisticEvent(Paralinguistic.LAUGH, start_time=0.0, duration=0.3)
)
```

### Direct Graph Manipulation

```python
from voice_soundboard.compiler import compile_request
from voice_soundboard.engine import load_backend

# Compile once
graph = compile_request("Hello!", emotion="happy")

# Inspect/modify
print(graph.tokens)
print(graph.speaker)

# Synthesize
backend = load_backend()
audio = backend.synthesize(graph)
```

---

## Compatibility Checklist

✅ **No action required if you:**
- Only use `VoiceEngine.speak()`
- Only use `quick_speak()`
- Only use standard voices

⚠️ **Review needed if you:**
- Imported from internal modules
- Relied on specific sample rates
- Used streaming APIs
- Extended the engine

---

## Questions?

Open an issue: https://github.com/mcp-tool-shop-org/voice-soundboard-v2/issues
