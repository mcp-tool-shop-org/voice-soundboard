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

**Voice Soundboard** é um motor de texto para fala desenvolvido para programadores que precisam de mais do que apenas um arquivo `.mp3`.

A maioria das bibliotecas de TTS (Text-to-Speech) oferece uma escolha: APIs simples que escondem tudo, ou ferramentas complexas de baixo nível que exigem conhecimento em engenharia de áudio. O Voice Soundboard oferece o melhor dos dois mundos.

*   **API de alto nível simples**: Basta chamar `engine.speak("Olá")` e obter o áudio.
*   **Funcionalidades avançadas**: Por baixo, usamos uma arquitetura de compilador/grafo/motor que separa o *que* é dito (intenção, emoção) de *como* é renderizado (backend, formato de áudio).
*   **Abstrações sem custo adicional**: Emoções, estilos e SSML são compilados em um grafo de controle, para que o motor de execução permaneça rápido e leve.

## Início rápido

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

## Arquitetura

```
compile_request("text", emotion="happy")
        |
    ControlGraph (pure data)
        |
    engine.synthesize(graph)
        |
    PCM audio (numpy array)
```

**O compilador** transforma a intenção (texto + emoção + estilo) em um `ControlGraph`.

**O motor** transforma o grafo em áudio. Ele não sabe nada sobre emoções ou estilos.

Essa separação significa:
- As funcionalidades são "gratuitas" em tempo de execução (já incorporadas no grafo)
- O motor é pequeno, rápido e testável
- Os backends podem ser substituídos sem alterar a lógica das funcionalidades

## Uso

### Básico

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

### Avançado: Manipulação direta do grafo

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

### Streaming

O streaming opera em dois níveis:

1. **Streaming do grafo**: `compile_stream()` gera ControlGraphs à medida que os limites das frases são detectados.
2. **Streaming de áudio**: `StreamingSynthesizer` divide o áudio em partes para reprodução em tempo real.

**Observação**: Este é um streaming em nível de frase, não uma síntese incremental palavra por palavra. O compilador espera os limites das frases antes de gerar os grafos. A síntese incremental verdadeira (execução especulativa com reversão) é suportada arquiteturalmente, mas ainda não foi implementada.

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

## CLI (Interface de Linha de Comando)

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

## Backends

| Backend (Servidor de Áudio) | Qualidade | Speed | Taxa de amostragem | Instalação |
| --------- | --------- | ------- | ------------- | --------- |
| Kokoro | Excelente | Rápido (GPU) | 24000 Hz | `pip install voice-soundboard[kokoro]` |
| Piper | Great | Rápido (CPU) | 22050 Hz | `pip install voice-soundboard[piper]` |
| Mock | N/A | Instantâneo | 24000 Hz | (integrado, para testes) |

### Configuração do Kokoro

```bash
pip install voice-soundboard[kokoro]

# Download models
mkdir models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### Configuração do Piper

```bash
pip install voice-soundboard[piper]

# Download a voice (example: en_US_lessac_medium)
python -m piper.download_voices en_US-lessac-medium
```

Recursos do Piper:
- **Mais de 30 vozes** em vários idiomas (inglês, alemão, francês, espanhol)
- **Apenas CPU** - não requer GPU
- **Controle de velocidade** via `length_scale` (inverso: 0.8 = mais rápido, 1.2 = mais lento)
- **Taxa de amostragem**: 22050 Hz (específica do backend)

Mapeamento de vozes do Kokoro:
```python
# These Kokoro voices have Piper equivalents
engine = VoiceEngine(Config(backend="piper"))
result = engine.speak("Hello!", voice="af_bella")  # Uses en_US_lessac_medium
```

## Estrutura do Pacote

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

**Invariante chave**: O diretório `engine/` nunca importa nada do diretório `compiler/`.

## Invariantes da Arquitetura

Essas regras são aplicadas em testes e nunca devem ser violadas:

1. **Isolamento do motor**: O diretório `engine/` nunca importa nada do diretório `compiler/`. O motor não sabe nada sobre emoções, estilos ou configurações predefinidas -- apenas ControlGraphs.

2. **Limite de clonagem de voz**: O áudio bruto nunca chega ao motor. O compilador extrai as características do falante; o motor recebe apenas vetores de características via `SpeakerRef`.

3. **Estabilidade do grafo**: `GRAPH_VERSION` (atualmente 1) é incrementado em caso de alterações que quebrem a compatibilidade do ControlGraph. Os backends podem verificar isso para garantir a compatibilidade.

```python
from voice_soundboard.graph import GRAPH_VERSION, ControlGraph
assert GRAPH_VERSION == 1
```

## Migração da versão 1

A API pública não foi alterada:

```python
# This works in both v1 and v2
from voice_soundboard import VoiceEngine
engine = VoiceEngine()
result = engine.speak("Hello!", voice="af_bella", emotion="happy")
```

Se você importou elementos internos, consulte o mapeamento de migração:

| v1 | v2 |
|----|-----|
| `engine.py` | `adapters/api.py` |
| `emotions.py` | `compiler/emotion.py` |
| `interpreter.py` | `compiler/style.py` |
| `engines/kokoro.py` | `engine/backends/kokoro.py` |

## Licença

MIT -- veja [LICENSE](LICENSE) para detalhes.
