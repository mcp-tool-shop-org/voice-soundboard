---
title: Getting Started
description: Install Voice Soundboard, run your first synthesis, and explore the CLI.
sidebar:
  order: 1
---

## Installation

Voice Soundboard is a Python package available on [PyPI](https://pypi.org/project/voice-soundboard/).

```bash
# Core library
pip install voice-soundboard

# With Kokoro backend (GPU)
pip install voice-soundboard[kokoro]

# With Piper backend (CPU)
pip install voice-soundboard[piper]
```

Requires **Python 3.10+**.

## Quick Start

```python
from voice_soundboard import VoiceEngine

engine = VoiceEngine()
result = engine.speak("Hello world! This is my AI voice.")
print(f"Saved to: {result.audio_path}")
```

That is the entire happy path. The engine picks a default backend and voice, compiles
your text into a `ControlGraph`, synthesizes audio, and returns a result object.

## Adding Voice and Emotion

```python
# With a specific voice
result = engine.speak("Cheerio!", voice="bm_george")

# With a preset
result = engine.speak("Breaking news!", preset="announcer")

# With emotion
result = engine.speak("I'm so happy!", emotion="excited")

# With natural language style
result = engine.speak("Good morning!", style="warmly and cheerfully")
```

## CLI Usage

Voice Soundboard includes a command-line interface for quick synthesis and discovery.

```bash
# Speak text
voice-soundboard speak "Hello world!"

# With options
voice-soundboard speak "Breaking news!" --preset announcer --speed 1.1

# List available voices
voice-soundboard voices

# List presets
voice-soundboard presets

# List emotions
voice-soundboard emotions
```
