<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.md">English</a> | <a href="README.fr.md">Français</a> | <a href="README.hi.md">हिन्दी</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
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
    <a href="https://codecov.io/gh/mcp-tool-shop-org/voice-soundboard">
        <img src="https://codecov.io/gh/mcp-tool-shop-org/voice-soundboard/branch/main/graph/badge.svg" alt="Codecov">
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

**Voice Soundboard** es un motor de texto a voz diseñado para desarrolladores que necesitan algo más que un simple archivo `.mp3`.

La mayoría de las bibliotecas de TTS ofrecen una elección limitada: APIs sencillas que ocultan todo, o herramientas de bajo nivel y complejas que requieren conocimientos de ingeniería de audio. Voice Soundboard le ofrece lo mejor de ambos mundos.

*   **API de alto nivel sencilla**: Simplemente llame a `engine.speak("Hola")` y obtenga el audio.
*   **Internos potentes**: En el núcleo, utilizamos una arquitectura de Compilador/Gráfico/Motor que separa *lo que* se dice (intención, emoción) de *cómo* se reproduce (backend, formato de audio).
*   **Abstracciones sin costo adicional**: Las emociones, los estilos y el SSML se compilan en un gráfico de control, por lo que el motor de ejecución permanece rápido y ligero.

## Comienzo rápido

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

## Arquitectura

```
compile_request("text", emotion="happy")
        |
    ControlGraph (pure data)
        |
    engine.synthesize(graph)
        |
    PCM audio (numpy array)
```

**El compilador** transforma la intención (texto + emoción + estilo) en un `ControlGraph`.

**El motor** transforma el gráfico en audio. No sabe nada sobre emociones ni estilos.

Esta separación significa:
- Las funciones son "gratuitas" en tiempo de ejecución (ya están integradas en el gráfico).
- El motor es pequeño, rápido y fácil de probar.
- Los backends se pueden cambiar sin modificar la lógica de las funciones.

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

### Avanzado: Manipulación directa del gráfico

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

### Transmisión

La transmisión opera en dos niveles:

1. **Transmisión de gráficos**: `compile_stream()` genera ControlGraphs a medida que se detectan los límites de las oraciones.
2. **Transmisión de audio**: `StreamingSynthesizer` divide el audio para la reproducción en tiempo real.

**Nota**: Esto es una transmisión a nivel de oración, no una síntesis incremental palabra por palabra. El compilador espera los límites de las oraciones antes de generar gráficos. La síntesis incremental verdadera (ejecución especulativa con retroceso) está soportada arquitectónicamente, pero aún no está implementada.

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

## CLI (Interfaz de línea de comandos)

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

## Backends (Servidores)

| Backend (Servidor) | Calidad | Velocidad | Frecuencia de muestreo | Instalación |
|---------|---------|-------|-------------|---------|
| Kokoro | Excelente | Rápido (GPU) | 24000 Hz | `pip install voice-soundboard[kokoro]` |
| Piper | Muy bueno | Rápido (CPU) | 22050 Hz | `pip install voice-soundboard[piper]` |
| Mock (Simulación) | N/A (No disponible) | Instantáneo (Inmediato) | 24000 Hz | (integrado, para pruebas) |

### Configuración de Kokoro

```bash
pip install voice-soundboard[kokoro]

# Download models
mkdir models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### Configuración de Piper

```bash
pip install voice-soundboard[piper]

# Download a voice (example: en_US_lessac_medium)
python -m piper.download_voices en_US-lessac-medium
```

Características de Piper:
- **Más de 30 voces** en múltiples idiomas (inglés, alemán, francés, español)
- **Solo CPU** - no se requiere GPU
- **Control de velocidad** a través de `length_scale` (inverso: 0.8 = más rápido, 1.2 = más lento)
- **Frecuencia de muestreo**: 22050 Hz (específica del backend)

Mapeo de voces de Kokoro:
```python
# These Kokoro voices have Piper equivalents
engine = VoiceEngine(Config(backend="piper"))
result = engine.speak("Hello!", voice="af_bella")  # Uses en_US_lessac_medium
```

## Estructura del paquete

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

**Invariante clave**: `engine/` nunca importa nada de `compiler/`.

## Invariantes de la arquitectura

Estas reglas se aplican en las pruebas y nunca deben violarse:

1. **Aislamiento del motor**: `engine/` nunca importa nada de `compiler/`. El motor no sabe nada sobre emociones, estilos ni configuraciones preestablecidas; solo conoce los ControlGraphs.

2. **Límite de clonación de voz**: El audio sin procesar nunca llega al motor. El compilador extrae incrustaciones de hablantes; el motor solo recibe vectores de incrustación a través de `SpeakerRef`.

3. **Estabilidad del gráfico**: `GRAPH_VERSION` (actualmente 1) se actualiza cuando hay cambios importantes en el ControlGraph. Los backends pueden verificar esto para la compatibilidad.

```python
from voice_soundboard.graph import GRAPH_VERSION, ControlGraph
assert GRAPH_VERSION == 1
```

## Migración desde la versión 1

La API pública no ha cambiado:

```python
# This works in both v1 and v2
from voice_soundboard import VoiceEngine
engine = VoiceEngine()
result = engine.speak("Hello!", voice="af_bella", emotion="happy")
```

Si importó elementos internos, consulte el mapeo de migración:

| v1 | v2 |
|----|-----|
| `engine.py` | `adapters/api.py` |
| `emotions.py` | `compiler/emotion.py` |
| `interpreter.py` | `compiler/style.py` |
| `engines/kokoro.py` | `engine/backends/kokoro.py` |

## Seguridad y alcance de datos

- **Datos accedidos:** Lee la entrada de texto para la síntesis de voz. Procesa el audio a través de los backends configurados (Kokoro, Piper o un entorno de prueba). Devuelve audio en formato PCM como arreglos de numpy o archivos WAV.
- **Datos NO accedidos:** Por defecto, no hay comunicación de red (los backends son locales). No hay telemetría, análisis ni seguimiento. No se almacena ningún dato de usuario más allá de los búferes de audio temporales.
- **Permisos requeridos:** Acceso de lectura a los archivos del modelo de síntesis de voz. Acceso de escritura opcional para la salida de audio.

Consulte [SECURITY.md](SECURITY.md) para informar sobre vulnerabilidades.

## Cuadro de evaluación

| Categoría | Puntuación |
|----------|-------|
| A. Seguridad | 10/10 |
| B. Manejo de errores | 10/10 |
| C. Documentación para el usuario | 10/10 |
| D. Higiene en el desarrollo | 10/10 |
| E. Identificación (suave) | 10/10 |
| **Overall** | **50/50** |

> Evaluado con [`@mcptoolshop/shipcheck`](https://github.com/mcp-tool-shop-org/shipcheck)

## Licencia

MIT: consulte [LICENSE](LICENSE) para obtener más detalles.

---

Desarrollado por [MCP Tool Shop](https://mcp-tool-shop.github.io/)
