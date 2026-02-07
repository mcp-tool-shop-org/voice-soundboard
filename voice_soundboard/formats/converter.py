"""
Audio format conversion utilities.

Provides format detection and conversion between audio formats.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, BinaryIO, Union
from pathlib import Path
import struct
import io
import numpy as np


class AudioFormat(Enum):
    """Supported audio formats."""
    WAV = "wav"
    PCM = "pcm"      # Raw PCM data
    MP3 = "mp3"
    OPUS = "opus"
    OGG = "ogg"
    FLAC = "flac"
    
    @classmethod
    def from_extension(cls, ext: str) -> "AudioFormat":
        """Get format from file extension."""
        ext = ext.lower().lstrip(".")
        mapping = {
            "wav": cls.WAV,
            "wave": cls.WAV,
            "pcm": cls.PCM,
            "raw": cls.PCM,
            "mp3": cls.MP3,
            "opus": cls.OPUS,
            "ogg": cls.OGG,
            "flac": cls.FLAC,
        }
        if ext not in mapping:
            raise ValueError(f"Unknown format: {ext}")
        return mapping[ext]


@dataclass
class AudioMetadata:
    """
    Metadata for audio data.
    
    Attributes:
        sample_rate: Sample rate in Hz
        channels: Number of channels
        bit_depth: Bits per sample
        format: Audio format
        duration_seconds: Duration in seconds
        extra: Format-specific metadata
    """
    sample_rate: int = 22050
    channels: int = 1
    bit_depth: int = 16
    format: AudioFormat = AudioFormat.WAV
    duration_seconds: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)


def detect_format(data: bytes) -> AudioFormat:
    """
    Detect audio format from file header.
    
    Args:
        data: First bytes of audio file (at least 12 bytes)
        
    Returns:
        Detected AudioFormat
        
    Raises:
        ValueError: If format cannot be detected
    """
    if len(data) < 4:
        raise ValueError("Insufficient data to detect format")
    
    # WAV: "RIFF....WAVE"
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WAVE":
        return AudioFormat.WAV
    
    # MP3: ID3 tag or sync word
    if data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return AudioFormat.MP3
    
    # OGG: "OggS"
    if data[:4] == b"OggS":
        # Check if it's Opus inside OGG
        if len(data) >= 36 and b"OpusHead" in data[:36]:
            return AudioFormat.OPUS
        return AudioFormat.OGG
    
    # FLAC: "fLaC"
    if data[:4] == b"fLaC":
        return AudioFormat.FLAC
    
    # If no header detected, might be raw PCM
    return AudioFormat.PCM


@dataclass
class FormatConverter:
    """
    Audio format converter.
    
    Converts between different audio formats.
    Note: MP3 and OPUS encoding require external libraries.
    
    Attributes:
        default_sample_rate: Default sample rate for output
        default_bit_depth: Default bit depth for output
    """
    default_sample_rate: int = 22050
    default_bit_depth: int = 16
    
    def convert(
        self,
        audio: np.ndarray,
        from_format: AudioFormat,
        to_format: AudioFormat,
        sample_rate: int = 22050,
    ) -> bytes:
        """
        Convert audio between formats.
        
        Args:
            audio: Audio samples
            from_format: Source format (for metadata)
            to_format: Target format
            sample_rate: Sample rate
            
        Returns:
            Encoded audio bytes
        """
        if to_format == AudioFormat.WAV:
            return self._to_wav(audio, sample_rate)
        elif to_format == AudioFormat.PCM:
            return self._to_pcm(audio)
        elif to_format == AudioFormat.MP3:
            return self._to_mp3(audio, sample_rate)
        elif to_format == AudioFormat.OPUS:
            return self._to_opus(audio, sample_rate)
        elif to_format == AudioFormat.OGG:
            return self._to_ogg(audio, sample_rate)
        elif to_format == AudioFormat.FLAC:
            return self._to_flac(audio, sample_rate)
        else:
            raise ValueError(f"Unsupported output format: {to_format}")
    
    def decode(
        self,
        data: bytes,
        format_hint: Optional[AudioFormat] = None,
    ) -> tuple[np.ndarray, AudioMetadata]:
        """
        Decode audio bytes to samples.
        
        Args:
            data: Audio file bytes
            format_hint: Optional format hint
            
        Returns:
            Tuple of (audio samples, metadata)
        """
        format = format_hint or detect_format(data)
        
        if format == AudioFormat.WAV:
            return self._from_wav(data)
        elif format == AudioFormat.PCM:
            return self._from_pcm(data)
        else:
            raise ValueError(
                f"Decoding {format.value} requires external libraries. "
                "Install pydub or soundfile for full format support."
            )
    
    def _to_wav(self, audio: np.ndarray, sample_rate: int) -> bytes:
        """Encode to WAV format."""
        # Convert to int16 if needed
        if audio.dtype == np.float32 or audio.dtype == np.float64:
            audio = (audio * 32767).astype(np.int16)
        elif audio.dtype != np.int16:
            audio = audio.astype(np.int16)
        
        buffer = io.BytesIO()
        
        # RIFF header
        channels = 1
        bit_depth = 16
        byte_rate = sample_rate * channels * bit_depth // 8
        block_align = channels * bit_depth // 8
        data_size = len(audio) * block_align
        file_size = 36 + data_size
        
        # RIFF chunk
        buffer.write(b"RIFF")
        buffer.write(struct.pack("<I", file_size))
        buffer.write(b"WAVE")
        
        # fmt chunk
        buffer.write(b"fmt ")
        buffer.write(struct.pack("<I", 16))  # Chunk size
        buffer.write(struct.pack("<H", 1))   # PCM format
        buffer.write(struct.pack("<H", channels))
        buffer.write(struct.pack("<I", sample_rate))
        buffer.write(struct.pack("<I", byte_rate))
        buffer.write(struct.pack("<H", block_align))
        buffer.write(struct.pack("<H", bit_depth))
        
        # data chunk
        buffer.write(b"data")
        buffer.write(struct.pack("<I", data_size))
        buffer.write(audio.tobytes())
        
        return buffer.getvalue()
    
    def _to_pcm(self, audio: np.ndarray) -> bytes:
        """Encode to raw PCM."""
        if audio.dtype == np.float32 or audio.dtype == np.float64:
            audio = (audio * 32767).astype(np.int16)
        elif audio.dtype != np.int16:
            audio = audio.astype(np.int16)
        return audio.tobytes()
    
    def _to_mp3(self, audio: np.ndarray, sample_rate: int) -> bytes:
        """Encode to MP3."""
        raise NotImplementedError(
            "MP3 encoding requires external libraries. "
            "Install pydub with ffmpeg or use a different format."
        )
    
    def _to_opus(self, audio: np.ndarray, sample_rate: int) -> bytes:
        """Encode to Opus."""
        raise NotImplementedError(
            "Opus encoding requires external libraries. "
            "Install pyogg or opuslib for Opus support."
        )
    
    def _to_ogg(self, audio: np.ndarray, sample_rate: int) -> bytes:
        """Encode to Ogg Vorbis."""
        raise NotImplementedError(
            "OGG encoding requires external libraries. "
            "Install pydub or soundfile for OGG support."
        )
    
    def _to_flac(self, audio: np.ndarray, sample_rate: int) -> bytes:
        """Encode to FLAC."""
        raise NotImplementedError(
            "FLAC encoding requires external libraries. "
            "Install soundfile or pyflac for FLAC support."
        )
    
    def _from_wav(self, data: bytes) -> tuple[np.ndarray, AudioMetadata]:
        """Decode WAV file."""
        buffer = io.BytesIO(data)
        
        # Read RIFF header
        riff = buffer.read(4)
        if riff != b"RIFF":
            raise ValueError("Invalid WAV: missing RIFF")
        
        file_size = struct.unpack("<I", buffer.read(4))[0]
        wave = buffer.read(4)
        if wave != b"WAVE":
            raise ValueError("Invalid WAV: missing WAVE")
        
        # Find fmt and data chunks
        sample_rate = 22050
        channels = 1
        bit_depth = 16
        audio_data = None
        
        while buffer.tell() < len(data):
            chunk_id = buffer.read(4)
            if len(chunk_id) < 4:
                break
            
            chunk_size = struct.unpack("<I", buffer.read(4))[0]
            
            if chunk_id == b"fmt ":
                fmt_data = buffer.read(chunk_size)
                audio_format = struct.unpack("<H", fmt_data[0:2])[0]
                channels = struct.unpack("<H", fmt_data[2:4])[0]
                sample_rate = struct.unpack("<I", fmt_data[4:8])[0]
                # byte_rate = struct.unpack("<I", fmt_data[8:12])[0]
                # block_align = struct.unpack("<H", fmt_data[12:14])[0]
                bit_depth = struct.unpack("<H", fmt_data[14:16])[0]
            elif chunk_id == b"data":
                audio_data = buffer.read(chunk_size)
            else:
                buffer.seek(chunk_size, 1)  # Skip unknown chunk
        
        if audio_data is None:
            raise ValueError("Invalid WAV: missing data chunk")
        
        # Convert to numpy
        if bit_depth == 16:
            audio = np.frombuffer(audio_data, dtype=np.int16)
        elif bit_depth == 32:
            audio = np.frombuffer(audio_data, dtype=np.int32)
        elif bit_depth == 8:
            audio = np.frombuffer(audio_data, dtype=np.uint8).astype(np.int16)
            audio = (audio - 128) * 256
        else:
            raise ValueError(f"Unsupported bit depth: {bit_depth}")
        
        # Handle multi-channel
        if channels > 1:
            audio = audio.reshape(-1, channels)
            # Convert to mono
            audio = np.mean(audio, axis=1).astype(np.int16)
        
        metadata = AudioMetadata(
            sample_rate=sample_rate,
            channels=channels,
            bit_depth=bit_depth,
            format=AudioFormat.WAV,
            duration_seconds=len(audio) / sample_rate,
        )
        
        return audio, metadata
    
    def _from_pcm(
        self,
        data: bytes,
        sample_rate: int = 22050,
        bit_depth: int = 16,
    ) -> tuple[np.ndarray, AudioMetadata]:
        """Decode raw PCM."""
        if bit_depth == 16:
            audio = np.frombuffer(data, dtype=np.int16)
        elif bit_depth == 32:
            audio = np.frombuffer(data, dtype=np.int32)
        elif bit_depth == 8:
            audio = np.frombuffer(data, dtype=np.uint8).astype(np.int16)
            audio = (audio - 128) * 256
        else:
            raise ValueError(f"Unsupported bit depth: {bit_depth}")
        
        metadata = AudioMetadata(
            sample_rate=sample_rate,
            channels=1,
            bit_depth=bit_depth,
            format=AudioFormat.PCM,
            duration_seconds=len(audio) / sample_rate,
        )
        
        return audio, metadata


def convert_format(
    audio: np.ndarray,
    to_format: AudioFormat,
    sample_rate: int = 22050,
) -> bytes:
    """
    Convert audio to specified format.
    
    Convenience function for quick format conversion.
    
    Args:
        audio: Audio samples
        to_format: Target format
        sample_rate: Sample rate
        
    Returns:
        Encoded audio bytes
        
    Example:
        wav_bytes = convert_format(audio, AudioFormat.WAV)
        
        with open("output.wav", "wb") as f:
            f.write(wav_bytes)
    """
    converter = FormatConverter()
    return converter.convert(audio, AudioFormat.PCM, to_format, sample_rate)


def save_audio(
    audio: np.ndarray,
    path: Union[str, Path],
    sample_rate: int = 22050,
    format: Optional[AudioFormat] = None,
) -> None:
    """
    Save audio to file.
    
    Args:
        audio: Audio samples
        path: Output file path
        sample_rate: Sample rate
        format: Audio format (detected from extension if None)
    """
    path = Path(path)
    
    if format is None:
        format = AudioFormat.from_extension(path.suffix)
    
    data = convert_format(audio, format, sample_rate)
    
    with open(path, "wb") as f:
        f.write(data)


def load_audio(
    path: Union[str, Path],
) -> tuple[np.ndarray, AudioMetadata]:
    """
    Load audio from file.
    
    Args:
        path: Audio file path
        
    Returns:
        Tuple of (audio samples, metadata)
    """
    path = Path(path)
    
    with open(path, "rb") as f:
        data = f.read()
    
    converter = FormatConverter()
    return converter.decode(data)
