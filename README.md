# Voice Soundboard v2

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Text-to-speech for AI agents and developers.** Compiler → Graph → Engine architecture.

## What's New in v2

v2 is a complete architectural rewrite with the same public API:

- **Compiler/Engine separation**: Features compile to a `ControlGraph`, engine just synthesizes
- **Zero runtime feature cost**: Emotion, style, SSML are compile-time transforms
- **Swappable backends**: Kokoro, Piper, or bring your own
- **Same API**: `VoiceEngine.speak()` works exactly like v1

## Quick Start

```bash
pip install voice-soundboard
```

```python
from voice_soundboard import VoiceEngine

engine = VoiceEngine()
result = engine.speak("Hello world!")
print(result.audio_path)  # output/af_bella_<hash>.wav
```

## Architecture

```
compile_request("text", emotion="happy")
        ↓
    ControlGraph (pure data)
        ↓
    engine.synthesize(graph)
        ↓
    PCM audio (numpy array)
```

**The compiler** transforms intent (text + emotion + style) into a `ControlGraph`.

**The engine** transforms the graph into audio. It knows nothing about emotions or styles.

This separation means:
- Features are "free" at runtime (already baked into the graph)
- Engine is tiny, fast, testable
- Backends are swappable without touching feature logic

## Usage

### Basic

```python
from voice_soundboard import VoiceEngine

engine = VoiceEngine()

# Simple
result = engine.speak("Hello world!")

# With voice
result = engine.speak("Cheerio!", voice="bm_george")

# With preset
result = engine.speak("Breaking news!", preset="announcer")

# With emotion
result = engine.speak("I'm so happy!", emotion="excited")

# With natural language style
result = engine.speak("Good morning!", style="warmly and cheerfully")
```

### Advanced: Direct Graph Manipulation

```python
from voice_soundboard.compiler import compile_request
from voice_soundboard.engine import load_backend

# Compile once
graph = compile_request(
    "Hello world!",
    voice="af_bella",
    emotion="happy",
)

# Synthesize many times (or with different backends)
backend = load_backend("kokoro")
audio = backend.synthesize(graph)
```

### Streaming

Streaming operates at two levels:

1. **Graph streaming**: `compile_stream()` yields ControlGraphs as sentence boundaries are detected
2. **Audio streaming**: `StreamingSynthesizer` chunks audio for real-time playback

**Note**: This is sentence-level streaming, not word-by-word incremental synthesis. The compiler waits for sentence boundaries before yielding graphs. True incremental synthesis (speculative execution with rollback) is architecturally supported but not yet implemented.

```python
from voice_soundboard.compiler import compile_stream
from voice_soundboard.runtime import StreamingSynthesizer

# For LLM output or real-time text
def text_chunks():
    yield "Hello, "
    yield "how are "
    yield "you today?"

backend = load_backend()
streamer = StreamingSynthesizer(backend)

for graph in compile_stream(text_chunks()):
    for audio_chunk in streamer.stream(graph):
        play(audio_chunk)
```

## CLI

```bash
# Speak text
voice-soundboard speak "Hello world!"

# With options
voice-soundboard speak "Breaking news!" --preset announcer --speed 1.1

# List voices
voice-soundboard voices

# List presets
voice-soundboard presets

# List emotions
voice-soundboard emotions
```

## Backends

| Backend | Quality | Speed | Sample Rate | Install |
|---------|---------|-------|-------------|---------|
| Kokoro | ⭐⭐⭐⭐⭐ | Fast (GPU) | 24000 Hz | `pip install voice-soundboard[kokoro]` |
| Piper | ⭐⭐⭐⭐ | Fast (CPU) | 22050 Hz | `pip install voice-soundboard[piper]` |
| Mock | N/A | Instant | 24000 Hz | (built-in, for testing) |

### Kokoro Setup

```bash
pip install voice-soundboard[kokoro]

# Download models
mkdir models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### Piper Setup

```bash
pip install voice-soundboard[piper]

# Download a voice (example: en_US_lessac_medium)
python -m piper.download_voices en_US-lessac-medium
```

Piper features:
- **30+ voices** across multiple languages (English, German, French, Spanish)
- **Pure CPU** - no GPU required
- **Speed control** via `length_scale` (inverted: 0.8 = faster, 1.2 = slower)
- **Sample rate**: 22050 Hz (backend-specific)

Voice mapping from Kokoro:
```python
# These Kokoro voices have Piper equivalents
engine = VoiceEngine(Config(backend="piper"))
result = engine.speak("Hello!", voice="af_bella")  # Uses en_US_lessac_medium
```

## Package Structure

```
voice_soundboard/
├── graph/          # ControlGraph, TokenEvent, SpeakerRef
├── compiler/       # Text → Graph (all features live here)
│   ├── text.py     # Tokenization, normalization
│   ├── emotion.py  # Emotion → prosody
│   ├── style.py    # Natural language style
│   └── compile.py  # Main entry point
├── engine/         # Graph → PCM (no features, just synthesis)
│   └── backends/   # Kokoro, Piper, Mock
├── runtime/        # Streaming, scheduling
└── adapters/       # CLI, API, MCP (thin wrappers)
```

**Key invariant**: `engine/` never imports from `compiler/`.

## Architecture Invariants

These rules are enforced in tests and must never be violated:

1. **Engine isolation**: `engine/` never imports from `compiler/`. The engine knows nothing about emotions, styles, or presets - only ControlGraphs.

2. **Voice cloning boundary**: Raw audio never reaches the engine. The compiler extracts speaker embeddings; the engine receives only embedding vectors via `SpeakerRef`.

3. **Graph stability**: `GRAPH_VERSION` (currently 1) is bumped on breaking changes to ControlGraph. Backends can check this for compatibility.

```python
from voice_soundboard.graph import GRAPH_VERSION, ControlGraph
assert GRAPH_VERSION == 1
```

## Migration from v1

The public API is unchanged:

```python
# This works in both v1 and v2
from voice_soundboard import VoiceEngine
engine = VoiceEngine()
result = engine.speak("Hello!", voice="af_bella", emotion="happy")
```

If you imported internals, see the migration mapping:

| v1 | v2 |
|----|-----|
| `engine.py` | `adapters/api.py` |
| `emotions.py` | `compiler/emotion.py` |
| `interpreter.py` | `compiler/style.py` |
| `engines/kokoro.py` | `engine/backends/kokoro.py` |

## License

MIT
