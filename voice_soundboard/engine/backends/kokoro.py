"""
Kokoro Backend - High-quality neural TTS via ONNX.

Kokoro is an 82M parameter model that produces 24kHz audio.
This backend lowers ControlGraph to Kokoro's text+voice+speed format.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from voice_soundboard.engine.base import BaseTTSBackend
from voice_soundboard.graph import ControlGraph

if TYPE_CHECKING:
    from kokoro_onnx import Kokoro

logger = logging.getLogger(__name__)


class KokoroBackend(BaseTTSBackend):
    """Kokoro ONNX TTS backend.
    
    Requires optional dependency: pip install voice-soundboard[kokoro]
    
    Model files required in model_dir:
        - kokoro-v1.0.onnx
        - voices-v1.0.bin
    """
    
    def __init__(
        self,
        model_dir: Path | str | None = None,
        device: str = "auto",
    ):
        """Initialize Kokoro backend.
        
        Args:
            model_dir: Directory containing model files.
                       Defaults to VOICE_SOUNDBOARD_MODELS env var or ./models
            device: "cuda", "cpu", or "auto" (default)
        """
        self._model_dir = Path(model_dir) if model_dir else self._default_model_dir()
        self._device = device
        self._kokoro: Kokoro | None = None
        self._loaded = False
    
    @staticmethod
    def _default_model_dir() -> Path:
        env = os.environ.get("VOICE_SOUNDBOARD_MODELS")
        if env:
            return Path(env)
        return Path.cwd() / "models"
    
    @property
    def name(self) -> str:
        return "kokoro"
    
    @property
    def sample_rate(self) -> int:
        return 24000
    
    def _ensure_loaded(self) -> None:
        """Lazy load the model on first use."""
        if self._loaded:
            return
        
        try:
            from kokoro_onnx import Kokoro
        except ImportError:
            raise ImportError(
                "Kokoro backend requires kokoro-onnx. "
                "Install with: pip install voice-soundboard[kokoro]"
            )
        
        model_path = self._model_dir / "kokoro-v1.0.onnx"
        voices_path = self._model_dir / "voices-v1.0.bin"
        
        if not model_path.exists():
            raise FileNotFoundError(
                f"Kokoro model not found: {model_path}\n"
                f"Download from: https://github.com/thewh1teagle/kokoro-onnx/releases"
            )
        
        if not voices_path.exists():
            raise FileNotFoundError(
                f"Kokoro voices not found: {voices_path}\n"
                f"Download from: https://github.com/thewh1teagle/kokoro-onnx/releases"
            )
        
        logger.info("Loading Kokoro model from %s", self._model_dir)
        self._kokoro = Kokoro(str(model_path), str(voices_path))
        self._loaded = True
        logger.info("Kokoro model loaded")
    
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Lower ControlGraph to Kokoro format and synthesize.
        
        Kokoro lowering:
            - Concatenates token text
            - Uses speaker.value as voice ID
            - Applies global_speed
            - Per-token prosody is NOT supported (ignored)
        """
        self._ensure_loaded()
        
        # Lower graph to Kokoro's format
        text = self._lower_text(graph)
        voice = self._lower_voice(graph)
        speed = graph.global_speed
        
        # Clamp speed to valid range
        speed = max(0.5, min(2.0, speed))
        
        # Synthesize
        samples, _sr = self._kokoro.create(text, voice=voice, speed=speed)
        
        return np.array(samples, dtype=np.float32)
    
    def _lower_text(self, graph: ControlGraph) -> str:
        """Lower tokens to plain text for Kokoro."""
        parts = []
        for token in graph.tokens:
            parts.append(token.text)
            # Add pause markers (Kokoro uses ... for pauses)
            if token.pause_after > 0.2:
                parts.append("...")
            elif token.pause_after > 0.1:
                parts.append("..")
        return " ".join(parts)
    
    def _lower_voice(self, graph: ControlGraph) -> str:
        """Extract voice ID from speaker reference."""
        speaker = graph.speaker
        
        if speaker.type == "voice_id":
            return speaker.value
        elif speaker.type == "preset":
            # Presets should have been resolved by compiler
            # but fall back to the preset name as voice ID
            return speaker.value
        elif speaker.type == "embedding":
            # Kokoro doesn't support embeddings, use default
            logger.warning("Kokoro doesn't support voice embeddings, using default")
            return "af_bella"
        
        return "af_bella"
    
    def get_voices(self) -> list[str]:
        """Return available Kokoro voices."""
        self._ensure_loaded()
        return self._kokoro.get_voices()
    
    def supports_voice(self, voice_id: str) -> bool:
        """Check if voice is available."""
        try:
            return voice_id in self.get_voices()
        except Exception:
            return False


def is_available() -> bool:
    """Check if Kokoro backend is available."""
    try:
        from kokoro_onnx import Kokoro
        return True
    except ImportError:
        return False
