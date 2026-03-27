---
title: For Beginners
description: New to Voice Soundboard? Start here for a gentle introduction.
sidebar:
  order: 99
---

## What Is Voice Soundboard?

Voice Soundboard is a Python text-to-speech library that turns plain text into spoken audio. It wraps multiple TTS backends (Kokoro, Piper, OpenAI, and others) behind a single API so you can generate speech with one line of code instead of wrestling with model files, sample rates, and audio formats yourself.

The library separates *what* you want to say (text, emotion, style) from *how* it gets rendered (which TTS engine, which voice model). This means you can switch from a local GPU backend to a cloud API without changing your application code.

## Who Is This For?

- **Application developers** adding voice output to chatbots, assistants, or accessibility features
- **Hobbyists** building voice-enabled side projects who want results in minutes, not hours
- **AI/ML engineers** who need a clean TTS abstraction they can slot into an LLM pipeline

No audio engineering background is required. If you can write basic Python and use `pip`, you are ready.

## 1. Prerequisites

You need **Python 3.10 or newer**. Check your version:

```bash
python --version
```

A virtual environment is recommended to keep dependencies isolated:

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

No GPU is required. The Piper backend runs on CPU, and the built-in Mock backend needs no models at all.

## 2. Installation

Install the core library from PyPI:

```bash
pip install voice-soundboard
```

For real audio output, install a backend. Piper is the easiest choice because it runs on CPU with no extra setup beyond downloading a voice model:

```bash
pip install voice-soundboard[piper]
```

If you have an NVIDIA GPU available, Kokoro produces excellent quality:

```bash
pip install voice-soundboard[kokoro]
```

To install everything at once (all backends):

```bash
pip install voice-soundboard[all]
```

## 3. Your First Synthesis

Create a file called `hello.py`:

```python
from voice_soundboard import VoiceEngine, Config

# Use the mock backend so this runs without model downloads
engine = VoiceEngine(Config(backend="mock"))
result = engine.speak("Hello world! This is my first synthesis.")
print(f"Audio saved to: {result.audio_path}")
print(f"Duration: {result.duration_seconds:.2f}s")
```

Run it:

```bash
python hello.py
```

The Mock backend produces silence but exercises the full pipeline (compiler, graph, engine). This confirms your installation works before downloading real models.

To generate audible speech, switch the backend to `"piper"` or `"kokoro"` after installing the corresponding extra and downloading models (see the [Backends](/voice-soundboard/handbook/backends/) page).

## 4. Key Concepts

Voice Soundboard uses a three-stage pipeline:

1. **Compiler** -- Turns your text, voice, emotion, and style choices into a `ControlGraph` (pure data). All the "intelligence" lives here.
2. **ControlGraph** -- An immutable data structure that describes exactly what to synthesize. It contains token events, speaker references, and prosody parameters.
3. **Engine** -- Takes a `ControlGraph` and produces PCM audio through a backend (Kokoro, Piper, OpenAI, etc.). The engine knows nothing about emotions or styles; those have already been compiled away.

This separation means you can compile once and synthesize many times, swap backends without changing application code, and test the compiler in isolation without any TTS models.

## 5. Choosing Voices, Emotions, and Presets

### Voices

Voice Soundboard ships with 28 built-in Kokoro voice definitions spanning American and British accents in male and female variants. Pass a voice ID to `speak()`:

```python
result = engine.speak("Good morning!", voice="af_bella")   # American female, warm
result = engine.speak("Good morning!", voice="bm_george")  # British male, authoritative
```

List available voices from the CLI:

```bash
voice-soundboard voices
```

### Emotions

Emotions adjust pitch, speed, energy, and pause timing at compile time. They are baked into the graph before the engine ever sees them:

```python
result = engine.speak("I passed the exam!", emotion="excited")
result = engine.speak("I'm sorry to hear that.", emotion="sad")
result = engine.speak("Stay alert.", emotion="serious")
```

Available emotions include: neutral, happy, excited, joyful, enthusiastic, calm, peaceful, relaxed, sad, melancholy, angry, frustrated, fearful, anxious, surprised, confident, and serious.

### Presets

Presets bundle a voice, speed, and description into a single name:

```python
result = engine.speak("Breaking news!", preset="announcer")
result = engine.speak("Once upon a time...", preset="storyteller")
```

Built-in presets: `assistant`, `narrator`, `announcer`, `storyteller`, `whisper`.

### Natural Language Styles

Describe the voice quality in plain English and the compiler maps it to prosody adjustments:

```python
result = engine.speak("Welcome back.", style="warmly and cheerfully")
```

## 6. Using the CLI

The `voice-soundboard` command is installed automatically with the package:

```bash
# Synthesize text
voice-soundboard speak "Hello from the CLI!"

# Specify voice and speed
voice-soundboard speak "Breaking news!" --preset announcer --speed 1.1

# Discovery commands
voice-soundboard voices     # List all voices
voice-soundboard presets    # List all presets
voice-soundboard emotions   # List all emotions
```

The CLI is a thin wrapper around the same `VoiceEngine` API you use in Python.

## 7. Common Mistakes

1. **Forgetting to download models.** Installing `voice-soundboard[kokoro]` gives you the Python bindings, but Kokoro also needs ONNX model files in a `models/` directory. If you see a "model not found" error, revisit the [Backends](/voice-soundboard/handbook/backends/) page for download commands.

2. **Using the wrong backend name.** Backend names are lowercase strings: `"kokoro"`, `"piper"`, `"openai"`, `"mock"`. A typo like `"Kokoro"` or `"piper-tts"` will raise an error. Check with `Config(backend="mock")` first to confirm your code works before switching to a real backend.

3. **Mixing up `voice` and `preset`.** A voice is a single speaker identity (`"af_bella"`). A preset bundles a voice with a speed and description (`"announcer"`). If you pass both, the explicit `voice` parameter wins. Pick one or the other to avoid confusion.

4. **Expecting word-level streaming.** `compile_stream()` yields graphs at sentence boundaries, not after every word. If your LLM produces a long paragraph without punctuation, the compiler waits until it sees a sentence-ending character. Add punctuation to your prompts for smoother streaming.

5. **Running Kokoro without a GPU.** Kokoro uses ONNX Runtime and benefits heavily from GPU acceleration. On a CPU-only machine it will work but may be slow. Use Piper instead for fast CPU-only synthesis.

## 8. Next Steps

Now that you have a working setup, explore these handbook pages:

- [Architecture](/voice-soundboard/handbook/architecture/) -- Understand the Compiler / Graph / Engine design and why it matters.
- [Backends](/voice-soundboard/handbook/backends/) -- Set up Kokoro (GPU), Piper (CPU), cloud backends (OpenAI, ElevenLabs, Azure), or Coqui for your use case.
- [Streaming](/voice-soundboard/handbook/streaming/) -- Wire Voice Soundboard into an LLM token stream for real-time voice output.
- [Reference](/voice-soundboard/handbook/reference/) -- Full emotion list, style guide, presets, migration notes, and security scope.

For bug reports or feature requests, visit the [GitHub repository](https://github.com/mcp-tool-shop-org/voice-soundboard).

## 9. Glossary

- **Backend** -- A TTS engine that converts a `ControlGraph` into audio. Examples: Kokoro (GPU), Piper (CPU), OpenAI (cloud), Mock (testing).
- **Compiler** -- The first stage of the pipeline. It takes your text, emotion, style, and voice choices and produces a `ControlGraph`. All "intelligence" lives here.
- **ControlGraph** -- An immutable data structure that describes exactly what to synthesize. It contains token events, speaker references, and prosody parameters. This is the contract between the compiler and the engine.
- **Emotion** -- A compile-time concept that adjusts pitch, speed, energy, and pause timing. After compilation, the emotion name is gone; only numeric prosody values remain in the graph.
- **Engine** -- The second stage of the pipeline. It takes a `ControlGraph` and produces PCM audio through a backend. The engine knows nothing about emotions or styles.
- **PCM** -- Pulse-code modulation. The raw digital audio format produced by synthesis, stored as a NumPy float32 array.
- **Preset** -- A named bundle of voice, speed, and description (e.g., `"announcer"` = Michael voice at 1.1x speed).
- **Prosody** -- The rhythm, stress, and intonation of speech. Emotions and styles modify prosody parameters at compile time.
- **SpeakerRef** -- A reference to a speaker identity inside a `ControlGraph`. Can point to a built-in voice ID or a custom speaker embedding.
- **Style** -- A natural-language description of how speech should sound (e.g., "warmly and cheerfully"). The compiler interprets it into prosody adjustments.
- **TokenEvent** -- A single unit in a `ControlGraph` representing a word or pause, with attached prosody modifiers (pitch scale, energy scale, duration scale).
