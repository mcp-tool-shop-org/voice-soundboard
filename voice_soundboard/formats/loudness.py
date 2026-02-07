"""
Loudness normalization utilities.

Provides LUFS-based loudness measurement and normalization.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np


@dataclass
class LoudnessStats:
    """
    Loudness measurement statistics.
    
    Attributes:
        integrated: Integrated loudness in LUFS
        peak: True peak level in dBFS
        range: Loudness range in LU
        short_term_max: Maximum short-term loudness
        momentary_max: Maximum momentary loudness
    """
    integrated: float
    peak: float
    range: float = 0.0
    short_term_max: float = -70.0
    momentary_max: float = -70.0
    
    def meets_standard(
        self,
        target_lufs: float = -16.0,
        tolerance: float = 1.0,
        max_peak: float = -1.0,
    ) -> bool:
        """
        Check if loudness meets broadcast standard.
        
        Args:
            target_lufs: Target integrated loudness
            tolerance: Allowed deviation in LU
            max_peak: Maximum allowed true peak
            
        Returns:
            True if within standards
        """
        lufs_ok = abs(self.integrated - target_lufs) <= tolerance
        peak_ok = self.peak <= max_peak
        return lufs_ok and peak_ok


def measure_loudness(
    audio: np.ndarray,
    sample_rate: int = 22050,
) -> LoudnessStats:
    """
    Measure loudness of audio according to ITU-R BS.1770.
    
    This is a simplified implementation. For broadcast-compliant
    measurements, use a certified loudness meter.
    
    Args:
        audio: Audio samples (mono or stereo)
        sample_rate: Sample rate in Hz
        
    Returns:
        LoudnessStats with measured values
    """
    if len(audio) == 0:
        return LoudnessStats(
            integrated=-70.0,
            peak=-70.0,
        )
    
    # Convert to float
    audio_float = audio.astype(np.float64)
    if audio.dtype == np.int16:
        audio_float = audio_float / 32768.0
    elif audio.dtype == np.int32:
        audio_float = audio_float / 2147483648.0
    
    # Ensure mono for simplicity
    if len(audio_float.shape) > 1:
        audio_float = np.mean(audio_float, axis=1)
    
    # True peak measurement
    true_peak = np.max(np.abs(audio_float))
    peak_db = 20 * np.log10(true_peak + 1e-10)
    
    # K-weighting filter (simplified)
    # Full implementation requires pre-filter and RLB filter
    audio_weighted = _apply_k_weighting(audio_float, sample_rate)
    
    # Gated loudness measurement
    integrated, short_term_max, momentary_max = _gated_loudness(
        audio_weighted, sample_rate
    )
    
    # Loudness range (simplified)
    loudness_range = _measure_loudness_range(audio_weighted, sample_rate)
    
    return LoudnessStats(
        integrated=integrated,
        peak=peak_db,
        range=loudness_range,
        short_term_max=short_term_max,
        momentary_max=momentary_max,
    )


def _apply_k_weighting(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """
    Apply K-weighting filter for loudness measurement.
    
    Simplified implementation using a high-shelf filter approximation.
    """
    # This is a simplified approximation
    # Full K-weighting requires:
    # 1. Pre-filter (high shelf +4dB at 1681 Hz)
    # 2. RLB filter (highpass at 38 Hz)
    
    # Simple high-pass to approximate RLB
    from math import pi
    
    # Highpass at ~38 Hz
    fc = 38.0
    rc = 1.0 / (2.0 * pi * fc)
    dt = 1.0 / sample_rate
    alpha = rc / (rc + dt)
    
    filtered = np.zeros_like(audio)
    filtered[0] = audio[0]
    
    for i in range(1, len(audio)):
        filtered[i] = alpha * (filtered[i-1] + audio[i] - audio[i-1])
    
    return filtered


def _gated_loudness(
    audio: np.ndarray,
    sample_rate: int,
) -> Tuple[float, float, float]:
    """
    Calculate gated loudness per ITU-R BS.1770.
    
    Returns:
        (integrated_lufs, short_term_max, momentary_max)
    """
    # Block sizes
    momentary_size = int(sample_rate * 0.4)   # 400ms
    short_term_size = int(sample_rate * 3.0)  # 3s
    hop_size = int(sample_rate * 0.1)         # 100ms overlap
    
    if len(audio) < momentary_size:
        # Audio too short, use simple RMS
        rms = np.sqrt(np.mean(audio ** 2))
        lufs = -0.691 + 10 * np.log10(rms ** 2 + 1e-10)
        return lufs, lufs, lufs
    
    # Calculate momentary loudness for each block
    n_blocks = (len(audio) - momentary_size) // hop_size + 1
    momentary_loudness = []
    
    for i in range(n_blocks):
        start = i * hop_size
        block = audio[start:start + momentary_size]
        mean_square = np.mean(block ** 2)
        if mean_square > 0:
            loudness = -0.691 + 10 * np.log10(mean_square)
            momentary_loudness.append(loudness)
    
    if not momentary_loudness:
        return -70.0, -70.0, -70.0
    
    momentary_loudness = np.array(momentary_loudness)
    momentary_max = np.max(momentary_loudness)
    
    # Short-term loudness (3s moving average of momentary)
    short_term_blocks = max(1, int(3.0 / 0.1))
    if len(momentary_loudness) >= short_term_blocks:
        short_term_loudness = [
            np.mean(momentary_loudness[i:i+short_term_blocks])
            for i in range(len(momentary_loudness) - short_term_blocks + 1)
        ]
        short_term_max = max(short_term_loudness)
    else:
        short_term_max = np.mean(momentary_loudness)
    
    # Gating (ITU-R BS.1770-4)
    # First gate: absolute threshold of -70 LUFS
    above_absolute = momentary_loudness[momentary_loudness > -70]
    
    if len(above_absolute) == 0:
        return -70.0, short_term_max, momentary_max
    
    # Second gate: relative threshold = ungated mean - 10 LU
    ungated_mean = np.mean(above_absolute)
    relative_threshold = ungated_mean - 10
    
    # Final gated measurement
    above_relative = above_absolute[above_absolute > relative_threshold]
    
    if len(above_relative) == 0:
        integrated = ungated_mean
    else:
        integrated = np.mean(above_relative)
    
    return integrated, short_term_max, momentary_max


def _measure_loudness_range(audio: np.ndarray, sample_rate: int) -> float:
    """
    Measure loudness range (LRA) per EBU R128.
    
    Simplified implementation.
    """
    # Calculate short-term loudness distribution
    block_size = int(sample_rate * 3.0)  # 3s
    hop_size = int(sample_rate * 1.0)    # 1s overlap
    
    if len(audio) < block_size:
        return 0.0
    
    n_blocks = (len(audio) - block_size) // hop_size + 1
    short_term = []
    
    for i in range(n_blocks):
        start = i * hop_size
        block = audio[start:start + block_size]
        mean_square = np.mean(block ** 2)
        if mean_square > 0:
            loudness = -0.691 + 10 * np.log10(mean_square)
            short_term.append(loudness)
    
    if len(short_term) < 2:
        return 0.0
    
    short_term = np.array(short_term)
    
    # Gate at -70 LUFS absolute and -20 LU relative
    above_absolute = short_term[short_term > -70]
    if len(above_absolute) == 0:
        return 0.0
    
    relative_threshold = np.mean(above_absolute) - 20
    gated = above_absolute[above_absolute > relative_threshold]
    
    if len(gated) < 2:
        return 0.0
    
    # LRA is 10th to 95th percentile range
    p10 = np.percentile(gated, 10)
    p95 = np.percentile(gated, 95)
    
    return p95 - p10


@dataclass
class LoudnessNormalizer:
    """
    Loudness normalizer for consistent audio levels.
    
    Attributes:
        target_lufs: Target integrated loudness
        true_peak_limit: Maximum true peak level
        allow_increase: Whether to allow gain increase
    """
    target_lufs: float = -16.0
    true_peak_limit: float = -1.0
    allow_increase: bool = True
    
    def normalize(
        self,
        audio: np.ndarray,
        sample_rate: int = 22050,
    ) -> np.ndarray:
        """
        Normalize audio to target loudness.
        
        Args:
            audio: Input audio samples
            sample_rate: Sample rate in Hz
            
        Returns:
            Normalized audio
        """
        if len(audio) == 0:
            return audio.copy()
        
        # Measure current loudness
        stats = measure_loudness(audio, sample_rate)
        
        # Calculate required gain
        gain_lu = self.target_lufs - stats.integrated
        
        # Limit gain if not allowing increase
        if not self.allow_increase and gain_lu > 0:
            gain_lu = 0.0
        
        # Convert to linear
        gain_linear = 10 ** (gain_lu / 20)
        
        # Apply gain
        audio_float = audio.astype(np.float64)
        if audio.dtype == np.int16:
            audio_float = audio_float / 32768.0
        elif audio.dtype == np.int32:
            audio_float = audio_float / 2147483648.0
        
        normalized = audio_float * gain_linear
        
        # Check and limit true peak
        peak = np.max(np.abs(normalized))
        peak_limit_linear = 10 ** (self.true_peak_limit / 20)
        
        if peak > peak_limit_linear:
            normalized = normalized * (peak_limit_linear / peak)
        
        # Convert back to original dtype
        if audio.dtype == np.int16:
            normalized = (normalized * 32768).astype(np.int16)
        elif audio.dtype == np.int32:
            normalized = (normalized * 2147483648).astype(np.int32)
        else:
            normalized = normalized.astype(audio.dtype)
        
        return normalized


def normalize_loudness(
    audio: np.ndarray,
    target_lufs: float = -16.0,
    sample_rate: int = 22050,
    true_peak_limit: float = -1.0,
) -> np.ndarray:
    """
    Normalize audio to target loudness.
    
    Convenience function for quick loudness normalization.
    
    Args:
        audio: Input audio samples
        target_lufs: Target integrated loudness in LUFS
        sample_rate: Sample rate in Hz
        true_peak_limit: Maximum true peak in dBFS
        
    Returns:
        Normalized audio
        
    Example:
        # Normalize to streaming standard
        normalized = normalize_loudness(audio, target_lufs=-14.0)
        
        # Normalize for broadcast
        broadcast_audio = normalize_loudness(audio, target_lufs=-23.0, 
                                             true_peak_limit=-1.0)
    """
    normalizer = LoudnessNormalizer(
        target_lufs=target_lufs,
        true_peak_limit=true_peak_limit,
    )
    return normalizer.normalize(audio, sample_rate)


# Common loudness targets
LOUDNESS_TARGETS = {
    "spotify": -14.0,
    "apple_music": -16.0,
    "youtube": -14.0,
    "broadcast_ebu": -23.0,
    "broadcast_atsc": -24.0,
    "podcast": -16.0,
}


def get_target_lufs(platform: str) -> float:
    """
    Get target LUFS for a specific platform.
    
    Args:
        platform: Platform name
        
    Returns:
        Target LUFS value
        
    Raises:
        ValueError: If platform not recognized
    """
    if platform not in LOUDNESS_TARGETS:
        raise ValueError(f"Unknown platform: {platform}. Available: {list(LOUDNESS_TARGETS.keys())}")
    return LOUDNESS_TARGETS[platform]
