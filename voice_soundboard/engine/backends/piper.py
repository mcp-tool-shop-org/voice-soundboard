"""
Piper Backend - Fast, local neural TTS.

Piper is a lightweight neural TTS system using VITS.
Models are ONNX files with companion JSON config.
Output is 22050Hz by default.

This backend lowers ControlGraph to Piper's text+config format.
"""

from __future__ import annotations

import io
import logging
import os
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

import numpy as np

from voice_soundboard.engine.base import BaseTTSBackend
from voice_soundboard.graph import ControlGraph

if TYPE_CHECKING:
    from piper import PiperVoice

logger = logging.getLogger(__name__)


# Piper voice mappings (voice name -> model file pattern)
# Users can download voices with: python -m piper.download_voices <voice_name>
PIPER_VOICES = {
    # English US
    "en_US_lessac_medium": {"model": "en_US-lessac-medium", "quality": "medium"},
    "en_US_lessac_high": {"model": "en_US-lessac-high", "quality": "high"},
    "en_US_amy_medium": {"model": "en_US-amy-medium", "quality": "medium"},
    "en_US_danny_low": {"model": "en_US-danny-low", "quality": "low"},
    "en_US_kathleen_low": {"model": "en_US-kathleen-low", "quality": "low"},
    "en_US_kusal_medium": {"model": "en_US-kusal-medium", "quality": "medium"},
    "en_US_l2arctic_medium": {"model": "en_US-l2arctic-medium", "quality": "medium"},
    "en_US_libritts_high": {"model": "en_US-libritts-high", "quality": "high"},
    "en_US_ljspeech_high": {"model": "en_US-ljspeech-high", "quality": "high"},
    "en_US_ljspeech_medium": {"model": "en_US-ljspeech-medium", "quality": "medium"},
    "en_US_ryan_high": {"model": "en_US-ryan-high", "quality": "high"},
    "en_US_ryan_medium": {"model": "en_US-ryan-medium", "quality": "medium"},
    
    # English GB
    "en_GB_alan_medium": {"model": "en_GB-alan-medium", "quality": "medium"},
    "en_GB_alba_medium": {"model": "en_GB-alba-medium", "quality": "medium"},
    "en_GB_aru_medium": {"model": "en_GB-aru-medium", "quality": "medium"},
    "en_GB_jenny_dioco_medium": {"model": "en_GB-jenny_dioco-medium", "quality": "medium"},
    "en_GB_northern_english_male_medium": {"model": "en_GB-northern_english_male-medium", "quality": "medium"},
    "en_GB_semaine_medium": {"model": "en_GB-semaine-medium", "quality": "medium"},
    "en_GB_southern_english_female_low": {"model": "en_GB-southern_english_female-low", "quality": "low"},
    "en_GB_vctk_medium": {"model": "en_GB-vctk-medium", "quality": "medium"},
    
    # German
    "de_DE_thorsten_high": {"model": "de_DE-thorsten-high", "quality": "high"},
    "de_DE_thorsten_medium": {"model": "de_DE-thorsten-medium", "quality": "medium"},
    "de_DE_eva_k_medium": {"model": "de_DE-eva_k-medium", "quality": "medium"},
    
    # French
    "fr_FR_upmc_medium": {"model": "fr_FR-upmc-medium", "quality": "medium"},
    "fr_FR_siwis_medium": {"model": "fr_FR-siwis-medium", "quality": "medium"},
    
    # Spanish
    "es_ES_davefx_medium": {"model": "es_ES-davefx-medium", "quality": "medium"},
    "es_MX_ald_medium": {"model": "es_MX-ald-medium", "quality": "medium"},
}

# Compatibility shims: Kokoro voice IDs → Piper equivalents.
# These are BEST-EFFORT mappings, not guarantees of identical output.
# Treat as convenience for users migrating from Kokoro backend.
# Do not rely on these for production voice matching.
KOKORO_TO_PIPER = {
    "af_bella": "en_US_lessac_medium",      # Female US
    "af_jessica": "en_US_amy_medium",       # Female US alt
    "am_michael": "en_US_ryan_medium",      # Male US
    "bm_george": "en_GB_alan_medium",       # Male GB
    "bf_emma": "en_GB_alba_medium",         # Female GB
}


class PiperBackend(BaseTTSBackend):
    """Piper TTS backend.
    
    Requires optional dependency: pip install voice-soundboard[piper]
    
    Model files can be downloaded with:
        python -m piper.download_voices <voice_name>
    
    Models are stored in ~/.local/share/piper-voices/ by default.
    """
    
    def __init__(
        self,
        model_dir: Path | str | None = None,
        default_voice: str = "en_US_lessac_medium",
        use_cuda: bool = False,
    ):
        """Initialize Piper backend.
        
        Args:
            model_dir: Directory containing model files.
                       Defaults to ~/.local/share/piper-voices/ or
                       PIPER_VOICES_DIR env var.
            default_voice: Default Piper voice to use.
            use_cuda: Enable GPU acceleration (requires onnxruntime-gpu).
        """
        self._model_dir = Path(model_dir) if model_dir else self._default_model_dir()
        self._default_voice = default_voice
        self._use_cuda = use_cuda
        self._voices: dict[str, PiperVoice] = {}  # Cached loaded voices
    
    @staticmethod
    def _default_model_dir() -> Path:
        env = os.environ.get("PIPER_VOICES_DIR")
        if env:
            return Path(env)
        
        # Default piper voices location
        if os.name == "nt":  # Windows
            return Path.home() / "AppData" / "Local" / "piper-voices"
        else:  # Linux/Mac
            return Path.home() / ".local" / "share" / "piper-voices"
    
    @property
    def name(self) -> str:
        return "piper"
    
    @property
    def sample_rate(self) -> int:
        return 22050  # Piper default
    
    def _get_voice(self, voice_name: str) -> "PiperVoice":
        """Load or retrieve cached voice."""
        if voice_name in self._voices:
            return self._voices[voice_name]
        
        try:
            from piper import PiperVoice
        except ImportError:
            raise ImportError(
                "Piper backend requires piper-tts. "
                "Install with: pip install voice-soundboard[piper]"
            )
        
        # Resolve voice info
        voice_info = PIPER_VOICES.get(voice_name)
        if not voice_info:
            raise ValueError(
                f"Unknown Piper voice: {voice_name}. "
                f"Available: {list(PIPER_VOICES.keys())}"
            )
        
        # Find model file
        model_name = voice_info["model"]
        model_path = self._find_model(model_name)
        
        if not model_path:
            raise FileNotFoundError(
                f"Piper model not found: {model_name}\n"
                f"Download with: python -m piper.download_voices {model_name}\n"
                f"Searched in: {self._model_dir}"
            )
        
        logger.info("Loading Piper voice: %s from %s", voice_name, model_path)
        voice = PiperVoice.load(str(model_path), use_cuda=self._use_cuda)
        self._voices[voice_name] = voice
        
        return voice
    
    def _find_model(self, model_name: str) -> Path | None:
        """Find model file in model directory."""
        # Try direct path
        direct = self._model_dir / f"{model_name}.onnx"
        if direct.exists():
            return direct
        
        # Try in subdirectory (piper download structure)
        subdir = self._model_dir / model_name.replace("-", "_")
        if subdir.exists():
            onnx_files = list(subdir.glob("*.onnx"))
            if onnx_files:
                return onnx_files[0]
        
        # Try alternate naming
        alt = self._model_dir / model_name / f"{model_name}.onnx"
        if alt.exists():
            return alt
        
        return None
    
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Lower ControlGraph to Piper format and synthesize.
        
        Piper lowering:
            - Concatenates token text
            - Maps speaker to Piper voice
            - Applies global_speed via length_scale
            - Per-token prosody affects length_scale (limited support)
            
        Paralinguistic events are lowered to silence (lossy).
        Piper doesn't support native paralinguistics.
        """
        # Lower graph to Piper's format
        text = self._lower_text(graph)
        voice_name = self._lower_voice(graph)
        length_scale = self._lower_speed(graph)
        
        voice = self._get_voice(voice_name)
        
        # Synthesize to WAV in memory
        wav_buffer = io.BytesIO()
        
        try:
            from piper import SynthesisConfig
            
            config = SynthesisConfig(
                length_scale=length_scale,
                normalize_audio=True,
            )
            
            with wave.open(wav_buffer, "wb") as wav_file:
                voice.synthesize_wav(text, wav_file, syn_config=config)
        except ImportError:
            # Older piper versions without SynthesisConfig
            with wave.open(wav_buffer, "wb") as wav_file:
                voice.synthesize_wav(text, wav_file)
        
        # Read back as numpy array
        wav_buffer.seek(0)
        with wave.open(wav_buffer, "rb") as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Lower events to silence (lossy lowering)
        audio = self._lower_events(graph, audio)
        
        return audio
    
    def synthesize_stream(self, graph: ControlGraph, chunk_size: int = 4096) -> Iterator[np.ndarray]:
        """Streaming synthesis using Piper's native streaming."""
        text = self._lower_text(graph)
        voice_name = self._lower_voice(graph)
        voice = self._get_voice(voice_name)
        
        try:
            for chunk in voice.synthesize(text):
                # Convert int16 bytes to float32 array
                audio = np.frombuffer(
                    chunk.audio_int16_bytes, dtype=np.int16
                ).astype(np.float32) / 32768.0
                yield audio
        except AttributeError:
            # Fallback if streaming not available
            audio = self.synthesize(graph)
            for i in range(0, len(audio), chunk_size):
                yield audio[i:i + chunk_size]
    
    def _lower_text(self, graph: ControlGraph) -> str:
        """Lower tokens to plain text for Piper."""
        parts = []
        for token in graph.tokens:
            parts.append(token.text)
        return " ".join(parts)
    
    def _lower_voice(self, graph: ControlGraph) -> str:
        """Map speaker reference to Piper voice name."""
        speaker = graph.speaker
        
        if speaker.type == "voice_id":
            voice_id = speaker.value
            
            # Check if it's already a Piper voice
            if voice_id in PIPER_VOICES:
                return voice_id
            
            # Try mapping from Kokoro voice
            if voice_id in KOKORO_TO_PIPER:
                return KOKORO_TO_PIPER[voice_id]
            
            # Try fuzzy match
            for piper_voice in PIPER_VOICES:
                if voice_id in piper_voice or piper_voice in voice_id:
                    return piper_voice
        
        # Default
        return self._default_voice
    
    def _lower_speed(self, graph: ControlGraph) -> float:
        """Convert semantic speed to Piper's length_scale.
        
        IMPORTANT: This is a backend-specific inversion.
        
        Semantic speed (ControlGraph):
            speed=2.0 means "speak twice as fast"
            speed=0.5 means "speak half as fast"
            
        Piper's length_scale:
            length_scale=2.0 means "take twice as long" (slower)
            length_scale=0.5 means "take half as long" (faster)
            
        Therefore: length_scale = 1.0 / speed
        
        This inversion is CORRECT and INTENTIONAL. Do not "fix" it.
        Do not normalize this at the compiler level - speed is semantic,
        length_scale is backend math.
        """
        speed = graph.global_speed
        
        # Also factor in per-token duration scales (average)
        if graph.tokens:
            avg_duration = sum(t.duration_scale for t in graph.tokens) / len(graph.tokens)
            speed = speed / avg_duration  # duration_scale > 1 means longer = slower
        
        # Clamp and invert
        speed = max(0.25, min(4.0, speed))
        length_scale = 1.0 / speed
        
        return length_scale
    
    def _lower_events(self, graph: ControlGraph, audio: np.ndarray) -> np.ndarray:
        """Lower paralinguistic events to silence (lossy).
        
        Piper doesn't support native paralinguistics.
        Events are converted to silence padding at the appropriate timeline position.
        This is lossy but keeps timing intact.
        
        Future: Could mix in prerecorded audio at adapter level.
        """
        if not graph.events:
            return audio
        
        # For simplicity, prepend event durations as silence
        # (More sophisticated implementation would splice at exact times)
        total_event_time = sum(e.duration for e in graph.events)
        silence_samples = int(total_event_time * self.sample_rate)
        
        if silence_samples > 0:
            silence = np.zeros(silence_samples, dtype=np.float32)
            audio = np.concatenate([silence, audio])
        
        return audio
    
    def get_voices(self) -> list[str]:
        """Return available Piper voice names."""
        return list(PIPER_VOICES.keys())
    
    def supports_voice(self, voice_id: str) -> bool:
        """Check if voice is supported."""
        if voice_id in PIPER_VOICES:
            return True
        if voice_id in KOKORO_TO_PIPER:
            return True
        return False


def is_available() -> bool:
    """Check if Piper backend is available."""
    try:
        from piper import PiperVoice
        return True
    except ImportError:
        return False
