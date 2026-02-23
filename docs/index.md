# Voice Soundboard

Text-to-speech engine with compiler/graph/engine architecture. Give your AI agents a voice that feels real.

## Key Features

- **Simple High-Level API** — Just call `engine.speak("Hello")` and get audio
- **Compiler/Graph/Engine Architecture** — Separates intent from rendering
- **Emotion & Style Support** — Compiled into control graphs for zero-cost runtime
- **Streaming** — Sentence-level graph and audio streaming for real-time playback
- **Multiple Backends** — Kokoro (GPU), Piper (CPU), Mock (testing)
- **CLI** — Speak text, list voices/presets/emotions from the command line

## Install / Quick Start

```bash
pip install voice-soundboard
```

```python
from voice_soundboard import VoiceEngine
engine = VoiceEngine()
result = engine.speak("Hello world!")
```

## Links

- [GitHub Repository](https://github.com/mcp-tool-shop-org/voice-soundboard)
- [voice-soundboard on PyPI](https://pypi.org/project/voice-soundboard/)
- [MCP Tool Shop](https://github.com/mcp-tool-shop-org)
