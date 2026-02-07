"""
Azure TTS Backend - Microsoft Azure Neural Text-to-Speech.

v2.4 Feature (P2): Enterprise-grade cloud TTS via Azure Cognitive Services.

Usage:
    engine = VoiceEngine(Config(backend="azure"))
    result = engine.speak("Hello!", voice="en-US-JennyNeural")

Features:
    - Neural TTS voices
    - SSML support
    - Multiple languages and locales
    - Custom Neural Voice support
    - Speaking styles and emotions

Requires:
    - AZURE_SPEECH_KEY and AZURE_SPEECH_REGION environment variables
    - azure-cognitiveservices-speech package: pip install voice-soundboard[azure]
"""

from __future__ import annotations

import os
import logging
from typing import Iterator

import numpy as np

from voice_soundboard.graph import ControlGraph
from voice_soundboard.engine.base import BaseTTSBackend

logger = logging.getLogger(__name__)


# Popular Azure Neural TTS voices
AZURE_VOICES = {
    # US English
    "jenny": "en-US-JennyNeural",
    "aria": "en-US-AriaNeural",
    "guy": "en-US-GuyNeural",
    "davis": "en-US-DavisNeural",
    "jane": "en-US-JaneNeural",
    "jason": "en-US-JasonNeural",
    "sara": "en-US-SaraNeural",
    "tony": "en-US-TonyNeural",
    "nancy": "en-US-NancyNeural",
    
    # UK English
    "sonia": "en-GB-SoniaNeural",
    "ryan": "en-GB-RyanNeural",
    "libby": "en-GB-LibbyNeural",
    
    # Other
    "natasha": "en-AU-NatashaNeural",
    "william": "en-AU-WilliamNeural",
}

# Speaking styles available for some voices
SPEAKING_STYLES = {
    "en-US-JennyNeural": [
        "assistant", "chat", "customerservice", "newscast",
        "angry", "cheerful", "sad", "excited", "friendly",
        "terrified", "shouting", "unfriendly", "whispering", "hopeful",
    ],
    "en-US-AriaNeural": [
        "chat", "customerservice", "narration-professional", 
        "newscast-casual", "newscast-formal", "cheerful", "empathetic",
    ],
    "en-US-GuyNeural": [
        "newscast", "angry", "cheerful", "sad", "excited",
        "friendly", "terrified", "shouting", "unfriendly", "whispering",
    ],
}


class AzureTTSBackend(BaseTTSBackend):
    """Azure Neural TTS backend using Azure Cognitive Services.
    
    Enterprise-grade cloud-based text-to-speech with neural voices.
    Requires AZURE_SPEECH_KEY and AZURE_SPEECH_REGION environment variables.
    
    Features:
        - Neural TTS with natural prosody
        - SSML support for fine control
        - Speaking styles and emotions
        - Custom Neural Voice support
        - Multiple languages and locales
        - Viseme/word timing support
    
    Limitations:
        - Requires API key and internet
        - Paid API (character-based pricing)
        - Some styles only available on specific voices
    """
    
    def __init__(
        self,
        *,
        speech_key: str | None = None,
        speech_region: str | None = None,
        voice: str = "en-US-JennyNeural",
        style: str | None = None,
        style_degree: float = 1.0,
        role: str | None = None,
        output_format: str = "Raw24Khz16BitMonoPcm",
    ):
        """Initialize Azure TTS backend.
        
        Args:
            speech_key: Azure Speech key (defaults to AZURE_SPEECH_KEY env var)
            speech_region: Azure region (defaults to AZURE_SPEECH_REGION env var)
            voice: Default voice name
            style: Speaking style (e.g., "cheerful", "sad")
            style_degree: Style intensity (0.01-2.0)
            role: Speaking role (for multi-role scenarios)
            output_format: Audio output format
        """
        self._speech_key = speech_key or os.environ.get("AZURE_SPEECH_KEY")
        self._speech_region = speech_region or os.environ.get("AZURE_SPEECH_REGION")
        
        if not self._speech_key or not self._speech_region:
            raise ValueError(
                "Azure Speech credentials required. Set AZURE_SPEECH_KEY and "
                "AZURE_SPEECH_REGION environment variables."
            )
        
        self._default_voice = voice
        self._style = style
        self._style_degree = style_degree
        self._role = role
        self._output_format = output_format
        self._sample_rate = 24000  # For Raw24Khz format
        
        # Lazy config and synthesizer
        self._speech_config = None
        self._synthesizer = None
    
    def _get_speech_config(self):
        """Lazy-load speech config."""
        if self._speech_config is None:
            try:
                import azure.cognitiveservices.speech as speechsdk
                
                self._speech_config = speechsdk.SpeechConfig(
                    subscription=self._speech_key,
                    region=self._speech_region,
                )
                self._speech_config.set_speech_synthesis_output_format(
                    getattr(
                        speechsdk.SpeechSynthesisOutputFormat,
                        self._output_format,
                        speechsdk.SpeechSynthesisOutputFormat.Raw24Khz16BitMonoPcm,
                    )
                )
            except ImportError:
                raise ImportError(
                    "azure-cognitiveservices-speech package required. Install with: "
                    "pip install voice-soundboard[azure]"
                )
        return self._speech_config
    
    def _get_synthesizer(self):
        """Lazy-load speech synthesizer."""
        if self._synthesizer is None:
            import azure.cognitiveservices.speech as speechsdk
            
            config = self._get_speech_config()
            self._synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=config,
                audio_config=None,  # We'll handle audio ourselves
            )
        return self._synthesizer
    
    @property
    def name(self) -> str:
        return "azure"
    
    @property
    def sample_rate(self) -> int:
        return self._sample_rate
    
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Synthesize audio from a ControlGraph."""
        synthesizer = self._get_synthesizer()
        
        # Build SSML from graph
        ssml = self._build_ssml(graph)
        
        if not ssml:
            return np.array([], dtype=np.float32)
        
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            # Synthesize
            result = synthesizer.speak_ssml_async(ssml).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                # Convert to numpy array
                audio_data = result.audio_data
                samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                return samples / 32768.0  # Normalize to [-1, 1]
            
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation = result.cancellation_details
                logger.error(f"Azure TTS canceled: {cancellation.reason}")
                if cancellation.error_details:
                    logger.error(f"Error details: {cancellation.error_details}")
                raise RuntimeError(f"Azure TTS failed: {cancellation.reason}")
            
            else:
                raise RuntimeError(f"Unexpected result: {result.reason}")
                
        except Exception as e:
            logger.error(f"Azure TTS synthesis failed: {e}")
            raise
    
    def synthesize_streaming(self, graph: ControlGraph) -> Iterator[np.ndarray]:
        """Stream synthesized audio chunks."""
        import azure.cognitiveservices.speech as speechsdk
        
        config = self._get_speech_config()
        
        # Create push audio stream for capturing output
        push_stream = speechsdk.audio.PushAudioOutputStream()
        audio_config = speechsdk.audio.AudioOutputConfig(stream=push_stream)
        
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=config,
            audio_config=audio_config,
        )
        
        ssml = self._build_ssml(graph)
        
        if not ssml:
            return
        
        # Collect chunks
        audio_buffer = bytearray()
        chunk_size = 4800  # 200ms at 24kHz
        
        def audio_callback(evt):
            nonlocal audio_buffer
            if evt.result.audio_data:
                audio_buffer.extend(evt.result.audio_data)
        
        synthesizer.synthesizing.connect(audio_callback)
        
        try:
            result = synthesizer.speak_ssml_async(ssml).get()
            
            # Yield remaining audio
            while len(audio_buffer) >= chunk_size * 2:
                chunk = bytes(audio_buffer[:chunk_size * 2])
                audio_buffer = audio_buffer[chunk_size * 2:]
                
                samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
                yield samples / 32768.0
            
            # Yield final chunk
            if audio_buffer:
                samples = np.frombuffer(bytes(audio_buffer), dtype=np.int16).astype(np.float32)
                yield samples / 32768.0
                
        except Exception as e:
            logger.error(f"Azure TTS streaming failed: {e}")
            raise
    
    def _build_ssml(self, graph: ControlGraph) -> str:
        """Build SSML from ControlGraph."""
        # Extract text
        text = " ".join(token.text for token in graph.tokens if token.text.strip())
        
        if not text:
            return ""
        
        # Resolve voice
        voice = self._resolve_voice(graph)
        
        # Get prosody parameters
        rate = self._calculate_rate(graph)
        pitch = self._calculate_pitch(graph)
        
        # Build SSML
        ssml_parts = [
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" ',
            'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">',
        ]
        
        # Voice element
        ssml_parts.append(f'<voice name="{voice}">')
        
        # Style wrapper if configured
        if self._style and voice in SPEAKING_STYLES:
            if self._style in SPEAKING_STYLES[voice]:
                ssml_parts.append(
                    f'<mstts:express-as style="{self._style}" '
                    f'styledegree="{self._style_degree}">'
                )
        
        # Prosody wrapper
        ssml_parts.append(f'<prosody rate="{rate}" pitch="{pitch}">')
        
        # Add text with breaks
        for token in graph.tokens:
            if token.text.strip():
                ssml_parts.append(self._escape_xml(token.text))
            
            # Add pauses
            if token.pause_before > 0:
                pause_ms = int(token.pause_before * 1000)
                ssml_parts.append(f'<break time="{pause_ms}ms"/>')
        
        # Close tags
        ssml_parts.append('</prosody>')
        
        if self._style and voice in SPEAKING_STYLES and self._style in SPEAKING_STYLES[voice]:
            ssml_parts.append('</mstts:express-as>')
        
        ssml_parts.append('</voice>')
        ssml_parts.append('</speak>')
        
        return ''.join(ssml_parts)
    
    def _resolve_voice(self, graph: ControlGraph) -> str:
        """Resolve voice from graph or default."""
        voice_id = graph.voice_id
        
        if voice_id:
            # Check if it's a short name
            if voice_id.lower() in AZURE_VOICES:
                return AZURE_VOICES[voice_id.lower()]
            # Assume it's a full voice name
            return voice_id
        
        # Use default
        if self._default_voice.lower() in AZURE_VOICES:
            return AZURE_VOICES[self._default_voice.lower()]
        return self._default_voice
    
    def _calculate_rate(self, graph: ControlGraph) -> str:
        """Calculate speaking rate from graph."""
        if not graph.tokens:
            return "0%"
        
        avg_speed = sum(t.speed_scale for t in graph.tokens) / len(graph.tokens)
        
        # Convert to percentage (1.0 = 0%, 1.5 = +50%, 0.5 = -50%)
        percentage = int((avg_speed - 1.0) * 100)
        
        if percentage >= 0:
            return f"+{percentage}%"
        return f"{percentage}%"
    
    def _calculate_pitch(self, graph: ControlGraph) -> str:
        """Calculate pitch from graph."""
        if not graph.tokens:
            return "0%"
        
        avg_pitch = sum(t.pitch_scale for t in graph.tokens) / len(graph.tokens)
        
        # Convert to percentage
        percentage = int((avg_pitch - 1.0) * 50)  # Pitch is more sensitive
        
        if percentage >= 0:
            return f"+{percentage}%"
        return f"{percentage}%"
    
    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters."""
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
    
    def list_voices(self, locale: str | None = None) -> list[dict]:
        """List available voices.
        
        Args:
            locale: Filter by locale (e.g., "en-US")
            
        Returns:
            List of voice info dicts
        """
        synthesizer = self._get_synthesizer()
        
        try:
            result = synthesizer.get_voices_async(locale or "").get()
            
            if result.reason == result.reason.VoicesListRetrieved:
                return [
                    {
                        "name": v.name,
                        "locale": v.locale,
                        "gender": v.gender.name,
                        "styles": v.style_list if hasattr(v, 'style_list') else [],
                    }
                    for v in result.voices
                ]
            else:
                logger.error(f"Failed to list voices: {result.reason}")
                return []
                
        except Exception as e:
            logger.error(f"Error listing voices: {e}")
            return []
    
    def set_style(self, style: str, degree: float = 1.0) -> None:
        """Set the speaking style.
        
        Args:
            style: Style name (e.g., "cheerful", "sad")
            degree: Style intensity (0.01-2.0)
        """
        self._style = style
        self._style_degree = max(0.01, min(2.0, degree))


# Check availability
try:
    import azure.cognitiveservices.speech as _azure_check
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
