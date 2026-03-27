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

## Migration

The public API is unchanged across all major versions:

```python
# This works in v1, v2, and v3
from voice_soundboard import VoiceEngine

engine = VoiceEngine()
result = engine.speak("Hello!", voice="af_bella", emotion="happy")
```

### v2 to v3

v3 removes 11 speculative modules that shipped with zero test coverage (distributed, serverless, intelligence, analytics, monitoring, security, ambiance, scenes, spatial, mcp, v3-alpha). The public API is unchanged. If you imported removed internals, see the [CHANGELOG](https://github.com/mcp-tool-shop-org/voice-soundboard/blob/main/CHANGELOG.md) for details.

### v1 to v2

If you imported internal modules, use this migration mapping:

| v1 | v2+ |
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
