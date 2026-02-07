"""
Embedding Extractor - Extract speaker embeddings from audio.

Provides a standardized interface for extracting speaker embeddings
from reference audio files. Multiple backends can be used.

Usage:
    from voice_soundboard.cloning import extract_embedding
    
    # Simple usage
    embedding = extract_embedding("reference.wav")
    
    # With specific backend
    extractor = EmbeddingExtractor(backend="resemblyzer")
    embedding = extractor.extract("reference.wav")
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingFormat(str, Enum):
    """Supported embedding formats."""
    # Standard 256-dim speaker embedding
    RESEMBLYZER = "resemblyzer"
    # Coqui TTS speaker encoder
    COQUI = "coqui"
    # OpenVoice embedding
    OPENVOICE = "openvoice"
    # Raw mel spectrogram features
    MEL = "mel"


@dataclass
class EmbeddingResult:
    """Result of embedding extraction."""
    embedding: list[float]
    format: EmbeddingFormat
    source_file: str
    source_hash: str
    duration_seconds: float
    sample_rate: int
    
    def to_dict(self) -> dict:
        return {
            "embedding": self.embedding,
            "format": self.format.value,
            "source_file": self.source_file,
            "source_hash": self.source_hash,
            "duration_seconds": self.duration_seconds,
            "sample_rate": self.sample_rate,
        }


class EmbeddingExtractor:
    """Extracts speaker embeddings from audio files.
    
    Supports multiple embedding types:
    - resemblyzer: General speaker embeddings
    - coqui: Coqui TTS speaker encoder
    - mel: Raw mel features
    
    Example:
        extractor = EmbeddingExtractor(backend="resemblyzer")
        embedding = extractor.extract("reference.wav")
    """
    
    def __init__(
        self,
        backend: str = "resemblyzer",
        model_path: Path | str | None = None,
    ):
        """Initialize extractor.
        
        Args:
            backend: Backend to use ("resemblyzer", "coqui", "mel")
            model_path: Optional path to pretrained model
        """
        self._backend = backend
        self._model_path = model_path
        self._model = None
    
    def extract(
        self,
        audio_path: Path | str,
        *,
        max_duration: float = 30.0,
    ) -> EmbeddingResult:
        """Extract speaker embedding from audio file.
        
        Args:
            audio_path: Path to audio file (wav, mp3, etc.)
            max_duration: Maximum duration to process (seconds)
        
        Returns:
            EmbeddingResult with embedding and metadata
        
        Raises:
            FileNotFoundError: If audio file doesn't exist
            ValueError: If audio is too short or invalid
        """
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")
        
        # Load audio
        audio, sr = self._load_audio(path, max_duration)
        
        # Calculate source hash for caching
        source_hash = self._calculate_hash(path)
        
        # Extract embedding based on backend
        if self._backend == "resemblyzer":
            embedding = self._extract_resemblyzer(audio, sr)
            fmt = EmbeddingFormat.RESEMBLYZER
        elif self._backend == "coqui":
            embedding = self._extract_coqui(audio, sr)
            fmt = EmbeddingFormat.COQUI
        elif self._backend == "mel":
            embedding = self._extract_mel(audio, sr)
            fmt = EmbeddingFormat.MEL
        else:
            raise ValueError(f"Unknown backend: {self._backend}")
        
        return EmbeddingResult(
            embedding=embedding.tolist(),
            format=fmt,
            source_file=str(path.name),
            source_hash=source_hash,
            duration_seconds=len(audio) / sr,
            sample_rate=sr,
        )
    
    def _load_audio(
        self,
        path: Path,
        max_duration: float,
    ) -> tuple[np.ndarray, int]:
        """Load and preprocess audio."""
        import soundfile as sf
        
        # Read audio
        audio, sr = sf.read(str(path))
        
        # Convert to mono if stereo
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        
        # Trim to max duration
        max_samples = int(max_duration * sr)
        if len(audio) > max_samples:
            audio = audio[:max_samples]
        
        # Validate
        if len(audio) < sr:  # Less than 1 second
            raise ValueError(
                f"Audio too short ({len(audio)/sr:.1f}s). "
                "Need at least 1 second for embedding."
            )
        
        return audio.astype(np.float32), sr
    
    def _calculate_hash(self, path: Path) -> str:
        """Calculate file hash for caching."""
        hasher = hashlib.sha256()
        hasher.update(path.read_bytes())
        return hasher.hexdigest()[:16]
    
    def _extract_resemblyzer(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Extract embedding using resemblyzer."""
        try:
            from resemblyzer import VoiceEncoder, preprocess_wav
            
            # Get or create encoder
            if self._model is None:
                self._model = VoiceEncoder()
            
            # Preprocess
            wav = preprocess_wav(audio, source_sr=sr)
            
            # Extract embedding
            embedding = self._model.embed_utterance(wav)
            
            return embedding
            
        except ImportError:
            logger.warning(
                "resemblyzer not installed. Using fallback mel embedding. "
                "Install with: pip install resemblyzer"
            )
            return self._extract_mel(audio, sr)
    
    def _extract_coqui(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Extract embedding using Coqui speaker encoder."""
        try:
            from TTS.utils.audio import AudioProcessor
            from TTS.encoder.utils.generic_utils import setup_encoder_model
            
            # This would require a trained encoder model
            # For now, fall back to mel
            logger.warning("Coqui encoder requires trained model. Using mel fallback.")
            return self._extract_mel(audio, sr)
            
        except ImportError:
            logger.warning("Coqui TTS not installed. Using mel fallback.")
            return self._extract_mel(audio, sr)
    
    def _extract_mel(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Extract mel spectrogram features as embedding.
        
        This is a simple fallback that creates a fixed-size
        embedding from mel spectrogram statistics.
        """
        # Simple mel-like features without librosa
        # Compute FFT-based features
        n_fft = 2048
        hop_length = 512
        n_mels = 80
        
        # Pad audio
        if len(audio) < n_fft:
            audio = np.pad(audio, (0, n_fft - len(audio)))
        
        # Compute spectrogram via STFT
        n_frames = 1 + (len(audio) - n_fft) // hop_length
        spectrogram = np.zeros((n_fft // 2 + 1, n_frames))
        
        for i in range(n_frames):
            start = i * hop_length
            frame = audio[start:start + n_fft]
            if len(frame) < n_fft:
                frame = np.pad(frame, (0, n_fft - len(frame)))
            windowed = frame * np.hanning(n_fft)
            fft = np.fft.rfft(windowed)
            spectrogram[:, i] = np.abs(fft)
        
        # Convert to mel scale (simplified)
        mel_matrix = self._mel_filterbank(sr, n_fft, n_mels)
        mel_spec = np.dot(mel_matrix, spectrogram ** 2)
        mel_spec = np.log(mel_spec + 1e-9)
        
        # Create embedding from statistics
        embedding = np.concatenate([
            mel_spec.mean(axis=1),  # Mean per band
            mel_spec.std(axis=1),   # Std per band
            mel_spec.max(axis=1) - mel_spec.min(axis=1),  # Range
        ])
        
        # Normalize
        embedding = (embedding - embedding.mean()) / (embedding.std() + 1e-9)
        
        return embedding.astype(np.float32)
    
    def _mel_filterbank(self, sr: int, n_fft: int, n_mels: int) -> np.ndarray:
        """Create mel filterbank matrix."""
        # Hz to mel conversion
        def hz_to_mel(hz):
            return 2595 * np.log10(1 + hz / 700)
        
        def mel_to_hz(mel):
            return 700 * (10 ** (mel / 2595) - 1)
        
        # Frequency bins
        n_bins = n_fft // 2 + 1
        fmax = sr / 2
        
        # Mel points
        mel_min = hz_to_mel(0)
        mel_max = hz_to_mel(fmax)
        mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
        hz_points = mel_to_hz(mel_points)
        
        # Bin indices
        bin_indices = np.floor((n_fft + 1) * hz_points / sr).astype(int)
        
        # Create filterbank
        filterbank = np.zeros((n_mels, n_bins))
        for i in range(n_mels):
            left = bin_indices[i]
            center = bin_indices[i + 1]
            right = bin_indices[i + 2]
            
            for j in range(left, center):
                if center != left:
                    filterbank[i, j] = (j - left) / (center - left)
            for j in range(center, right):
                if right != center:
                    filterbank[i, j] = (right - j) / (right - center)
        
        return filterbank


def extract_embedding(
    audio_path: Path | str,
    *,
    backend: str = "resemblyzer",
    max_duration: float = 30.0,
) -> list[float]:
    """Extract speaker embedding from audio file.
    
    Convenience function for simple embedding extraction.
    
    Args:
        audio_path: Path to audio file
        backend: Embedding backend ("resemblyzer", "coqui", "mel")
        max_duration: Maximum duration to process
    
    Returns:
        List of floats representing the speaker embedding
    
    Example:
        embedding = extract_embedding("reference.wav")
        speaker = SpeakerRef.from_embedding(embedding)
    """
    extractor = EmbeddingExtractor(backend=backend)
    result = extractor.extract(audio_path, max_duration=max_duration)
    return result.embedding
