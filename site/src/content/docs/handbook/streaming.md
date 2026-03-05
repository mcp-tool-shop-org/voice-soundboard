---
title: Streaming
description: Sentence-level streaming synthesis for real-time audio and LLM integration.
sidebar:
  order: 4
---

Voice Soundboard supports streaming synthesis at two levels, designed for real-time
audio playback and LLM integration.

## Two Levels of Streaming

1. **Graph streaming**: `compile_stream()` yields `ControlGraph`s as sentence boundaries are detected in incoming text chunks
2. **Audio streaming**: `StreamingSynthesizer` chunks audio for real-time playback

## Basic Streaming

```python
from voice_soundboard.compiler import compile_stream
from voice_soundboard.runtime import StreamingSynthesizer
from voice_soundboard.engine import load_backend

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

## How `compile_stream()` Works

The compiler accumulates text chunks until it detects a sentence boundary
(period, question mark, exclamation point, etc.). At each boundary it yields
a `ControlGraph` for that sentence.

This is **sentence-level streaming**, not word-by-word incremental synthesis.
The compiler waits for sentence boundaries before yielding graphs.

:::note
True incremental synthesis (speculative execution with rollback) is
architecturally supported by the Compiler / Graph / Engine design but is not
yet implemented.
:::

## LLM Integration

Streaming is designed to work with LLM output. Pass the LLM's token stream
directly to `compile_stream()`:

```python
from voice_soundboard.compiler import compile_stream
from voice_soundboard.runtime import StreamingSynthesizer

def llm_stream():
    """Your LLM token generator."""
    for token in my_llm.generate("Tell me a story"):
        yield token

backend = load_backend()
streamer = StreamingSynthesizer(backend)

for graph in compile_stream(llm_stream()):
    for chunk in streamer.stream(graph):
        play(chunk)  # Audio plays while LLM is still generating
```

This gives you near-real-time voice output: audio starts playing as soon as
the first sentence completes, while the LLM continues generating the rest.

## Direct Graph Manipulation

For advanced use cases, you can compile and synthesize separately:

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

This is useful when you want to compile a graph once and replay it, or
synthesize the same graph through multiple backends for comparison.
