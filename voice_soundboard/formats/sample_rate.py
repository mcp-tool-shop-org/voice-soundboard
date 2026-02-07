"""
Sample rate conversion utilities.

Provides high-quality sample rate conversion for audio.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import numpy as np


class ResamplingQuality(Enum):
    """Quality level for resampling."""
    FAST = "fast"           # Linear interpolation
    MEDIUM = "medium"       # Cubic interpolation
    HIGH = "high"           # Windowed sinc
    BEST = "best"           # Polyphase filter


@dataclass
class SampleRateConverter:
    """
    Sample rate converter with configurable quality.
    
    Attributes:
        quality: Resampling quality level
        window_size: Window size for sinc interpolation
    """
    quality: ResamplingQuality = ResamplingQuality.HIGH
    window_size: int = 64
    
    def convert(
        self,
        audio: np.ndarray,
        from_rate: int,
        to_rate: int,
    ) -> np.ndarray:
        """
        Convert sample rate of audio.
        
        Args:
            audio: Input audio samples
            from_rate: Source sample rate
            to_rate: Target sample rate
            
        Returns:
            Resampled audio
        """
        if from_rate == to_rate:
            return audio.copy()
        
        if len(audio) == 0:
            return np.array([], dtype=audio.dtype)
        
        ratio = to_rate / from_rate
        new_length = int(len(audio) * ratio)
        
        if new_length == 0:
            return np.array([], dtype=audio.dtype)
        
        if self.quality == ResamplingQuality.FAST:
            return self._linear_resample(audio, new_length)
        elif self.quality == ResamplingQuality.MEDIUM:
            return self._cubic_resample(audio, new_length)
        elif self.quality == ResamplingQuality.HIGH:
            return self._sinc_resample(audio, from_rate, to_rate)
        else:  # BEST
            return self._polyphase_resample(audio, from_rate, to_rate)
    
    def _linear_resample(
        self,
        audio: np.ndarray,
        new_length: int,
    ) -> np.ndarray:
        """Linear interpolation resampling."""
        indices = np.linspace(0, len(audio) - 1, new_length)
        return np.interp(indices, np.arange(len(audio)), audio).astype(audio.dtype)
    
    def _cubic_resample(
        self,
        audio: np.ndarray,
        new_length: int,
    ) -> np.ndarray:
        """Cubic interpolation resampling."""
        audio_float = audio.astype(np.float64)
        
        # Indices for new samples
        indices = np.linspace(0, len(audio) - 1, new_length)
        
        result = np.zeros(new_length, dtype=np.float64)
        
        for i, idx in enumerate(indices):
            idx_int = int(idx)
            frac = idx - idx_int
            
            # Get 4 surrounding samples
            p0 = audio_float[max(0, idx_int - 1)]
            p1 = audio_float[idx_int]
            p2 = audio_float[min(len(audio) - 1, idx_int + 1)]
            p3 = audio_float[min(len(audio) - 1, idx_int + 2)]
            
            # Catmull-Rom cubic interpolation
            result[i] = (
                (-0.5 * p0 + 1.5 * p1 - 1.5 * p2 + 0.5 * p3) * frac**3 +
                (p0 - 2.5 * p1 + 2 * p2 - 0.5 * p3) * frac**2 +
                (-0.5 * p0 + 0.5 * p2) * frac +
                p1
            )
        
        return result.astype(audio.dtype)
    
    def _sinc_resample(
        self,
        audio: np.ndarray,
        from_rate: int,
        to_rate: int,
    ) -> np.ndarray:
        """Windowed sinc resampling."""
        audio_float = audio.astype(np.float64)
        
        ratio = to_rate / from_rate
        new_length = int(len(audio) * ratio)
        
        result = np.zeros(new_length, dtype=np.float64)
        half_window = self.window_size // 2
        
        for i in range(new_length):
            # Position in original signal
            pos = i / ratio
            
            # Sinc interpolation with Hann window
            sample = 0.0
            norm = 0.0
            
            start = max(0, int(pos) - half_window)
            end = min(len(audio), int(pos) + half_window + 1)
            
            for j in range(start, end):
                x = pos - j
                
                # Sinc function
                if x == 0:
                    sinc = 1.0
                else:
                    sinc = np.sin(np.pi * x) / (np.pi * x)
                
                # Hann window
                window_pos = (j - int(pos) + half_window) / self.window_size
                if 0 <= window_pos <= 1:
                    window = 0.5 * (1 - np.cos(2 * np.pi * window_pos))
                else:
                    window = 0.0
                
                weight = sinc * window
                sample += audio_float[j] * weight
                norm += weight
            
            if norm > 0:
                result[i] = sample / norm
        
        return result.astype(audio.dtype)
    
    def _polyphase_resample(
        self,
        audio: np.ndarray,
        from_rate: int,
        to_rate: int,
    ) -> np.ndarray:
        """
        Polyphase filter resampling.
        
        This is a simplified implementation. For production use,
        consider using scipy.signal.resample_poly.
        """
        # Find GCD to determine interpolation/decimation factors
        from math import gcd
        g = gcd(from_rate, to_rate)
        up = to_rate // g
        down = from_rate // g
        
        # Limit factor for efficiency
        max_factor = 16
        if up > max_factor or down > max_factor:
            # Fall back to sinc for extreme ratios
            return self._sinc_resample(audio, from_rate, to_rate)
        
        audio_float = audio.astype(np.float64)
        
        # Upsample by inserting zeros
        upsampled = np.zeros(len(audio_float) * up, dtype=np.float64)
        upsampled[::up] = audio_float
        
        # Design lowpass filter
        cutoff = min(1.0 / up, 1.0 / down) * 0.9
        filter_len = self.window_size * up
        
        # Create windowed sinc filter
        n = np.arange(-filter_len // 2, filter_len // 2 + 1)
        h = np.sinc(2 * cutoff * n) * np.hanning(len(n))
        h = h / np.sum(h) * up  # Normalize and scale
        
        # Convolve
        filtered = np.convolve(upsampled, h, mode='same')
        
        # Downsample
        result = filtered[::down]
        
        return result.astype(audio.dtype)


def convert_sample_rate(
    audio: np.ndarray,
    from_rate: int,
    to_rate: int,
    quality: ResamplingQuality = ResamplingQuality.HIGH,
) -> np.ndarray:
    """
    Convert sample rate of audio.
    
    Convenience function that creates a converter with specified quality.
    
    Args:
        audio: Input audio samples
        from_rate: Source sample rate
        to_rate: Target sample rate
        quality: Resampling quality level
        
    Returns:
        Resampled audio
        
    Example:
        # Upsample from 22050 to 48000 Hz
        audio_48k = convert_sample_rate(audio_22k, 22050, 48000)
        
        # Downsample with high quality
        audio_16k = convert_sample_rate(audio_44k, 44100, 16000, 
                                        quality=ResamplingQuality.BEST)
    """
    converter = SampleRateConverter(quality=quality)
    return converter.convert(audio, from_rate, to_rate)


# Common sample rates
SAMPLE_RATES = {
    "telephone": 8000,
    "voip": 16000,
    "standard": 22050,
    "cd": 44100,
    "professional": 48000,
    "high_res": 96000,
}


def get_common_rate(name: str) -> int:
    """
    Get a common sample rate by name.
    
    Args:
        name: Rate name (telephone, voip, standard, cd, professional, high_res)
        
    Returns:
        Sample rate in Hz
        
    Raises:
        ValueError: If name not recognized
    """
    if name not in SAMPLE_RATES:
        raise ValueError(f"Unknown sample rate: {name}. Available: {list(SAMPLE_RATES.keys())}")
    return SAMPLE_RATES[name]
