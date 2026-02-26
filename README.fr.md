<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
</p>

<p align="center">
  
            <img src="https://raw.githubusercontent.com/mcp-tool-shop-org/brand/main/logos/voice-soundboard/readme.png"
           alt="Voice Soundboard Logo" width="200" />
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

**Voice Soundboard** est un moteur de synthèse vocale conçu pour les développeurs qui ont besoin de plus qu'un simple fichier `.mp3`.

La plupart des bibliothèques de synthèse vocale offrent un choix limité : des API simples qui masquent tout, ou des outils complexes de bas niveau qui nécessitent des connaissances en ingénierie audio. Voice Soundboard vous offre le meilleur des deux mondes.

*   **API de haut niveau simple** : Il suffit d'appeler `engine.speak("Bonjour")` pour obtenir l'audio.
*   **Fonctionnement interne puissant** : Au niveau interne, nous utilisons une architecture Compilateur/Graphe/Moteur qui sépare *ce qui* est dit (intention, émotion) de *la manière* dont cela est rendu (backend, format audio).
*   **Abstractions sans coût supplémentaire** : Les émotions, les styles et le SSML sont compilés dans un graphe de contrôle, ce qui permet au moteur d'exécution de rester rapide et léger.

## Démarrage rapide

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

## Architecture

```
compile_request("text", emotion="happy")
        |
    ControlGraph (pure data)
        |
    engine.synthesize(graph)
        |
    PCM audio (numpy array)
```

**Le compilateur** transforme l'intention (texte + émotion + style) en un `ControlGraph`.

**Le moteur** transforme le graphe en audio. Il ne connaît rien des émotions ou des styles.

Cette séparation signifie :
- Les fonctionnalités sont "gratuites" au moment de l'exécution (déjà intégrées dans le graphe)
- Le moteur est petit, rapide et testable
- Les backends peuvent être échangés sans modifier la logique des fonctionnalités

## Utilisation

### Basique

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

### Avancé : Manipulation directe du graphe

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

Le streaming fonctionne à deux niveaux :

1. **Streaming du graphe** : `compile_stream()` renvoie des graphes de contrôle à chaque délimitation de phrase.
2. **Streaming audio** : `StreamingSynthesizer` découpe l'audio pour une lecture en temps réel.

**Remarque** : Il s'agit d'un streaming au niveau de la phrase, et non d'une synthèse incrémentale mot par mot. Le compilateur attend la fin des phrases avant de renvoyer les graphes. La synthèse incrémentale réelle (exécution spéculative avec retour en arrière) est prise en charge architecturalement, mais n'est pas encore implémentée.

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

## CLI (Interface en ligne de commande)

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

## Backends (Serveurs)

| Backend (Serveur) | Qualité | Speed | Taux d'échantillonnage | Installation |
| --------- | --------- | ------- | ------------- | --------- |
| Kokoro | Excellent | Rapide (GPU) | 24000 Hz | `pip install voice-soundboard[kokoro]` |
| Piper | Great | Rapide (CPU) | 22050 Hz | `pip install voice-soundboard[piper]` |
| Mock | N/A | Instantané | 24000 Hz | (intégré, pour les tests) |

### Configuration de Kokoro

```bash
pip install voice-soundboard[kokoro]

# Download models
mkdir models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### Configuration de Piper

```bash
pip install voice-soundboard[piper]

# Download a voice (example: en_US_lessac_medium)
python -m piper.download_voices en_US-lessac-medium
```

Fonctionnalités de Piper :
- **Plus de 30 voix** dans plusieurs langues (anglais, allemand, français, espagnol)
- **Purement CPU** - pas de GPU requis
- **Contrôle de la vitesse** via `length_scale` (inversé : 0,8 = plus rapide, 1,2 = plus lent)
- **Taux d'échantillonnage** : 22050 Hz (spécifique au backend)

Correspondance des voix de Kokoro :
```python
# These Kokoro voices have Piper equivalents
engine = VoiceEngine(Config(backend="piper"))
result = engine.speak("Hello!", voice="af_bella")  # Uses en_US_lessac_medium
```

## Structure du paquet

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

**Invariant clé** : `engine/` n'importe jamais de `compiler/`.

## Invariants de l'architecture

Ces règles sont appliquées par des tests et ne doivent jamais être violées :

1. **Isolation du moteur** : `engine/` n'importe jamais de `compiler/`. Le moteur ne connaît rien des émotions, des styles ou des préréglages, seulement des graphes de contrôle.

2. **Frontière de clonage vocal** : L'audio brut n'atteint jamais le moteur. Le compilateur extrait les embeddings du locuteur ; le moteur reçoit uniquement des vecteurs d'embedding via `SpeakerRef`.

3. **Stabilité du graphe** : `GRAPH_VERSION` (actuellement 1) est incrémenté en cas de modifications majeures du `ControlGraph`. Les backends peuvent vérifier cela pour la compatibilité.

```python
from voice_soundboard.graph import GRAPH_VERSION, ControlGraph
assert GRAPH_VERSION == 1
```

## Migration depuis la version 1

L'API publique n'a pas changé :

```python
# This works in both v1 and v2
from voice_soundboard import VoiceEngine
engine = VoiceEngine()
result = engine.speak("Hello!", voice="af_bella", emotion="happy")
```

Si vous avez importé des éléments internes, consultez la correspondance de migration :

| v1 | v2 |
|----|-----|
| `engine.py` | `adapters/api.py` |
| `emotions.py` | `compiler/emotion.py` |
| `interpreter.py` | `compiler/style.py` |
| `engines/kokoro.py` | `engine/backends/kokoro.py` |

## Licence

MIT -- voir [LICENSE](LICENSE) pour plus de détails.
