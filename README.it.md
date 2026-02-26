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

**Voice Soundboard** è un motore di sintesi vocale progettato per sviluppatori che necessitano di qualcosa di più di un semplice file `.mp3`.

La maggior parte delle librerie di sintesi vocale offrono una scelta limitata: API semplici che nascondono tutto, oppure strumenti complessi di basso livello che richiedono conoscenze di ingegneria audio. Voice Soundboard offre il meglio di entrambi i mondi.

*   **API di alto livello semplice**: Basta chiamare `engine.speak("Hello")` per ottenere l'audio.
*   **Funzionalità avanzate**: Internamente, utilizziamo un'architettura Compiler/Graph/Engine che separa *ciò che* viene detto (intento, emozione) da *come* viene riprodotto (backend, formato audio).
*   **Astrazioni a costo zero**: Emozioni, stili e SSML vengono compilati in un grafo di controllo, in modo che il motore di runtime rimanga veloce e leggero.

## Guida rapida

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

## Architettura

```
compile_request("text", emotion="happy")
        |
    ControlGraph (pure data)
        |
    engine.synthesize(graph)
        |
    PCM audio (numpy array)
```

**Il compilatore** trasforma l'intento (testo + emozione + stile) in un `ControlGraph`.

**Il motore** trasforma il grafo in audio. Non conosce nulla di emozioni o stili.

Questa separazione significa:
- Le funzionalità sono "gratuite" a runtime (già integrate nel grafo)
- Il motore è piccolo, veloce e testabile
- I backend possono essere sostituiti senza modificare la logica delle funzionalità

## Utilizzo

### Base

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

### Avanzato: Manipolazione diretta del grafo

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

Lo streaming opera a due livelli:

1. **Streaming del grafo**: `compile_stream()` restituisce ControlGraph quando vengono rilevati i confini delle frasi.
2. **Streaming audio**: `StreamingSynthesizer` suddivide l'audio per la riproduzione in tempo reale.

**Nota**: Questo è lo streaming a livello di frase, non la sintesi incrementale parola per parola. Il compilatore attende i confini delle frasi prima di restituire i grafi. La vera sintesi incrementale (esecuzione speculativa con rollback) è supportata a livello architetturale, ma non ancora implementata.

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

## CLI (Command Line Interface)

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

## Backend

| Backend (sistema di riproduzione) | Qualità | Speed | Frequenza di campionamento | Installazione |
| --------- | --------- | ------- | ------------- | --------- |
| Kokoro | Eccellente | Veloce (GPU) | 24000 Hz | `pip install voice-soundboard[kokoro]` |
| Piper | Great | Veloce (CPU) | 22050 Hz | `pip install voice-soundboard[piper]` |
| Mock | N/A | Immediato | 24000 Hz | (integrato, per i test) |

### Configurazione di Kokoro

```bash
pip install voice-soundboard[kokoro]

# Download models
mkdir models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### Configurazione di Piper

```bash
pip install voice-soundboard[piper]

# Download a voice (example: en_US_lessac_medium)
python -m piper.download_voices en_US-lessac-medium
```

Funzionalità di Piper:
- **Più di 30 voci** in diverse lingue (inglese, tedesco, francese, spagnolo)
- **Solo CPU** - non è richiesta una GPU
- **Controllo della velocità** tramite `length_scale` (inverso: 0.8 = più veloce, 1.2 = più lento)
- **Frequenza di campionamento**: 22050 Hz (specifica del backend)

Mappatura delle voci da Kokoro:
```python
# These Kokoro voices have Piper equivalents
engine = VoiceEngine(Config(backend="piper"))
result = engine.speak("Hello!", voice="af_bella")  # Uses en_US_lessac_medium
```

## Struttura del pacchetto

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

**Invariante fondamentale**: la directory `engine/` non importa nulla dalla directory `compiler/`.

## Invarianti dell'architettura

Queste regole sono applicate tramite test e non devono mai essere violate:

1. **Isolamento del motore**: la directory `engine/` non importa nulla dalla directory `compiler/`. Il motore non conosce nulla di emozioni, stili o preset: conosce solo ControlGraph.

2. **Confine del cloning della voce**: l'audio grezzo non raggiunge mai il motore. Il compilatore estrae gli embedding del parlante; il motore riceve solo vettori di embedding tramite `SpeakerRef`.

3. **Stabilità del grafo**: `GRAPH_VERSION` (attualmente 1) viene incrementato in caso di modifiche che interrompono la compatibilità del ControlGraph. I backend possono verificare questo valore per garantire la compatibilità.

```python
from voice_soundboard.graph import GRAPH_VERSION, ControlGraph
assert GRAPH_VERSION == 1
```

## Migrazione dalla versione 1

L'API pubblica non è cambiata:

```python
# This works in both v1 and v2
from voice_soundboard import VoiceEngine
engine = VoiceEngine()
result = engine.speak("Hello!", voice="af_bella", emotion="happy")
```

Se hai importato elementi interni, consulta la mappatura della migrazione:

| v1 | v2 |
|----|-----|
| `engine.py` | `adapters/api.py` |
| `emotions.py` | `compiler/emotion.py` |
| `interpreter.py` | `compiler/style.py` |
| `engines/kokoro.py` | `engine/backends/kokoro.py` |

## Licenza

MIT -- consulta [LICENSE](LICENSE) per i dettagli.
