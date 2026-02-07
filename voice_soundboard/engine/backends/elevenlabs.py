"""
ElevenLabs TTS Backend - Premium cloud-based text-to-speech.

v2.4 Feature (P2): High-quality cloud TTS via ElevenLabs API.

Usage:
    engine = VoiceEngine(Config(backend="elevenlabs"))
    result = engine.speak("Hello!", voice="rachel")

Features:
    - Ultra-realistic voices
    - Voice cloning support
    - Emotion and style control
    - Multiple languages

Requires:
    - ELEVENLABS_API_KEY environment variable
    - elevenlabs package: pip install voice-soundboard[elevenlabs]
"""

from __future__ import annotations

import os
import logging
from typing import Iterator

import numpy as np

from voice_soundboard.graph import ControlGraph
from voice_soundboard.engine.base import BaseTTSBackend

logger = logging.getLogger(__name__)


# ElevenLabs voice IDs (common voices)
ELEVENLABS_VOICES = {
    "rachel": "21m00Tcm4TlvDq8ikWAM",      # American female
    "domi": "AZnzlk1XvdvUeBnXmlld",         # American female
    "bella": "EXAVITQu4vr4xnSDxMaL",        # American female
    "antoni": "ErXwobaYiN019PkySvjV",       # American male
    "elli": "MF3mGyEYCl7XYWbV9V6O",         # American female
    "josh": "TxGEqnHWrfWFTfGW9XjX",         # American male
    "arnold": "VR6AewLTigWG4xSOukaG",       # American male
    "adam": "pNInz6obpgDQGcFmaJgB",         # American male
    "sam": "yoZ06aMxZJJ28mfd3POQ",          # American male
    "nicole": "piTKgcLEGmPE4e6mEKli",       # American female
    "glinda": "z9fAnlkpzviPz146aGWa",       # American female
}

# Voice style/emotion mapping
VOICE_STYLES = {
    "neutral": {"stability": 0.5, "similarity_boost": 0.75},
    "expressive": {"stability": 0.3, "similarity_boost": 0.85},
    "stable": {"stability": 0.8, "similarity_boost": 0.6},
    "emotional": {"stability": 0.25, "similarity_boost": 0.9},
}


class ElevenLabsBackend(BaseTTSBackend):
    """ElevenLabs TTS backend using the ElevenLabs API.
    
    Premium cloud-based text-to-speech with ultra-realistic voices.
    Requires ELEVENLABS_API_KEY environment variable.
    
    Features:
        - Ultra-realistic voice synthesis
        - Voice cloning support
        - Emotion/style control via stability and similarity
        - Multiple languages
        - Streaming support
    
    Limitations:
        - Requires API key and internet
        - Paid API (character-based pricing)
        - No local processing
    """
    
    def __init__(
        self,
        *,
        api_key: str | None = None,
        voice: str = "rachel",
        model: str = "eleven_multilingual_v2",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        style: float = 0.0,
        use_speaker_boost: bool = True,
    ):
        """Initialize ElevenLabs TTS backend.
        
        Args:
            api_key: ElevenLabs API key (defaults to ELEVENLABS_API_KEY env var)
            voice: Default voice name or ID
            model: Model to use (eleven_multilingual_v2, eleven_turbo_v2)
            stability: Voice stability (0-1, lower = more expressive)
            similarity_boost: Voice clarity/similarity (0-1)
            style: Style exaggeration (0-1)
            use_speaker_boost: Apply speaker boost
        """
        self._api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self._api_key:
            raise ValueError(
                "ElevenLabs API key required. Set ELEVENLABS_API_KEY environment "
                "variable or pass api_key parameter."
            )
        
        self._default_voice = voice
        self._model = model
        self._stability = stability
        self._similarity_boost = similarity_boost
        self._style = style
        self._use_speaker_boost = use_speaker_boost
        self._sample_rate = 24000  # Default sample rate
        
        # Lazy client
        self._client = None
    
    def _get_client(self):
        """Lazy-load ElevenLabs client."""
        if self._client is None:
            try:
                from elevenlabs.client import ElevenLabs
                self._client = ElevenLabs(api_key=self._api_key)
            except ImportError:
                raise ImportError(
                    "elevenlabs package required. Install with: "
                    "pip install voice-soundboard[elevenlabs]"
                )
        return self._client
    
    @property
    def name(self) -> str:
        return "elevenlabs"
    
    @property
    def sample_rate(self) -> int:
        return self._sample_rate
    
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Synthesize audio from a ControlGraph."""
        client = self._get_client()
        
        # Extract text from tokens
        text = " ".join(token.text for token in graph.tokens if token.text.strip())
        
        if not text:
            return np.array([], dtype=np.float32)
        
        # Resolve voice
        voice_id = self._resolve_voice(graph)
        
        # Get voice settings based on prosody
        stability, similarity = self._calculate_settings(graph)
        
        try:
            from elevenlabs import VoiceSettings
            
            # Generate audio
            audio_generator = client.generate(
                text=text,
                voice=voice_id,
                model=self._model,
                voice_settings=VoiceSettings(
                    stability=stability,
                    similarity_boost=similarity,
                    style=self._style,
                    use_speaker_boost=self._use_speaker_boost,
                ),
            )
            
            # Collect audio bytes
            audio_bytes = b"".join(audio_generator)
            
            # Convert MP3 to PCM
            return self._decode_to_pcm(audio_bytes)
            
        except Exception as e:
            logger.error(f"ElevenLabs synthesis failed: {e}")
            raise
    
    def synthesize_streaming(self, graph: ControlGraph) -> Iterator[np.ndarray]:
        """Stream synthesized audio chunks."""
        client = self._get_client()
        
        text = " ".join(token.text for token in graph.tokens if token.text.strip())
        
        if not text:
            return
        
        voice_id = self._resolve_voice(graph)
        stability, similarity = self._calculate_settings(graph)
        
        try:
            from elevenlabs import VoiceSettings
            
            # Stream audio
            audio_stream = client.generate(
                text=text,
                voice=voice_id,
                model=self._model,
                voice_settings=VoiceSettings(
                    stability=stability,
                    similarity_boost=similarity,
                    style=self._style,
                    use_speaker_boost=self._use_speaker_boost,
                ),
                stream=True,
            )
            
            for chunk in audio_stream:
                if chunk:
                    yield self._decode_to_pcm(chunk)
                    
        except Exception as e:
            logger.error(f"ElevenLabs streaming failed: {e}")
            raise
    
    def _resolve_voice(self, graph: ControlGraph) -> str:
        """Resolve voice ID from graph or default."""
        # Check if voice_id is set in graph
        voice_id = graph.voice_id
        
        if voice_id:
            # Check if it's a known voice name
            if voice_id.lower() in ELEVENLABS_VOICES:
                return ELEVENLABS_VOICES[voice_id.lower()]
            # Assume it's a direct voice ID
            return voice_id
        
        # Use default
        if self._default_voice.lower() in ELEVENLABS_VOICES:
            return ELEVENLABS_VOICES[self._default_voice.lower()]
        return self._default_voice
    
    def _calculate_settings(self, graph: ControlGraph) -> tuple[float, float]:
        """Calculate stability and similarity from graph prosody."""
        stability = self._stability
        similarity = self._similarity_boost
        
        # Adjust based on prosody parameters
        if graph.tokens:
            # Lower stability for more expressive/emotional speech
            avg_pitch = sum(t.pitch_scale for t in graph.tokens) / len(graph.tokens)
            avg_energy = sum(t.energy_scale for t in graph.tokens) / len(graph.tokens)
            
            # Higher pitch variance = more expressive = lower stability
            pitch_variance = abs(avg_pitch - 1.0)
            stability = max(0.1, self._stability - pitch_variance * 0.3)
            
            # Higher energy = more clarity = higher similarity
            if avg_energy > 1.0:
                similarity = min(1.0, self._similarity_boost + 0.1)
        
        return stability, similarity
    
    def _decode_to_pcm(self, audio_bytes: bytes) -> np.ndarray:
        """Decode audio bytes (MP3) to PCM float32."""
        try:
            # Try pydub for MP3 decoding
            from pydub import AudioSegment
            import io
            
            audio = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
            audio = audio.set_frame_rate(self._sample_rate)
            audio = audio.set_channels(1)
            
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / 32768.0  # Normalize to [-1, 1]
            
            return samples
            
        except ImportError:
            # Fallback: try to decode as raw PCM
            logger.warning("pydub not available, attempting raw decode")
            samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            return samples / 32768.0
    
    def list_voices(self) -> list[dict]:
        """List available voices."""
        client = self._get_client()
        
        try:
            voices = client.voices.get_all()
            return [
                {
                    "id": v.voice_id,
                    "name": v.name,
                    "category": v.category,
                    "labels": v.labels,
                }
                for v in voices.voices
            ]
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []
    
    def clone_voice(
        self,
        name: str,
        audio_files: list[str | bytes],
        description: str = "",
    ) -> str:
        """Clone a voice from audio samples.
        
        Args:
            name: Name for the cloned voice
            audio_files: List of audio file paths or bytes
            description: Voice description
            
        Returns:
            New voice ID
        """
        client = self._get_client()
        
        # Prepare files
        files = []
        for i, audio in enumerate(audio_files):
            if isinstance(audio, str):
                with open(audio, 'rb') as f:
                    files.append((f"sample_{i}.mp3", f.read()))
            else:
                files.append((f"sample_{i}.mp3", audio))
        
        try:
            voice = client.clone(
                name=name,
                description=description,
                files=[f[1] for f in files],
            )
            return voice.voice_id
        except Exception as e:
            logger.error(f"Voice cloning failed: {e}")
            raise


# Check availability
try:
    from elevenlabs import ElevenLabs as _ElevenLabsCheck
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
