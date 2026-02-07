"""
Coqui TTS Backend - Open source text-to-speech.

v2.1 Feature (P2): High-quality open source TTS.

Usage:
    engine = VoiceEngine(Config(backend="coqui"))
    result = engine.speak("Hello!")

Models:
    - VITS: Fast, good quality
    - YourTTS: Voice cloning capable
    - XTTS: Multilingual, best quality

Requires:
    pip install voice-soundboard[coqui]
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

import numpy as np

from voice_soundboard.graph import ControlGraph
from voice_soundboard.engine.base import BaseTTSBackend

logger = logging.getLogger(__name__)


# Default model configurations
COQUI_MODELS = {
    "vits": {
        "name": "tts_models/en/ljspeech/vits",
        "sample_rate": 22050,
        "description": "Fast, good quality English TTS",
    },
    "vits-neon": {
        "name": "tts_models/en/ljspeech/vits--neon",
        "sample_rate": 22050,
        "description": "VITS with NEON optimizations",
    },
    "tacotron2-ddc": {
        "name": "tts_models/en/ljspeech/tacotron2-DDC",
        "sample_rate": 22050,
        "description": "Tacotron2 with DDC",
    },
    "yourtts": {
        "name": "tts_models/multilingual/multi-dataset/your_tts",
        "sample_rate": 16000,
        "description": "Voice cloning capable multilingual",
    },
    "xtts": {
        "name": "tts_models/multilingual/multi-dataset/xtts_v2",
        "sample_rate": 22050,
        "description": "Best quality, multilingual, voice cloning",
    },
}


class CoquiTTSBackend(BaseTTSBackend):
    """Coqui TTS backend using the TTS library.
    
    Open source text-to-speech with multiple model options.
    
    Features:
        - Multiple model choices (VITS, YourTTS, XTTS)
        - Voice cloning support (model-dependent)
        - Multilingual (model-dependent)
        - Local processing
    
    Models:
        - vits: Fast, good quality
        - yourtts: Voice cloning capable
        - xtts: Best quality, multilingual
    """
    
    def __init__(
        self,
        *,
        model: str = "vits",
        model_path: Path | str | None = None,
        gpu: bool = False,
    ):
        """Initialize Coqui TTS backend.
        
        Args:
            model: Model name or key (see COQUI_MODELS)
            model_path: Custom model path (overrides model name)
            gpu: Use GPU acceleration
        """
        self._model_key = model
        self._model_path = model_path
        self._gpu = gpu
        
        # Get model config
        if model in COQUI_MODELS:
            self._model_config = COQUI_MODELS[model]
            self._model_name = self._model_config["name"]
            self._sample_rate = self._model_config["sample_rate"]
        else:
            # Assume it's a full model name
            self._model_name = model
            self._sample_rate = 22050  # Default
            self._model_config = None
        
        # Lazy-load the TTS model
        self._tts = None
    
    def _get_tts(self):
        """Lazy-load TTS model."""
        if self._tts is None:
            try:
                from TTS.api import TTS
                
                logger.info(f"Loading Coqui TTS model: {self._model_name}")
                
                if self._model_path:
                    self._tts = TTS(model_path=str(self._model_path), gpu=self._gpu)
                else:
                    self._tts = TTS(model_name=self._model_name, gpu=self._gpu)
                
                # Update sample rate from loaded model
                if hasattr(self._tts, 'synthesizer') and self._tts.synthesizer:
                    self._sample_rate = self._tts.synthesizer.output_sample_rate
                
                logger.info(f"Coqui TTS loaded, sample_rate={self._sample_rate}")
                
            except ImportError:
                raise ImportError(
                    "TTS package required. Install with: "
                    "pip install voice-soundboard[coqui]"
                )
        
        return self._tts
    
    @property
    def name(self) -> str:
        return f"coqui-{self._model_key}"
    
    @property
    def sample_rate(self) -> int:
        return self._sample_rate
    
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Synthesize audio from a ControlGraph."""
        tts = self._get_tts()
        
        # Extract text from tokens
        text = " ".join(token.text for token in graph.tokens if token.text.strip())
        
        if not text:
            return np.array([], dtype=np.float32)
        
        logger.debug(f"Coqui TTS: synthesizing {len(text)} chars")
        
        try:
            # Check if voice cloning is supported and requested
            speaker_wav = None
            if graph.speaker.type == "embedding":
                # For embedding-based cloning, we'd need the original wav
                # This is a limitation - we log a warning
                logger.warning(
                    "Coqui backend doesn't support embeddings directly. "
                    "Use SpeakerDB with wav reference for voice cloning."
                )
            
            # Synthesize
            # TTS.tts() returns a list of floats
            audio_list = tts.tts(
                text=text,
                speaker_wav=speaker_wav,
                language=self._detect_language(text),
            )
            
            # Convert to numpy array
            audio = np.array(audio_list, dtype=np.float32)
            
            # Apply speed/prosody
            audio = self._apply_prosody(audio, graph)
            
            return audio
            
        except Exception as e:
            logger.error(f"Coqui TTS failed: {e}")
            raise
    
    def synthesize_with_reference(
        self,
        graph: ControlGraph,
        reference_wav: Path | str,
    ) -> np.ndarray:
        """Synthesize with voice cloning from reference audio.
        
        Args:
            graph: The control graph
            reference_wav: Path to reference audio for voice cloning
        
        Returns:
            Synthesized audio
        """
        tts = self._get_tts()
        
        text = " ".join(token.text for token in graph.tokens if token.text.strip())
        if not text:
            return np.array([], dtype=np.float32)
        
        try:
            audio_list = tts.tts(
                text=text,
                speaker_wav=str(reference_wav),
                language=self._detect_language(text),
            )
            
            audio = np.array(audio_list, dtype=np.float32)
            audio = self._apply_prosody(audio, graph)
            
            return audio
            
        except Exception as e:
            logger.error(f"Coqui TTS with reference failed: {e}")
            raise
    
    def synthesize_stream(
        self,
        graph: ControlGraph,
        chunk_size: int = 4096,
    ) -> Iterator[np.ndarray]:
        """Chunked synthesis (not true streaming).
        
        Coqui TTS doesn't support true streaming, so we synthesize
        fully and chunk the output.
        """
        audio = self.synthesize(graph)
        for i in range(0, len(audio), chunk_size):
            yield audio[i:i + chunk_size]
    
    def _detect_language(self, text: str) -> str | None:
        """Detect language for multilingual models."""
        # Simple heuristic - could be improved with langdetect
        if self._model_key in ("yourtts", "xtts"):
            # These models need language specification
            # Default to English
            return "en"
        return None
    
    def _apply_prosody(self, audio: np.ndarray, graph: ControlGraph) -> np.ndarray:
        """Apply prosody modifications."""
        # Speed adjustment via resampling
        if graph.global_speed != 1.0:
            target_length = int(len(audio) / graph.global_speed)
            if target_length > 0:
                # Simple linear interpolation for speed change
                x_original = np.linspace(0, 1, len(audio))
                x_target = np.linspace(0, 1, target_length)
                audio = np.interp(x_target, x_original, audio)
        
        # Energy scaling
        if graph.tokens:
            avg_energy = sum(t.energy_scale for t in graph.tokens) / len(graph.tokens)
            if avg_energy != 1.0:
                audio = audio * avg_energy
                audio = np.clip(audio, -1.0, 1.0)
        
        return audio.astype(np.float32)
    
    def get_voices(self) -> list[str]:
        """Get available model speakers."""
        tts = self._get_tts()
        
        if hasattr(tts, 'speakers') and tts.speakers:
            return tts.speakers
        
        # Return model key as the "voice"
        return [self._model_key]
    
    def get_languages(self) -> list[str]:
        """Get available languages for multilingual models."""
        tts = self._get_tts()
        
        if hasattr(tts, 'languages') and tts.languages:
            return tts.languages
        
        return ["en"]


def create_coqui_backend(**kwargs) -> CoquiTTSBackend:
    """Factory function for Coqui backend."""
    return CoquiTTSBackend(**kwargs)
