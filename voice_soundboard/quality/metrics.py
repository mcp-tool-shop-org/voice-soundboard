"""
Quality metrics data structures.

Defines metrics for measuring voice synthesis quality.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class QualityLevel(Enum):
    """Quality assessment level."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNACCEPTABLE = "unacceptable"
    
    @classmethod
    def from_score(cls, score: float) -> "QualityLevel":
        """
        Convert numeric score to quality level.
        
        Args:
            score: Score from 0.0 to 1.0
            
        Returns:
            QualityLevel corresponding to the score
        """
        if score >= 0.9:
            return cls.EXCELLENT
        elif score >= 0.75:
            return cls.GOOD
        elif score >= 0.6:
            return cls.ACCEPTABLE
        elif score >= 0.4:
            return cls.POOR
        else:
            return cls.UNACCEPTABLE


@dataclass
class PronunciationScore:
    """
    Score for pronunciation quality.
    
    Attributes:
        overall: Overall pronunciation score (0.0-1.0)
        word_scores: Per-word pronunciation scores
        phoneme_scores: Per-phoneme scores if available
        problem_words: Words with scores below threshold
        level: Quality level classification
    """
    overall: float
    word_scores: Dict[str, float] = field(default_factory=dict)
    phoneme_scores: Dict[str, float] = field(default_factory=dict)
    problem_words: List[str] = field(default_factory=list)
    
    @property
    def level(self) -> QualityLevel:
        """Get quality level for this score."""
        return QualityLevel.from_score(self.overall)
    
    def is_acceptable(self, threshold: float = 0.6) -> bool:
        """Check if pronunciation meets threshold."""
        return self.overall >= threshold


@dataclass
class TimingMetrics:
    """
    Metrics for timing/pacing quality.
    
    Attributes:
        words_per_minute: Speech rate
        target_wpm: Expected speech rate
        wpm_deviation: Deviation from target (percentage)
        pause_accuracy: How well pauses match expected timing
        syllable_timing: Per-syllable timing deviation
        overall_score: Combined timing score (0.0-1.0)
    """
    words_per_minute: float
    target_wpm: float = 150.0
    pause_accuracy: float = 1.0
    syllable_timing: float = 1.0
    
    @property
    def wpm_deviation(self) -> float:
        """Calculate WPM deviation as percentage."""
        if self.target_wpm == 0:
            return 0.0
        return abs(self.words_per_minute - self.target_wpm) / self.target_wpm
    
    @property
    def overall_score(self) -> float:
        """
        Calculate combined timing score.
        
        Weights: WPM deviation (40%), pause accuracy (30%), syllable timing (30%)
        """
        # Convert WPM deviation to score (0% deviation = 1.0, 50%+ = 0.0)
        wpm_score = max(0.0, 1.0 - self.wpm_deviation * 2)
        
        return (
            wpm_score * 0.4 +
            self.pause_accuracy * 0.3 +
            self.syllable_timing * 0.3
        )
    
    @property
    def level(self) -> QualityLevel:
        """Get quality level for timing."""
        return QualityLevel.from_score(self.overall_score)


@dataclass
class NaturalnessScore:
    """
    Score for naturalness/human-likeness.
    
    Attributes:
        overall: Overall naturalness score (0.0-1.0)
        prosody: Prosody naturalness (intonation, stress)
        fluency: Fluency without artifacts
        expressiveness: Emotional range and expression
        robotic_artifacts: Detected robotic quality (0=none, 1=severe)
    """
    overall: float
    prosody: float = 0.0
    fluency: float = 0.0
    expressiveness: float = 0.0
    robotic_artifacts: float = 0.0
    
    @property
    def level(self) -> QualityLevel:
        """Get quality level for naturalness."""
        return QualityLevel.from_score(self.overall)


@dataclass
class QualityMetrics:
    """
    Comprehensive quality metrics for synthesized speech.
    
    Attributes:
        pronunciation: Pronunciation quality score
        timing: Timing/pacing metrics
        naturalness: Naturalness assessment
        signal_quality: Audio signal quality (SNR, etc.)
        overall: Combined overall quality score
    """
    pronunciation: Optional[PronunciationScore] = None
    timing: Optional[TimingMetrics] = None
    naturalness: Optional[NaturalnessScore] = None
    signal_quality: float = 1.0  # 0.0-1.0
    
    @property
    def overall(self) -> float:
        """
        Calculate combined overall quality score.
        
        Weights components based on availability.
        """
        scores = []
        weights = []
        
        if self.pronunciation:
            scores.append(self.pronunciation.overall)
            weights.append(0.35)
        
        if self.timing:
            scores.append(self.timing.overall_score)
            weights.append(0.25)
        
        if self.naturalness:
            scores.append(self.naturalness.overall)
            weights.append(0.30)
        
        scores.append(self.signal_quality)
        weights.append(0.10)
        
        if not scores:
            return 0.0
        
        # Normalize weights
        total_weight = sum(weights)
        return sum(s * w / total_weight for s, w in zip(scores, weights))
    
    @property
    def level(self) -> QualityLevel:
        """Get overall quality level."""
        return QualityLevel.from_score(self.overall)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        result = {
            "overall": self.overall,
            "level": self.level.value,
            "signal_quality": self.signal_quality,
        }
        
        if self.pronunciation:
            result["pronunciation"] = {
                "score": self.pronunciation.overall,
                "level": self.pronunciation.level.value,
                "problem_words": self.pronunciation.problem_words,
            }
        
        if self.timing:
            result["timing"] = {
                "wpm": self.timing.words_per_minute,
                "target_wpm": self.timing.target_wpm,
                "deviation": self.timing.wpm_deviation,
                "score": self.timing.overall_score,
            }
        
        if self.naturalness:
            result["naturalness"] = {
                "score": self.naturalness.overall,
                "prosody": self.naturalness.prosody,
                "fluency": self.naturalness.fluency,
            }
        
        return result
