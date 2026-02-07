"""
Audio Assertions - Quality assertions for audio testing.

Features:
    - Duration assertions
    - Amplitude assertions
    - Clipping detection
    - Silence detection
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class AudioAnalysis:
    """Analysis results for audio data."""
    
    duration: float
    sample_rate: int
    num_samples: int
    
    # Amplitude
    peak_amplitude: float
    rms_amplitude: float
    dynamic_range_db: float
    
    # Quality
    has_clipping: bool
    clipping_percentage: float
    silence_percentage: float
    
    # Frequency (basic)
    dc_offset: float
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "num_samples": self.num_samples,
            "peak_amplitude": self.peak_amplitude,
            "rms_amplitude": self.rms_amplitude,
            "dynamic_range_db": self.dynamic_range_db,
            "has_clipping": self.has_clipping,
            "clipping_percentage": self.clipping_percentage,
            "silence_percentage": self.silence_percentage,
            "dc_offset": self.dc_offset,
        }


class AudioAssertions:
    """
    Audio quality assertions for testing.
    
    Example:
        # From PCM bytes
        assertions = AudioAssertions(audio_bytes, sample_rate=24000)
        
        # From numpy array
        assertions = AudioAssertions(audio_array)
        
        # Assert properties
        assertions.assert_duration(5.0, tolerance=0.1)
        assertions.assert_no_clipping()
        assertions.assert_not_silent()
        
        # Get analysis
        analysis = assertions.analyze()
    """
    
    def __init__(
        self,
        audio: bytes | np.ndarray,
        sample_rate: int = 24000,
    ):
        """Initialize assertions with audio data.
        
        Args:
            audio: PCM bytes (int16) or numpy array (float32)
            sample_rate: Sample rate in Hz
        """
        self.sample_rate = sample_rate
        
        # Convert to float32 numpy array
        if isinstance(audio, bytes):
            # Decode 16-bit PCM
            samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32)
            self.audio = samples / 32768.0
        elif isinstance(audio, np.ndarray):
            if audio.dtype != np.float32:
                self.audio = audio.astype(np.float32)
            else:
                self.audio = audio
        else:
            raise TypeError(f"Unsupported audio type: {type(audio)}")
        
        # Cache analysis
        self._analysis: AudioAnalysis | None = None
    
    @property
    def duration(self) -> float:
        """Get audio duration in seconds."""
        return len(self.audio) / self.sample_rate
    
    @property
    def num_samples(self) -> int:
        """Get number of samples."""
        return len(self.audio)
    
    def analyze(self) -> AudioAnalysis:
        """Perform full audio analysis."""
        if self._analysis is not None:
            return self._analysis
        
        if len(self.audio) == 0:
            self._analysis = AudioAnalysis(
                duration=0.0,
                sample_rate=self.sample_rate,
                num_samples=0,
                peak_amplitude=0.0,
                rms_amplitude=0.0,
                dynamic_range_db=0.0,
                has_clipping=False,
                clipping_percentage=0.0,
                silence_percentage=100.0,
                dc_offset=0.0,
            )
            return self._analysis
        
        # Calculate metrics
        peak = float(np.max(np.abs(self.audio)))
        rms = float(np.sqrt(np.mean(self.audio ** 2)))
        
        # Dynamic range
        if rms > 0:
            dynamic_range = 20 * np.log10(peak / rms) if peak > 0 else 0
        else:
            dynamic_range = 0
        
        # Clipping detection (samples at ±1.0)
        clipping_threshold = 0.99
        clipped_samples = np.sum(np.abs(self.audio) >= clipping_threshold)
        clipping_percentage = (clipped_samples / len(self.audio)) * 100
        
        # Silence detection (samples near 0)
        silence_threshold = 0.001
        silent_samples = np.sum(np.abs(self.audio) < silence_threshold)
        silence_percentage = (silent_samples / len(self.audio)) * 100
        
        # DC offset
        dc_offset = float(np.mean(self.audio))
        
        self._analysis = AudioAnalysis(
            duration=self.duration,
            sample_rate=self.sample_rate,
            num_samples=len(self.audio),
            peak_amplitude=peak,
            rms_amplitude=rms,
            dynamic_range_db=float(dynamic_range),
            has_clipping=clipping_percentage > 0,
            clipping_percentage=clipping_percentage,
            silence_percentage=silence_percentage,
            dc_offset=dc_offset,
        )
        
        return self._analysis
    
    def assert_duration(
        self,
        expected: float,
        tolerance: float = 0.1,
        message: str | None = None,
    ) -> "AudioAssertions":
        """Assert audio duration is within tolerance.
        
        Args:
            expected: Expected duration in seconds
            tolerance: Allowed deviation in seconds
            message: Custom error message
        """
        actual = self.duration
        
        if abs(actual - expected) > tolerance:
            msg = message or f"Duration {actual:.3f}s not within {tolerance}s of expected {expected:.3f}s"
            raise AssertionError(msg)
        
        return self
    
    def assert_min_duration(
        self,
        minimum: float,
        message: str | None = None,
    ) -> "AudioAssertions":
        """Assert audio is at least a minimum duration."""
        if self.duration < minimum:
            msg = message or f"Duration {self.duration:.3f}s is less than minimum {minimum:.3f}s"
            raise AssertionError(msg)
        
        return self
    
    def assert_max_duration(
        self,
        maximum: float,
        message: str | None = None,
    ) -> "AudioAssertions":
        """Assert audio is at most a maximum duration."""
        if self.duration > maximum:
            msg = message or f"Duration {self.duration:.3f}s exceeds maximum {maximum:.3f}s"
            raise AssertionError(msg)
        
        return self
    
    def assert_no_clipping(
        self,
        threshold: float = 0.01,
        message: str | None = None,
    ) -> "AudioAssertions":
        """Assert audio has no clipping.
        
        Args:
            threshold: Maximum allowed percentage of clipped samples
            message: Custom error message
        """
        analysis = self.analyze()
        
        if analysis.clipping_percentage > threshold:
            msg = message or f"Audio has {analysis.clipping_percentage:.2f}% clipped samples (threshold: {threshold}%)"
            raise AssertionError(msg)
        
        return self
    
    def assert_not_silent(
        self,
        threshold: float = 95.0,
        message: str | None = None,
    ) -> "AudioAssertions":
        """Assert audio is not mostly silent.
        
        Args:
            threshold: Maximum allowed percentage of silent samples
            message: Custom error message
        """
        analysis = self.analyze()
        
        if analysis.silence_percentage > threshold:
            msg = message or f"Audio is {analysis.silence_percentage:.1f}% silent (threshold: {threshold}%)"
            raise AssertionError(msg)
        
        return self
    
    def assert_peak_below(
        self,
        maximum: float,
        message: str | None = None,
    ) -> "AudioAssertions":
        """Assert peak amplitude is below threshold."""
        analysis = self.analyze()
        
        if analysis.peak_amplitude > maximum:
            msg = message or f"Peak amplitude {analysis.peak_amplitude:.3f} exceeds maximum {maximum:.3f}"
            raise AssertionError(msg)
        
        return self
    
    def assert_rms_range(
        self,
        minimum: float,
        maximum: float,
        message: str | None = None,
    ) -> "AudioAssertions":
        """Assert RMS amplitude is within range."""
        analysis = self.analyze()
        
        if analysis.rms_amplitude < minimum or analysis.rms_amplitude > maximum:
            msg = message or f"RMS amplitude {analysis.rms_amplitude:.3f} not in range [{minimum}, {maximum}]"
            raise AssertionError(msg)
        
        return self
    
    def assert_no_dc_offset(
        self,
        threshold: float = 0.01,
        message: str | None = None,
    ) -> "AudioAssertions":
        """Assert audio has no significant DC offset."""
        analysis = self.analyze()
        
        if abs(analysis.dc_offset) > threshold:
            msg = message or f"DC offset {analysis.dc_offset:.4f} exceeds threshold {threshold}"
            raise AssertionError(msg)
        
        return self
    
    def assert_valid(self) -> "AudioAssertions":
        """Run all common assertions."""
        self.assert_not_silent()
        self.assert_no_clipping()
        self.assert_no_dc_offset()
        return self
    
    def get_segment(
        self,
        start: float,
        end: float,
    ) -> "AudioAssertions":
        """Get assertions for a segment of audio.
        
        Args:
            start: Start time in seconds
            end: End time in seconds
            
        Returns:
            New AudioAssertions for the segment
        """
        start_sample = int(start * self.sample_rate)
        end_sample = int(end * self.sample_rate)
        
        segment = self.audio[start_sample:end_sample]
        
        return AudioAssertions(segment, self.sample_rate)
    
    def compare_with(
        self,
        other: "AudioAssertions",
        threshold: float = 0.1,
    ) -> dict[str, bool]:
        """Compare with another audio.
        
        Args:
            other: Other AudioAssertions to compare
            threshold: Similarity threshold
            
        Returns:
            Dict of comparison results
        """
        self_analysis = self.analyze()
        other_analysis = other.analyze()
        
        return {
            "similar_duration": abs(self_analysis.duration - other_analysis.duration) < threshold,
            "similar_peak": abs(self_analysis.peak_amplitude - other_analysis.peak_amplitude) < threshold,
            "similar_rms": abs(self_analysis.rms_amplitude - other_analysis.rms_amplitude) < threshold,
        }
