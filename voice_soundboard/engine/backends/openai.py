"""
OpenAI TTS Backend - Cloud-based text-to-speech.

v2.1 Feature (P2): High-quality cloud TTS via OpenAI API.

Usage:
    engine = VoiceEngine(Config(backend="openai"))
    result = engine.speak("Hello!", voice="alloy")

Voices:
    - alloy: Neutral, balanced
    - echo: Slightly deeper
    - fable: Expressive, British accent
    - onyx: Deep, authoritative
    - nova: Warm, friendly
    - shimmer: Clear, energetic

Requires:
    - OPENAI_API_KEY environment variable
    - openai package: pip install voice-soundboard[openai]
"""

from __future__ import annotations

import os
import logging
from typing import Iterator

import numpy as np

from voice_soundboard.graph import ControlGraph
from voice_soundboard.engine.base import BaseTTSBackend

logger = logging.getLogger(__name__)


# OpenAI TTS voices
OPENAI_VOICES = {
    "alloy": "Neutral, balanced tone",
    "echo": "Slightly deeper voice",
    "fable": "Expressive, British accent",
    "onyx": "Deep, authoritative",
    "nova": "Warm, friendly",
    "shimmer": "Clear, energetic",
}

# Default voice mapping from voice IDs to OpenAI voices
VOICE_MAPPING = {
    # Female voices
    "af_bella": "nova",
    "af_sarah": "shimmer",
    "af_nicole": "alloy",
    # Male voices
    "am_adam": "onyx",
    "am_michael": "echo",
    # British
    "bf_emma": "fable",
    "bm_george": "fable",
    # Default
    "default": "nova",
}


class OpenAITTSBackend(BaseTTSBackend):
    """OpenAI TTS backend using the OpenAI API.
    
    High-quality cloud-based text-to-speech.
    Requires OPENAI_API_KEY environment variable.
    
    Features:
        - HD quality option (tts-1-hd)
        - Multiple voices
        - Speed control
        - Simple integration
    
    Limitations:
        - Requires API key and internet
        - Paid API (usage-based pricing)
        - No local processing
        - Limited prosody control
    """
    
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "tts-1",
        voice: str = "nova",
        response_format: str = "pcm",
    ):
        """Initialize OpenAI TTS backend.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use ("tts-1" or "tts-1-hd")
            voice: Default voice
            response_format: Audio format ("pcm", "mp3", "opus", "aac", "flac")
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self._model = model
        self._default_voice = voice
        self._response_format = response_format
        self._sample_rate = 24000  # OpenAI uses 24kHz for PCM
        
        # Lazy import openai
        self._client = None
    
    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self._api_key)
            except ImportError:
                raise ImportError(
                    "openai package required. Install with: "
                    "pip install voice-soundboard[openai]"
                )
        return self._client
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def sample_rate(self) -> int:
        return self._sample_rate
    
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Synthesize audio from a ControlGraph.
        
        Note: OpenAI API has limited prosody control.
        pitch_scale and energy_scale are applied post-synthesis.
        """
        client = self._get_client()
        
        # Extract text from tokens
        text = " ".join(token.text for token in graph.tokens if token.text.strip())
        
        if not text:
            return np.array([], dtype=np.float32)
        
        # Resolve voice
        voice = self._resolve_voice(graph)
        
        # Calculate speed from graph
        speed = graph.global_speed
        # Clamp to OpenAI's range
        speed = max(0.25, min(4.0, speed))
        
        logger.debug(f"OpenAI TTS: {len(text)} chars, voice={voice}, speed={speed}")
        
        try:
            response = client.audio.speech.create(
                model=self._model,
                voice=voice,
                input=text,
                response_format=self._response_format,
                speed=speed,
            )
            
            # Convert response to numpy array
            if self._response_format == "pcm":
                # PCM is 16-bit signed integers at 24kHz
                audio_bytes = response.content
                audio = np.frombuffer(audio_bytes, dtype=np.int16)
                # Convert to float32 in [-1, 1]
                audio = audio.astype(np.float32) / 32768.0
            else:
                # For other formats, we'd need to decode
                # For now, only PCM is fully supported
                raise NotImplementedError(
                    f"Response format {self._response_format} not fully supported. "
                    "Use response_format='pcm'."
                )
            
            # Apply prosody modifiers (best effort)
            audio = self._apply_prosody(audio, graph)
            
            return audio
            
        except Exception as e:
            logger.error(f"OpenAI TTS failed: {e}")
            raise
    
    def synthesize_stream(
        self,
        graph: ControlGraph,
        chunk_size: int = 4096,
    ) -> Iterator[np.ndarray]:
        """Streaming synthesis using OpenAI's streaming endpoint."""
        client = self._get_client()
        
        text = " ".join(token.text for token in graph.tokens if token.text.strip())
        if not text:
            return
        
        voice = self._resolve_voice(graph)
        speed = max(0.25, min(4.0, graph.global_speed))
        
        try:
            # Use streaming response
            with client.audio.speech.with_streaming_response.create(
                model=self._model,
                voice=voice,
                input=text,
                response_format="pcm",
                speed=speed,
            ) as response:
                buffer = b""
                # 16-bit samples = 2 bytes per sample
                bytes_per_chunk = chunk_size * 2
                
                for chunk in response.iter_bytes():
                    buffer += chunk
                    
                    while len(buffer) >= bytes_per_chunk:
                        chunk_bytes = buffer[:bytes_per_chunk]
                        buffer = buffer[bytes_per_chunk:]
                        
                        audio = np.frombuffer(chunk_bytes, dtype=np.int16)
                        audio = audio.astype(np.float32) / 32768.0
                        yield audio
                
                # Yield remaining
                if buffer:
                    audio = np.frombuffer(buffer, dtype=np.int16)
                    audio = audio.astype(np.float32) / 32768.0
                    yield audio
                    
        except Exception as e:
            logger.error(f"OpenAI streaming TTS failed: {e}")
            raise
    
    def _resolve_voice(self, graph: ControlGraph) -> str:
        """Resolve voice ID to OpenAI voice name."""
        if graph.speaker.type == "voice_id":
            voice_id = graph.speaker.value
            if voice_id in OPENAI_VOICES:
                return voice_id
            return VOICE_MAPPING.get(voice_id, self._default_voice)
        return self._default_voice
    
    def _apply_prosody(self, audio: np.ndarray, graph: ControlGraph) -> np.ndarray:
        """Apply prosody modifications to synthesized audio.
        
        Note: This is best-effort since OpenAI doesn't expose
        fine-grained prosody control.
        """
        # Apply energy scaling (simple gain)
        if graph.tokens:
            avg_energy = sum(t.energy_scale for t in graph.tokens) / len(graph.tokens)
            if avg_energy != 1.0:
                audio = audio * avg_energy
                # Clip to prevent clipping
                audio = np.clip(audio, -1.0, 1.0)
        
        # Pitch shifting would require DSP (deferred to v3)
        
        return audio
    
    def get_voices(self) -> list[str]:
        """Get available OpenAI voices."""
        return list(OPENAI_VOICES.keys())


def create_openai_backend(**kwargs) -> OpenAITTSBackend:
    """Factory function for OpenAI backend."""
    return OpenAITTSBackend(**kwargs)
