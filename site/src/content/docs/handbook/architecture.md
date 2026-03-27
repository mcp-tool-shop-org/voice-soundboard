---
title: Architecture
description: Compiler, Graph, and Engine — how Voice Soundboard separates intent from synthesis.
sidebar:
  order: 2
---

Voice Soundboard uses a **Compiler / Graph / Engine** architecture that cleanly separates
*what* is said (intent, emotion, style) from *how* it is rendered (backend, audio format).

## Pipeline

```
compile_request("text", emotion="happy")
        |
    ControlGraph (pure data)
        |
    engine.synthesize(graph)
        |
    PCM audio (numpy array)
```

## The Three Layers

### Compiler

The compiler transforms intent (text + emotion + style) into a `ControlGraph`. All feature
logic — emotions, styles, SSML parsing, presets — lives here.

```python
from voice_soundboard.compiler import compile_request

graph = compile_request(
    "Hello world!",
    voice="af_bella",
    emotion="happy",
)
```

### ControlGraph

An immutable data structure containing `TokenEvent`s, `SpeakerRef`s, and prosody parameters.
This is the contract between the compiler and the engine.

```python
from voice_soundboard.graph import GRAPH_VERSION, ControlGraph

assert GRAPH_VERSION == 1
```

### Engine

The engine transforms graphs into PCM audio. It knows nothing about emotions, styles, or
presets — only how to synthesize a `ControlGraph` through a backend.

```python
from voice_soundboard.engine import load_backend

backend = load_backend("kokoro")
audio = backend.synthesize(graph)
```

## Why This Separation Matters

- **Features are free at runtime** — emotion and style are already baked into the graph
- **Engine stays tiny, fast, testable** — it only does synthesis
- **Backends are swappable** without touching feature logic
- **Graph is serializable** — compile once, synthesize many times or on different machines

## Architecture Invariants

These rules are enforced in tests and must never be violated:

1. **Engine isolation**: `engine/` never imports from `compiler/`. The engine knows nothing about emotions, styles, or presets — only `ControlGraph`s.

2. **Voice cloning boundary**: Raw audio never reaches the engine. The compiler extracts speaker embeddings; the engine receives only embedding vectors via `SpeakerRef`.

3. **Graph stability**: `GRAPH_VERSION` (currently 1) is bumped on breaking changes to `ControlGraph`. Backends can check this for compatibility.

## Package Structure

```
voice_soundboard/
├── graph/          # ControlGraph, TokenEvent, SpeakerRef
├── compiler/       # Text -> Graph (all features live here)
│   ├── text.py     # Tokenization, normalization
│   ├── emotion.py  # Emotion -> prosody
│   ├── style.py    # Natural language style
│   └── compile.py  # Main entry point
├── engine/         # Graph -> PCM (no features, just synthesis)
│   └── backends/   # Kokoro, Piper, OpenAI, Coqui, ElevenLabs, Azure, Mock
├── runtime/        # Streaming, timeline, ducking, batch, cache
├── adapters/       # CLI, public API (thin wrappers)
├── streaming/      # Incremental word-by-word synthesis
├── conversation/   # Multi-speaker dialogue
├── cloning/        # Speaker embedding extraction
├── speakers/       # Speaker database
├── realtime/       # Low-latency streaming engine
├── plugins/        # Plugin architecture
├── quality/        # Voice quality metrics
├── formats/        # Audio format conversion, LUFS
├── debug/          # Graph visualization, profiler
├── testing/        # VoiceMock, AudioAssertions
└── accessibility/  # Screen reader integration, captions
```
