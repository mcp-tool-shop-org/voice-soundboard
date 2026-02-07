"""
Voice comparison utilities.

Provides A/B comparison and regression detection for voice quality.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import numpy as np

from voice_soundboard.quality.metrics import QualityMetrics, QualityLevel
from voice_soundboard.quality.evaluation import evaluate_full


class ComparisonResult(Enum):
    """Result of A/B comparison."""
    A_BETTER = "a_better"
    B_BETTER = "b_better"
    EQUIVALENT = "equivalent"
    INCONCLUSIVE = "inconclusive"


@dataclass
class VoiceComparison:
    """
    Detailed comparison between two voice samples.
    
    Attributes:
        similarity: Overall similarity score (0.0-1.0)
        spectral_similarity: Spectral similarity
        temporal_similarity: Timing/rhythm similarity
        metrics_a: Quality metrics for sample A
        metrics_b: Quality metrics for sample B
        differences: Specific differences detected
    """
    similarity: float
    spectral_similarity: float = 0.0
    temporal_similarity: float = 0.0
    metrics_a: Optional[QualityMetrics] = None
    metrics_b: Optional[QualityMetrics] = None
    differences: Dict[str, float] = field(default_factory=dict)
    
    @property
    def are_similar(self) -> bool:
        """Check if samples are considered similar (>0.8)."""
        return self.similarity >= 0.8
    
    @property
    def major_differences(self) -> List[str]:
        """Get list of significant differences (>0.2)."""
        return [k for k, v in self.differences.items() if abs(v) > 0.2]


@dataclass
class ABTestResult:
    """
    Result of A/B testing between voice samples.
    
    Attributes:
        result: Which sample is better or if equivalent
        confidence: Confidence in the result (0.0-1.0)
        quality_diff: Quality score difference (B - A)
        a_metrics: Metrics for sample A
        b_metrics: Metrics for sample B
        breakdown: Per-dimension comparison
    """
    result: ComparisonResult
    confidence: float
    quality_diff: float
    a_metrics: QualityMetrics
    b_metrics: QualityMetrics
    breakdown: Dict[str, str] = field(default_factory=dict)
    
    @property
    def winner(self) -> Optional[str]:
        """Get the winning sample or None if equivalent/inconclusive."""
        if self.result == ComparisonResult.A_BETTER:
            return "A"
        elif self.result == ComparisonResult.B_BETTER:
            return "B"
        return None
    
    def summary(self) -> str:
        """Get human-readable summary of results."""
        if self.result == ComparisonResult.A_BETTER:
            return f"Sample A is better (confidence: {self.confidence:.1%})"
        elif self.result == ComparisonResult.B_BETTER:
            return f"Sample B is better (confidence: {self.confidence:.1%})"
        elif self.result == ComparisonResult.EQUIVALENT:
            return f"Samples are equivalent (diff: {abs(self.quality_diff):.3f})"
        else:
            return "Results are inconclusive"


def compare_voices(
    audio_a: np.ndarray,
    audio_b: np.ndarray,
    sample_rate: int = 22050,
    reference_text: Optional[str] = None,
) -> VoiceComparison:
    """
    Compare two voice samples for similarity.
    
    Analyzes spectral, temporal, and quality characteristics
    to determine how similar two voice samples are.
    
    Args:
        audio_a: First audio sample
        audio_b: Second audio sample
        sample_rate: Sample rate of both samples
        reference_text: Optional reference text for quality eval
        
    Returns:
        VoiceComparison with detailed similarity scores
    """
    # Calculate spectral similarity
    spectral_sim = _spectral_similarity(audio_a, audio_b, sample_rate)
    
    # Calculate temporal similarity
    temporal_sim = _temporal_similarity(audio_a, audio_b, sample_rate)
    
    # Get quality metrics if reference text provided
    metrics_a = None
    metrics_b = None
    if reference_text:
        metrics_a = evaluate_full(audio_a, reference_text, sample_rate)
        metrics_b = evaluate_full(audio_b, reference_text, sample_rate)
    
    # Calculate differences
    differences = _calculate_differences(audio_a, audio_b, sample_rate)
    
    # Combined similarity
    similarity = spectral_sim * 0.6 + temporal_sim * 0.4
    
    return VoiceComparison(
        similarity=similarity,
        spectral_similarity=spectral_sim,
        temporal_similarity=temporal_sim,
        metrics_a=metrics_a,
        metrics_b=metrics_b,
        differences=differences,
    )


def _spectral_similarity(
    audio_a: np.ndarray,
    audio_b: np.ndarray,
    sample_rate: int,
) -> float:
    """Calculate spectral similarity using simplified spectral comparison."""
    if len(audio_a) == 0 or len(audio_b) == 0:
        return 0.0
    
    # Convert to float
    a = audio_a.astype(np.float32)
    b = audio_b.astype(np.float32)
    
    if audio_a.dtype != np.float32:
        a = a / np.iinfo(audio_a.dtype).max
    if audio_b.dtype != np.float32:
        b = b / np.iinfo(audio_b.dtype).max
    
    # Compute short-time energy patterns
    window_size = int(sample_rate * 0.025)  # 25ms
    hop_size = int(sample_rate * 0.010)  # 10ms
    
    def get_energy_profile(audio: np.ndarray) -> np.ndarray:
        n_windows = max(1, (len(audio) - window_size) // hop_size)
        energies = []
        for i in range(n_windows):
            start = i * hop_size
            window = audio[start:start + window_size]
            energies.append(np.sqrt(np.mean(window ** 2)))
        return np.array(energies) if energies else np.array([0.0])
    
    profile_a = get_energy_profile(a)
    profile_b = get_energy_profile(b)
    
    # Resample to same length for comparison
    target_len = min(len(profile_a), len(profile_b))
    if target_len == 0:
        return 0.0
    
    # Simple resampling
    indices_a = np.linspace(0, len(profile_a) - 1, target_len).astype(int)
    indices_b = np.linspace(0, len(profile_b) - 1, target_len).astype(int)
    
    profile_a = profile_a[indices_a]
    profile_b = profile_b[indices_b]
    
    # Normalize
    profile_a = profile_a / (np.max(profile_a) + 1e-8)
    profile_b = profile_b / (np.max(profile_b) + 1e-8)
    
    # Correlation-based similarity
    correlation = np.corrcoef(profile_a, profile_b)[0, 1]
    
    # Handle NaN
    if np.isnan(correlation):
        return 0.5
    
    # Convert correlation (-1 to 1) to similarity (0 to 1)
    return (correlation + 1) / 2


def _temporal_similarity(
    audio_a: np.ndarray,
    audio_b: np.ndarray,
    sample_rate: int,
) -> float:
    """Calculate temporal/rhythm similarity."""
    # Duration similarity
    dur_a = len(audio_a) / sample_rate
    dur_b = len(audio_b) / sample_rate
    
    if dur_a == 0 or dur_b == 0:
        return 0.0
    
    duration_sim = min(dur_a, dur_b) / max(dur_a, dur_b)
    
    # Pause pattern similarity
    def get_pause_pattern(audio: np.ndarray) -> np.ndarray:
        audio_f = audio.astype(np.float32)
        if audio.dtype != np.float32:
            audio_f = audio_f / np.iinfo(audio.dtype).max
        
        window_size = int(sample_rate * 0.02)  # 20ms
        n_windows = max(1, len(audio_f) // window_size)
        
        pattern = []
        threshold = np.sqrt(np.mean(audio_f ** 2)) * 0.1
        
        for i in range(n_windows):
            window = audio_f[i*window_size:(i+1)*window_size]
            rms = np.sqrt(np.mean(window ** 2))
            pattern.append(1 if rms > threshold else 0)
        
        return np.array(pattern) if pattern else np.array([0])
    
    pattern_a = get_pause_pattern(audio_a)
    pattern_b = get_pause_pattern(audio_b)
    
    # Resample patterns to same length
    target_len = min(len(pattern_a), len(pattern_b))
    if target_len == 0:
        return duration_sim
    
    indices_a = np.linspace(0, len(pattern_a) - 1, target_len).astype(int)
    indices_b = np.linspace(0, len(pattern_b) - 1, target_len).astype(int)
    
    pattern_a = pattern_a[indices_a]
    pattern_b = pattern_b[indices_b]
    
    # Pattern match ratio
    pattern_sim = np.mean(pattern_a == pattern_b)
    
    return duration_sim * 0.4 + pattern_sim * 0.6


def _calculate_differences(
    audio_a: np.ndarray,
    audio_b: np.ndarray,
    sample_rate: int,
) -> Dict[str, float]:
    """Calculate specific differences between samples."""
    differences = {}
    
    # Duration difference
    dur_a = len(audio_a) / sample_rate
    dur_b = len(audio_b) / sample_rate
    differences["duration"] = dur_b - dur_a
    
    # Energy difference
    def rms(audio):
        a = audio.astype(np.float32)
        if audio.dtype != np.float32:
            a = a / np.iinfo(audio.dtype).max
        return np.sqrt(np.mean(a ** 2))
    
    rms_a = rms(audio_a) if len(audio_a) > 0 else 0
    rms_b = rms(audio_b) if len(audio_b) > 0 else 0
    differences["energy"] = rms_b - rms_a
    
    # Dynamic range difference
    def dynamic_range(audio):
        if len(audio) == 0:
            return 0
        a = audio.astype(np.float32)
        if audio.dtype != np.float32:
            a = a / np.iinfo(audio.dtype).max
        return np.max(np.abs(a)) - np.min(np.abs(a))
    
    dr_a = dynamic_range(audio_a)
    dr_b = dynamic_range(audio_b)
    differences["dynamic_range"] = dr_b - dr_a
    
    return differences


def ab_test(
    audio_a: np.ndarray,
    audio_b: np.ndarray,
    reference_text: str,
    sample_rate: int = 22050,
    equivalence_threshold: float = 0.05,
    confidence_threshold: float = 0.7,
) -> ABTestResult:
    """
    Perform A/B test between two voice samples.
    
    Evaluates both samples and determines which is better
    or if they are equivalent within threshold.
    
    Args:
        audio_a: First audio sample (A)
        audio_b: Second audio sample (B)
        reference_text: The text being synthesized
        sample_rate: Sample rate of samples
        equivalence_threshold: Max quality diff for equivalence
        confidence_threshold: Required confidence for decision
        
    Returns:
        ABTestResult with winner and confidence
    """
    # Evaluate both samples
    metrics_a = evaluate_full(audio_a, reference_text, sample_rate)
    metrics_b = evaluate_full(audio_b, reference_text, sample_rate)
    
    quality_a = metrics_a.overall
    quality_b = metrics_b.overall
    quality_diff = quality_b - quality_a
    
    # Per-dimension comparison
    breakdown = {}
    
    if metrics_a.pronunciation and metrics_b.pronunciation:
        diff = metrics_b.pronunciation.overall - metrics_a.pronunciation.overall
        breakdown["pronunciation"] = "A" if diff < 0 else "B" if diff > 0 else "="
    
    if metrics_a.timing and metrics_b.timing:
        diff = metrics_b.timing.overall_score - metrics_a.timing.overall_score
        breakdown["timing"] = "A" if diff < 0 else "B" if diff > 0 else "="
    
    if metrics_a.naturalness and metrics_b.naturalness:
        diff = metrics_b.naturalness.overall - metrics_a.naturalness.overall
        breakdown["naturalness"] = "A" if diff < 0 else "B" if diff > 0 else "="
    
    # Determine result
    if abs(quality_diff) <= equivalence_threshold:
        result = ComparisonResult.EQUIVALENT
        confidence = 1.0 - abs(quality_diff) / equivalence_threshold
    elif quality_diff > 0:
        result = ComparisonResult.B_BETTER
        confidence = min(1.0, abs(quality_diff) / 0.2)
    else:
        result = ComparisonResult.A_BETTER
        confidence = min(1.0, abs(quality_diff) / 0.2)
    
    # Check confidence threshold
    if confidence < confidence_threshold and result != ComparisonResult.EQUIVALENT:
        result = ComparisonResult.INCONCLUSIVE
    
    return ABTestResult(
        result=result,
        confidence=confidence,
        quality_diff=quality_diff,
        a_metrics=metrics_a,
        b_metrics=metrics_b,
        breakdown=breakdown,
    )


@dataclass
class RegressionResult:
    """Result of regression detection."""
    has_regression: bool
    regressed_metrics: List[str]
    improvements: List[str]
    baseline_quality: float
    current_quality: float
    delta: float


def detect_regression(
    baseline_audio: np.ndarray,
    current_audio: np.ndarray,
    reference_text: str,
    sample_rate: int = 22050,
    regression_threshold: float = 0.1,
) -> RegressionResult:
    """
    Detect quality regression between baseline and current version.
    
    Args:
        baseline_audio: Audio from baseline/previous version
        current_audio: Audio from current version
        reference_text: The text being synthesized
        sample_rate: Sample rate of samples
        regression_threshold: Min degradation to flag as regression
        
    Returns:
        RegressionResult with detailed regression info
    """
    baseline_metrics = evaluate_full(baseline_audio, reference_text, sample_rate)
    current_metrics = evaluate_full(current_audio, reference_text, sample_rate)
    
    regressed = []
    improved = []
    
    # Check pronunciation
    if baseline_metrics.pronunciation and current_metrics.pronunciation:
        diff = current_metrics.pronunciation.overall - baseline_metrics.pronunciation.overall
        if diff < -regression_threshold:
            regressed.append("pronunciation")
        elif diff > regression_threshold:
            improved.append("pronunciation")
    
    # Check timing
    if baseline_metrics.timing and current_metrics.timing:
        diff = current_metrics.timing.overall_score - baseline_metrics.timing.overall_score
        if diff < -regression_threshold:
            regressed.append("timing")
        elif diff > regression_threshold:
            improved.append("timing")
    
    # Check naturalness
    if baseline_metrics.naturalness and current_metrics.naturalness:
        diff = current_metrics.naturalness.overall - baseline_metrics.naturalness.overall
        if diff < -regression_threshold:
            regressed.append("naturalness")
        elif diff > regression_threshold:
            improved.append("naturalness")
    
    # Signal quality
    diff = current_metrics.signal_quality - baseline_metrics.signal_quality
    if diff < -regression_threshold:
        regressed.append("signal_quality")
    elif diff > regression_threshold:
        improved.append("signal_quality")
    
    return RegressionResult(
        has_regression=len(regressed) > 0,
        regressed_metrics=regressed,
        improvements=improved,
        baseline_quality=baseline_metrics.overall,
        current_quality=current_metrics.overall,
        delta=current_metrics.overall - baseline_metrics.overall,
    )
