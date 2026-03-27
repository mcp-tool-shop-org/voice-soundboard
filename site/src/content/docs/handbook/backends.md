---
title: Backends
description: Configure Kokoro (GPU), Piper (CPU), and Mock backends for Voice Soundboard.
sidebar:
  order: 3
---

Voice Soundboard ships with multiple TTS backends. Each backend implements the same
interface, so you can switch between them without changing application code.

## Backend Comparison

| Backend | Quality | Speed | Sample Rate | Install |
|---------|---------|-------|-------------|---------|
| Kokoro | Excellent | Fast (GPU) | 24000 Hz | `pip install voice-soundboard[kokoro]` |
| Piper | Great | Fast (CPU) | 22050 Hz | `pip install voice-soundboard[piper]` |
| OpenAI | Excellent | Cloud | 24000 Hz | `pip install voice-soundboard[openai]` |
| Coqui | Great | Moderate (GPU) | 22050 Hz | `pip install voice-soundboard[coqui]` |
| ElevenLabs | Premium | Cloud | 44100 Hz | `pip install voice-soundboard[elevenlabs]` |
| Azure | Excellent | Cloud | 24000 Hz | `pip install voice-soundboard[azure]` |
| Mock | N/A | Instant | 24000 Hz | Built-in (testing) |

## Kokoro (GPU)

Kokoro is the recommended backend for production use when a GPU is available.
It produces excellent quality audio at 24 kHz sample rate.

### Setup

```bash
pip install voice-soundboard[kokoro]

# Download models
mkdir models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### Usage

```python
from voice_soundboard import VoiceEngine, Config

engine = VoiceEngine(Config(backend="kokoro"))
result = engine.speak("Hello from Kokoro!", voice="af_bella")
```

## Piper (CPU)

Piper is ideal when no GPU is available. It runs entirely on CPU and supports
30+ voices across multiple languages (English, German, French, Spanish).

### Setup

```bash
pip install voice-soundboard[piper]

# Download a voice (example: en_US_lessac_medium)
python -m piper.download_voices en_US-lessac-medium
```

### Features

- **30+ voices** across multiple languages
- **Pure CPU** — no GPU required
- **Speed control** via `length_scale` (inverted: 0.8 = faster, 1.2 = slower)
- **Sample rate**: 22050 Hz (backend-specific)

### Usage

```python
from voice_soundboard import VoiceEngine, Config

engine = VoiceEngine(Config(backend="piper"))
result = engine.speak("Hello from Piper!")
```

## Voice Mapping

Kokoro voice names are automatically mapped to Piper equivalents when using the
Piper backend. This means you can write code with Kokoro voice names and it will
work on CPU machines with Piper installed.

```python
engine = VoiceEngine(Config(backend="piper"))
result = engine.speak("Hello!", voice="af_bella")  # Uses en_US_lessac_medium
```

## OpenAI (Cloud)

Uses the OpenAI TTS API. Requires an API key and internet connectivity.

```bash
pip install voice-soundboard[openai]
```

```python
from voice_soundboard import VoiceEngine, Config

engine = VoiceEngine(Config(backend="openai"))
result = engine.speak("Hello from OpenAI TTS!")
```

Set your API key via the `OPENAI_API_KEY` environment variable.

## Coqui (GPU)

Coqui TTS provides open-source models with GPU acceleration.

```bash
pip install voice-soundboard[coqui]
```

```python
engine = VoiceEngine(Config(backend="coqui"))
result = engine.speak("Hello from Coqui!")
```

## ElevenLabs (Cloud)

Premium cloud voices with high fidelity at 44100 Hz sample rate. Requires an API key.

```bash
pip install voice-soundboard[elevenlabs]
```

```python
engine = VoiceEngine(Config(backend="elevenlabs"))
result = engine.speak("Hello from ElevenLabs!")
```

Set your API key via the `ELEVENLABS_API_KEY` environment variable.

## Azure Neural TTS (Cloud)

Microsoft Azure Cognitive Services Speech. Requires an Azure subscription.

```bash
pip install voice-soundboard[azure]
```

```python
engine = VoiceEngine(Config(backend="azure"))
result = engine.speak("Hello from Azure!")
```

Configure via `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` environment variables.

## Mock Backend

The mock backend produces instant silence. It is built-in and requires no
installation. Use it for testing and CI pipelines.

```python
from voice_soundboard import VoiceEngine, Config

engine = VoiceEngine(Config(backend="mock"))
result = engine.speak("This produces silence instantly.")
```
