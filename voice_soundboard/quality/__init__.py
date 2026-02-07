"""
Voice Quality Metrics for Voice Soundboard v2.3.

Provides tools for measuring and comparing voice quality:
- Pronunciation scoring
- Timing deviation metrics
- A/B comparison utilities
- Regression detection

Example:
    from voice_soundboard.quality import evaluate_pronunciation, compare_voices
    
    score = evaluate_pronunciation(audio, reference_text)
    print(f"Pronunciation score: {score.overall}")
    
    comparison = compare_voices(audio_a, audio_b)
    print(f"Similarity: {comparison.similarity}")
"""

from voice_soundboard.quality.metrics import (
    QualityMetrics,
    PronunciationScore,
    TimingMetrics,
)
from voice_soundboard.quality.evaluation import (
    evaluate_pronunciation,
    evaluate_timing,
    evaluate_naturalness,
)
from voice_soundboard.quality.comparison import (
    VoiceComparison,
    compare_voices,
    ABTestResult,
)

__all__ = [
    # Metrics
    "QualityMetrics",
    "PronunciationScore",
    "TimingMetrics",
    # Evaluation
    "evaluate_pronunciation",
    "evaluate_timing",
    "evaluate_naturalness",
    # Comparison
    "VoiceComparison",
    "compare_voices",
    "ABTestResult",
]
