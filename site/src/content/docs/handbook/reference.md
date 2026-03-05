---
title: Reference
description: Emotions, styles, presets, migration guide, security scope, and PyPI package info.
sidebar:
  order: 5
---

## Emotions

Add emotion to any synthesis call. The compiler translates emotions into prosody
parameters that are baked into the `ControlGraph`.

```python
result = engine.speak("I'm so happy!", emotion="excited")
result = engine.speak("That's terrible.", emotion="sad")
result = engine.speak("Watch out!", emotion="urgent")
```

List all available emotions:

```bash
voice-soundboard emotions
```

## Natural Language Styles

Styles let you describe the voice quality in plain English. The compiler
interprets these and maps them to prosody adjustments.

```python
result = engine.speak("Good morning!", style="warmly and cheerfully")
result = engine.speak("The market dropped.", style="serious and measured")
```

## Presets

Presets bundle voice + emotion + style + speed into a single name.

```python
result = engine.speak("Breaking news!", preset="announcer")
result = engine.speak("Once upon a time...", preset="storyteller")
```

List all available presets:

```bash
voice-soundboard presets
```

## Migration from v1

The public API is unchanged between v1 and v2:

```python
# This works in both v1 and v2
from voice_soundboard import VoiceEngine

engine = VoiceEngine()
result = engine.speak("Hello!", voice="af_bella", emotion="happy")
```

If you imported internal modules, use this migration mapping:

| v1 | v2 |
|----|-----|
| `engine.py` | `adapters/api.py` |
| `emotions.py` | `compiler/emotion.py` |
| `interpreter.py` | `compiler/style.py` |
| `engines/kokoro.py` | `engine/backends/kokoro.py` |

## Security & Data Scope

- **Data accessed**: Reads text input for TTS synthesis. Processes audio through configured backends (Kokoro, Piper, or mock). Returns PCM audio as numpy arrays or WAV files.
- **Data NOT accessed**: No network egress by default (backends are local). No telemetry, analytics, or tracking. No user data storage beyond transient audio buffers.
- **Permissions required**: Read access to TTS model files. Optional write access for audio output.

See [SECURITY.md](https://github.com/mcp-tool-shop-org/voice-soundboard/blob/main/SECURITY.md) for vulnerability reporting.

## PyPI Package

```bash
pip install voice-soundboard
```

- **Package**: [voice-soundboard on PyPI](https://pypi.org/project/voice-soundboard/)
- **License**: MIT
- **Python**: 3.10+
- **Source**: [GitHub](https://github.com/mcp-tool-shop-org/voice-soundboard)
