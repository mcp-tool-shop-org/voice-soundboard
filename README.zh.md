<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/mcp-tool-shop-org/brand/main/logos/voice-soundboard/readme.png" alt="Voice Soundboard Logo" width="200" />
</p>

<p align="center">
    <em>Give your AI agents a voice that feels real.</em>
</p>

<p align="center">
    <a href="https://pypi.org/project/voice-soundboard/">
        <img src="https://img.shields.io/pypi/v/voice-soundboard.svg" alt="PyPI version">
    </a>
    <a href="https://github.com/mcp-tool-shop-org/voice-soundboard/actions/workflows/ci.yml">
        <img src="https://github.com/mcp-tool-shop-org/voice-soundboard/actions/workflows/ci.yml/badge.svg" alt="CI">
    </a>
    <a href="https://www.python.org/downloads/">
        <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
    </a>
    <a href="https://opensource.org/licenses/MIT">
        <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT">
    </a>
    <a href="https://mcp-tool-shop-org.github.io/voice-soundboard/">
        <img src="https://img.shields.io/badge/Landing_Page-live-blue" alt="Landing Page">
    </a>
</p>

<p align="center">
  Part of <a href="https://mcp-tool-shop.github.io/">MCP Tool Shop</a> — practical developer tools that stay out of your way.
</p>

---

**Voice Soundboard** 是一款文本转语音引擎，专为需要超越简单 `.mp3` 文件的开发者设计。

大多数文本转语音库都面临一个选择：要么是易于使用的 API，但隐藏了底层细节；要么是复杂的底层工具，需要音频工程方面的知识。Voice Soundboard 结合了这两种优势。

*   **简单的高级 API**: 只需要调用 `engine.speak("Hello")` 即可获得音频。
*   **强大的底层机制**: 在底层，我们采用一种编译器/图/引擎的架构，将 *表达的内容*（意图、情感）与 *渲染方式*（后端、音频格式）分开。
*   **零成本抽象**: 情感、风格和 SSML 都被编译成一个控制图，从而使运行时引擎保持快速和轻量级。

## 快速入门

```bash
pip install voice-soundboard
```

```python
from voice_soundboard import VoiceEngine

# Easy text-to-speech
engine = VoiceEngine()
result = engine.speak("Hello world! This is my AI voice.")
print(f"Saved to: {result.audio_path}")
```

## 架构

```
compile_request("text", emotion="happy")
        |
    ControlGraph (pure data)
        |
    engine.synthesize(graph)
        |
    PCM audio (numpy array)
```

**编译器** 将意图（文本 + 情感 + 风格）转换为 `ControlGraph`。

**引擎** 将图转换为音频。它不了解任何情感或风格。

这种分离意味着：
- 运行时特性是“免费”的（已经包含在图中）
- 引擎非常小，速度快，易于测试
- 后端可以灵活切换，而无需修改特性逻辑

## 用法

### 基本用法

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

### 高级用法：直接图操作

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

### 流式传输

流式传输分为两个层次：

1. **图流式传输**: `compile_stream()` 会在检测到句子边界时生成 `ControlGraph`。
2. **音频流式传输**: `StreamingSynthesizer` 将音频分块，以便进行实时播放。

**注意**: 这是一种句子级别的流式传输，而不是逐字逐句的增量合成。编译器在检测到句子边界之前不会生成图。真正的增量合成（具有回滚的推测执行）在架构上是支持的，但尚未实现。

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

## 命令行界面 (CLI)

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

## 后端

| 后端 | 质量 | Speed | 采样率 | 安装 |
| --------- | --------- | ------- | ------------- | --------- |
| Kokoro | 优秀 | 快速 (GPU) | 24000 Hz | `pip install voice-soundboard[kokoro]` |
| Piper | Great | 快速 (CPU) | 22050 Hz | `pip install voice-soundboard[piper]` |
| Mock | N/A | 即时 | 24000 Hz | (内置，用于测试) |

### Kokoro 设置

```bash
pip install voice-soundboard[kokoro]

# Download models
mkdir models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### Piper 设置

```bash
pip install voice-soundboard[piper]

# Download a voice (example: en_US_lessac_medium)
python -m piper.download_voices en_US-lessac-medium
```

Piper 的特性：
- **30 多个语音**，支持多种语言（英语、德语、法语、西班牙语）
- **纯 CPU** - 不需要 GPU
- **速度控制**，通过 `length_scale` 实现（反向：0.8 = 更快，1.2 = 较慢）
- **采样率**: 22050 Hz (特定于后端)

从 Kokoro 映射的语音：
```python
# These Kokoro voices have Piper equivalents
engine = VoiceEngine(Config(backend="piper"))
result = engine.speak("Hello!", voice="af_bella")  # Uses en_US_lessac_medium
```

## 包结构

```
voice_soundboard/
├── graph/          # ControlGraph, TokenEvent, SpeakerRef
├── compiler/       # Text -> Graph (all features live here)
│   ├── text.py     # Tokenization, normalization
│   ├── emotion.py  # Emotion -> prosody
│   ├── style.py    # Natural language style
│   └── compile.py  # Main entry point
├── engine/         # Graph -> PCM (no features, just synthesis)
│   └── backends/   # Kokoro, Piper, Mock
├── runtime/        # Streaming, scheduling
└── adapters/       # CLI, API, MCP (thin wrappers)
```

**关键不变性**: `engine/` 目录永远不会导入 `compiler/` 目录的内容。

## 架构不变性

这些规则在测试中得到强制执行，并且绝不能被违反：

1. **引擎隔离**: `engine/` 目录永远不会导入 `compiler/` 目录的内容。引擎不了解任何情感、风格或预设，只了解 `ControlGraph`。

2. **语音克隆边界**: 原始音频永远不会到达引擎。编译器会提取说话人嵌入信息；引擎只接收嵌入向量，并通过 `SpeakerRef` 传递。

3. **图稳定性**: `GRAPH_VERSION`（当前为 1）会在 `ControlGraph` 发生破坏性更改时更新。后端可以检查此版本以进行兼容性检查。

```python
from voice_soundboard.graph import GRAPH_VERSION, ControlGraph
assert GRAPH_VERSION == 1
```

## 从 v1 迁移

公共 API 没有变化：

```python
# This works in both v1 and v2
from voice_soundboard import VoiceEngine
engine = VoiceEngine()
result = engine.speak("Hello!", voice="af_bella", emotion="happy")
```

如果您导入了底层组件，请参阅迁移映射：

| v1 | v2 |
|----|-----|
| `engine.py` | `adapters/api.py` |
| `emotions.py` | `compiler/emotion.py` |
| `interpreter.py` | `compiler/style.py` |
| `engines/kokoro.py` | `engine/backends/kokoro.py` |

## 许可证

MIT -- 详情请参见 [LICENSE](LICENSE)。
