<p align="center">
  <a href="README.ja.md">日本語</a> | <a href="README.zh.md">中文</a> | <a href="README.es.md">Español</a> | <a href="README.fr.md">Français</a> | <a href="README.md">English</a> | <a href="README.it.md">Italiano</a> | <a href="README.pt-BR.md">Português (BR)</a>
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

**वॉइस साउंडबोर्ड** एक टेक्स्ट-टू-स्पीच इंजन है जो उन डेवलपर्स के लिए बनाया गया है जिन्हें केवल `.mp3` फ़ाइल की आवश्यकता नहीं होती है।

ज्यादातर टेक्स्ट-टू-स्पीच लाइब्रेरी एक विकल्प पेश करती हैं: सरल एपीआई जो सब कुछ छिपा देते हैं, या जटिल, निम्न-स्तरीय उपकरण जो ऑडियो इंजीनियरिंग के ज्ञान की आवश्यकता होती है। वॉइस साउंडबोर्ड आपको दोनों का सर्वश्रेष्ठ प्रदान करता है।

*   **सरल, उच्च-स्तरीय एपीआई**: बस `engine.speak("Hello")` को कॉल करें और ऑडियो प्राप्त करें।
*   **शक्तिशाली आंतरिक संरचना**: अंदर, हम एक कंपाइलर/ग्राफ/इंजन आर्किटेक्चर का उपयोग करते हैं जो *क्या* कहा जा रहा है (इरादा, भावना) को *कैसे* प्रस्तुत किया जा रहा है (बैकएंड, ऑडियो प्रारूप) से अलग करता है।
*   **शून्य-लागत एब्स्ट्रैक्शन**: भावनाओं, शैलियों और एसएसएमएल को एक नियंत्रण ग्राफ में संकलित किया जाता है, इसलिए रनटाइम इंजन तेज और हल्का रहता है।

## शुरुआत कैसे करें

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

## आर्किटेक्चर

```
compile_request("text", emotion="happy")
        |
    ControlGraph (pure data)
        |
    engine.synthesize(graph)
        |
    PCM audio (numpy array)
```

**कंपाइलर** इरादे (टेक्स्ट + भावना + शैली) को एक `ControlGraph` में बदलता है।

**इंजन** ग्राफ को ऑडियो में बदलता है। यह भावनाओं या शैलियों के बारे में कुछ भी नहीं जानता है।

यह अलगाव का मतलब है:
- रनटाइम पर विशेषताएं "मुफ़्त" हैं (पहले से ही ग्राफ में शामिल हैं)
- इंजन छोटा, तेज़ और परीक्षण योग्य है
- बैकएंड को फीचर लॉजिक को छुए बिना बदला जा सकता है

## उपयोग

### बुनियादी

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

### उन्नत: सीधे ग्राफ में हेरफेर

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

### स्ट्रीमिंग

स्ट्रीमिंग दो स्तरों पर काम करता है:

1. **ग्राफ स्ट्रीमिंग**: `compile_stream()` वाक्य सीमाओं का पता चलने पर कंट्रोल ग्राफ उत्पन्न करता है।
2. **ऑडियो स्ट्रीमिंग**: `StreamingSynthesizer` वास्तविक समय में प्लेबैक के लिए ऑडियो को छोटे-छोटे टुकड़ों में विभाजित करता है।

**ध्यान दें**: यह वाक्य-स्तर पर स्ट्रीमिंग है, शब्द-दर-शब्द वृद्धिशील संश्लेषण नहीं। कंपाइलर ग्राफ उत्पन्न करने से पहले वाक्य सीमाओं की प्रतीक्षा करता है। वास्तविक वृद्धिशील संश्लेषण (रोलबैक के साथ अनुमानित निष्पादन) वास्तुशिल्प रूप से समर्थित है लेकिन अभी तक लागू नहीं किया गया है।

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

## कमांड लाइन इंटरफेस (CLI)

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

## बैकएंड

| बैकएंड | गुणवत्ता | गति | सैंपल दर | इंस्टॉल करें |
|---------|---------|-------|-------------|---------|
| कोकोरो | उत्कृष्ट | तेज़ (GPU) | 24000 Hz | `pip install voice-soundboard[kokoro]` |
| पाइपर | बहुत अच्छा | तेज़ (CPU) | 22050 Hz | `pip install voice-soundboard[piper]` |
| मॉक | लागू नहीं | तत्काल | 24000 Hz | (बिल्ट-इन, परीक्षण के लिए) |

### कोकोरो सेटअप

```bash
pip install voice-soundboard[kokoro]

# Download models
mkdir models && cd models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### पाइपर सेटअप

```bash
pip install voice-soundboard[piper]

# Download a voice (example: en_US_lessac_medium)
python -m piper.download_voices en_US-lessac-medium
```

पाइपर विशेषताएं:
- **30+ आवाजें** कई भाषाओं में (अंग्रेजी, जर्मन, फ्रेंच, स्पेनिश)
- **केवल CPU** - GPU की आवश्यकता नहीं है
- **गति नियंत्रण** `length_scale` के माध्यम से (उल्टा: 0.8 = तेज़, 1.2 = धीमा)
- **सैंपल दर**: 22050 Hz (बैकएंड-विशिष्ट)

कोकोरो से आवाज का मैपिंग:
```python
# These Kokoro voices have Piper equivalents
engine = VoiceEngine(Config(backend="piper"))
result = engine.speak("Hello!", voice="af_bella")  # Uses en_US_lessac_medium
```

## पैकेज संरचना

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

**मुख्य नियम**: `engine/` कभी भी `compiler/` से आयात नहीं करता है।

## आर्किटेक्चर नियम

ये नियम परीक्षणों में लागू किए जाते हैं और इनका उल्लंघन कभी नहीं किया जाना चाहिए:

1. **इंजन अलगाव**: `engine/` कभी भी `compiler/` से आयात नहीं करता है। इंजन भावनाओं, शैलियों या प्रीसेट के बारे में कुछ नहीं जानता है - केवल कंट्रोल ग्राफ।

2. **वॉयस क्लोनिंग सीमा**: कच्चा ऑडियो कभी भी इंजन तक नहीं पहुंचता है। कंपाइलर स्पीकर एम्बेडिंग निकालता है; इंजन केवल `SpeakerRef` के माध्यम से एम्बेडिंग वेक्टर प्राप्त करता है।

3. **ग्राफ स्थिरता**: `GRAPH_VERSION` (वर्तमान में 1) कंट्रोल ग्राफ में ब्रेकिंग परिवर्तनों पर बढ़ाया जाता है। बैकएंड संगतता के लिए इसकी जांच कर सकते हैं।

```python
from voice_soundboard.graph import GRAPH_VERSION, ControlGraph
assert GRAPH_VERSION == 1
```

## v1 से माइग्रेशन

सार्वजनिक एपीआई अपरिवर्तित है:

```python
# This works in both v1 and v2
from voice_soundboard import VoiceEngine
engine = VoiceEngine()
result = engine.speak("Hello!", voice="af_bella", emotion="happy")
```

यदि आपने आंतरिक तत्वों को आयात किया है, तो माइग्रेशन मैपिंग देखें:

| v1 | v2 |
|----|-----|
| `engine.py` | `adapters/api.py` |
| `emotions.py` | `compiler/emotion.py` |
| `interpreter.py` | `compiler/style.py` |
| `engines/kokoro.py` | `engine/backends/kokoro.py` |

## सुरक्षा और डेटा दायरा

- **डेटा तक पहुंच:** यह टेक्स्ट इनपुट को टेक्स्ट-टू-स्पीच (TTS) संश्लेषण के लिए पढ़ता है। यह ऑडियो को कॉन्फ़िगर किए गए बैकएंड (कोकोरो, पाइपर, या मॉक) के माध्यम से संसाधित करता है। यह पीसीएम ऑडियो को numpy एरे या WAV फ़ाइलों के रूप में वापस करता है।
- **डेटा तक नहीं पहुंच:** डिफ़ॉल्ट रूप से, कोई भी नेटवर्क कनेक्शन नहीं होता (बैकएंड स्थानीय होते हैं)। कोई टेलीमेट्री, एनालिटिक्स या ट्रैकिंग नहीं होती। उपयोगकर्ता डेटा केवल अस्थायी ऑडियो बफ़र में ही संग्रहीत होता है।
- **आवश्यक अनुमतियाँ:** टीटीएस मॉडल फ़ाइलों तक पढ़ने की पहुंच। ऑडियो आउटपुट के लिए वैकल्पिक रूप से लिखने की पहुंच।

सुरक्षा संबंधी कमजोरियों की रिपोर्टिंग के लिए [SECURITY.md](SECURITY.md) देखें।

## स्कोरकार्ड

| श्रेणी | स्कोर |
|----------|-------|
| A. सुरक्षा | 10/10 |
| B. त्रुटि प्रबंधन | 10/10 |
| C. ऑपरेटर दस्तावेज़ | 10/10 |
| D. शिपिंग स्वच्छता | 10/10 |
| E. पहचान (सॉफ्ट) | 10/10 |
| **Overall** | **50/50** |

> [`@mcptoolshop/shipcheck`](https://github.com/mcp-tool-shop-org/shipcheck) के साथ मूल्यांकन किया गया।

## लाइसेंस

एमआईटी -- विवरण के लिए [LICENSE](LICENSE) देखें।

---

[MCP Tool Shop](https://mcp-tool-shop.github.io/) द्वारा निर्मित।
