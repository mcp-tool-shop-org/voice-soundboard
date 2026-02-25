<p align="center">
  <img src="logo.png" alt="Voice Soundboard Logo" width="200" />
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

**Voice Soundboard**は、単なる`.mp3`ファイル以上の機能が必要な開発者向けのテキスト読み上げエンジンです。

多くのTTSライブラリでは、使いやすいAPIを提供する一方で、内部構造が隠されているか、または高度な知識を必要とする複雑なツールしか提供されていません。Voice Soundboardは、その両方の利点を兼ね備えています。

*   **シンプルで高レベルなAPI**: `engine.speak("Hello")`と呼び出すだけで、音声が得られます。
*   **強力な内部構造**: 内部では、コンパイラ/グラフ/エンジンというアーキテクチャを採用しており、発話内容（意図、感情）と、その表現方法（バックエンド、音声フォーマット）を分離しています。
*   **オーバーヘッドのない機能**: 感情、スタイル、SSMLなどは、制御グラフにコンパイルされるため、実行時のエンジンは高速で軽量です。

## クイックスタート

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

## アーキテクチャ

```
compile_request("text", emotion="happy")
        |
    ControlGraph (pure data)
        |
    engine.synthesize(graph)
        |
    PCM audio (numpy array)
```

**コンパイラ**は、意図（テキスト + 感情 + スタイル）を`ControlGraph`に変換します。

**エンジン**は、グラフを音声に変換します。エンジンは、感情やスタイルに関する知識を持ちません。

この分離により、以下の利点があります。
- 実行時の機能は「無料」（グラフに組み込まれている）
- エンジンは小さく、高速で、テスト可能
- バックエンドを機能ロジックを変更せずに置き換え可能

## 使い方

### 基本

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

### 応用編：グラフの直接操作

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

### ストリーミング

ストリーミングは、2つのレベルで動作します。

1. **グラフストリーミング**: `compile_stream()`は、文の区切りが検出されるたびに`ControlGraph`を生成します。
2. **音声ストリーミング**: `StreamingSynthesizer`は、音声をチャンクに分割してリアルタイムで再生します。

**注意**: これは文レベルのストリーミングであり、単語ごとの逐次合成ではありません。コンパイラは、グラフを生成する前に文の区切りを待ちます。真の逐次合成（ロールバック付きの推測的実行）は、アーキテクチャ的にサポートされていますが、まだ実装されていません。

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

## CLI（コマンドラインインターフェース）

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

## バックエンド

| バックエンド | 品質 | Speed | サンプリングレート | インストール |
| --------- | --------- | ------- | ------------- | --------- |
| Kokoro | 優れている | 高速（GPU） | 24000 Hz | `pip install voice-soundboard[kokoro]` |
| Piper | Great | 高速（CPU） | 22050 Hz | `pip install voice-soundboard[piper]` |
| Mock | N/A | 即時 | 24000 Hz | （内蔵、テスト用） |

### Kokoroの設定

```bash
pip install voice-soundboard[kokoro]

# Download models
mkdir models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### Piperの設定

```bash
pip install voice-soundboard[piper]

# Download a voice (example: en_US_lessac_medium)
python -m piper.download_voices en_US-lessac-medium
```

Piperの特徴：
- **30種類以上の音声**（複数の言語：英語、ドイツ語、フランス語、スペイン語）
- **CPUのみ** - GPUは不要
- **速度制御**: `length_scale`で調整（0.8 = 高速、1.2 = 低速）
- **サンプリングレート**: 22050 Hz（バックエンドによって異なる）

Kokoroからの音声マッピング
```python
# These Kokoro voices have Piper equivalents
engine = VoiceEngine(Config(backend="piper"))
result = engine.speak("Hello!", voice="af_bella")  # Uses en_US_lessac_medium
```

## パッケージ構成

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

**重要なルール**: `engine/`は、`compiler/`からインポートしてはいけません。

## アーキテクチャの制約

これらのルールはテストで検証され、決して破られてはなりません。

1. **エンジンの分離**: `engine/`は、`compiler/`からインポートしてはいけません。エンジンは、感情、スタイル、プリセットに関する知識を持たず、`ControlGraph`のみを認識します。

2. **音声クローニングの境界**: 生の音声は、エンジンに到達しません。コンパイラは、話者埋め込み情報を抽出し、エンジンは`SpeakerRef`を介して埋め込みベクトルのみを受け取ります。

3. **グラフの安定性**: `GRAPH_VERSION`（現在は1）は、`ControlGraph`の互換性を壊す変更があった場合にのみ変更されます。バックエンドは、このバージョンを確認して互換性を判断できます。

```python
from voice_soundboard.graph import GRAPH_VERSION, ControlGraph
assert GRAPH_VERSION == 1
```

## v1からの移行

公開APIは変更されていません。

```python
# This works in both v1 and v2
from voice_soundboard import VoiceEngine
engine = VoiceEngine()
result = engine.speak("Hello!", voice="af_bella", emotion="happy")
```

内部APIを使用していた場合は、移行マッピングを参照してください。

| v1 | v2 |
|----|-----|
| `engine.py` | `adapters/api.py` |
| `emotions.py` | `compiler/emotion.py` |
| `interpreter.py` | `compiler/style.py` |
| `engines/kokoro.py` | `engine/backends/kokoro.py` |

## ライセンス

MIT -- 詳細については、[LICENSE](LICENSE)を参照してください。
