"""
Tests for v2.3 quality module.
"""

import pytest
import numpy as np

from voice_soundboard.quality import (
    QualityMetrics,
    PronunciationScore,
    TimingMetrics,
    evaluate_pronunciation,
    evaluate_timing,
    evaluate_naturalness,
    VoiceComparison,
    compare_voices,
    ABTestResult,
)
from voice_soundboard.quality.metrics import QualityLevel, NaturalnessScore
from voice_soundboard.quality.comparison import ab_test, detect_regression, ComparisonResult


class TestQualityMetrics:
    """Tests for QualityMetrics."""
    
    def test_quality_level_from_score(self):
        assert QualityLevel.from_score(0.95) == QualityLevel.EXCELLENT
        assert QualityLevel.from_score(0.8) == QualityLevel.GOOD
        assert QualityLevel.from_score(0.65) == QualityLevel.ACCEPTABLE
        assert QualityLevel.from_score(0.45) == QualityLevel.POOR
        assert QualityLevel.from_score(0.2) == QualityLevel.UNACCEPTABLE
        
    def test_pronunciation_score(self):
        score = PronunciationScore(
            overall=0.85,
            word_scores={"hello": 0.9, "world": 0.8},
            problem_words=["world"],
        )
        
        assert score.overall == 0.85
        assert score.level == QualityLevel.GOOD
        assert score.is_acceptable()
        assert "world" in score.problem_words
        
    def test_timing_metrics(self):
        timing = TimingMetrics(
            words_per_minute=145,
            target_wpm=150,
            pause_accuracy=0.9,
            syllable_timing=0.85,
        )
        
        assert timing.wpm_deviation == pytest.approx(0.033, rel=0.1)
        assert timing.overall_score > 0.8
        
    def test_combined_quality_metrics(self):
        metrics = QualityMetrics(
            pronunciation=PronunciationScore(overall=0.8),
            timing=TimingMetrics(words_per_minute=150, target_wpm=150),
            naturalness=NaturalnessScore(overall=0.75),
            signal_quality=0.9,
        )
        
        # Overall should be weighted combination
        assert 0.7 <= metrics.overall <= 0.9
        assert metrics.level in [QualityLevel.GOOD, QualityLevel.ACCEPTABLE]
        
    def test_quality_metrics_to_dict(self):
        metrics = QualityMetrics(
            pronunciation=PronunciationScore(overall=0.8, problem_words=["test"]),
            signal_quality=0.9,
        )
        
        data = metrics.to_dict()
        
        assert "overall" in data
        assert "pronunciation" in data
        assert data["pronunciation"]["score"] == 0.8


class TestPronunciationEvaluation:
    """Tests for pronunciation evaluation."""
    
    def test_evaluate_pronunciation_basic(self):
        # Generate simple audio
        sample_rate = 22050
        duration = 1.0
        audio = np.sin(2 * np.pi * 440 * np.linspace(0, duration, int(sample_rate * duration)))
        audio = (audio * 32767).astype(np.int16)
        
        score = evaluate_pronunciation(audio, "Hello world", sample_rate)
        
        assert isinstance(score, PronunciationScore)
        assert 0.0 <= score.overall <= 1.0
        
    def test_evaluate_pronunciation_empty_audio(self):
        score = evaluate_pronunciation(np.array([], dtype=np.int16), "Hello")
        
        assert score.overall == 0.0
        assert "Hello" in score.problem_words


class TestTimingEvaluation:
    """Tests for timing evaluation."""
    
    def test_evaluate_timing_basic(self):
        # Generate audio representing ~150 WPM
        sample_rate = 22050
        words = 3
        target_wpm = 150
        duration = (words / target_wpm) * 60  # Duration for 3 words at 150 WPM
        
        audio = np.random.randn(int(sample_rate * duration)) * 0.5
        audio = (audio * 32767).astype(np.int16)
        
        timing = evaluate_timing(
            audio,
            "Hello world friends",
            sample_rate,
            target_wpm=150,
        )
        
        assert isinstance(timing, TimingMetrics)
        # WPM should be close to target
        assert abs(timing.words_per_minute - 150) < 50
        
    def test_evaluate_timing_empty_audio(self):
        timing = evaluate_timing(np.array([], dtype=np.int16), "Hello")
        
        assert timing.words_per_minute == 0.0


class TestNaturalnessEvaluation:
    """Tests for naturalness evaluation."""
    
    def test_evaluate_naturalness_basic(self):
        # Generate varied audio (more natural)
        sample_rate = 22050
        duration = 2.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Varying frequency to simulate natural speech
        freq = 200 + 100 * np.sin(2 * np.pi * 0.5 * t)  # Modulated frequency
        audio = np.sin(2 * np.pi * freq * t)
        audio = (audio * 16000).astype(np.int16)
        
        score = evaluate_naturalness(audio, sample_rate)
        
        assert isinstance(score, NaturalnessScore)
        assert 0.0 <= score.overall <= 1.0
        assert 0.0 <= score.prosody <= 1.0
        assert 0.0 <= score.fluency <= 1.0


class TestVoiceComparison:
    """Tests for voice comparison."""
    
    def test_compare_identical_voices(self):
        sample_rate = 22050
        audio = np.sin(np.linspace(0, 10, sample_rate)) * 32767
        audio = audio.astype(np.int16)
        
        comparison = compare_voices(audio, audio.copy(), sample_rate)
        
        assert comparison.similarity > 0.9
        assert comparison.are_similar
        
    def test_compare_different_voices(self):
        sample_rate = 22050
        
        # Two different audio signals
        audio_a = (np.sin(np.linspace(0, 20, sample_rate)) * 32767).astype(np.int16)
        audio_b = (np.sin(np.linspace(0, 40, sample_rate)) * 32767).astype(np.int16)
        
        comparison = compare_voices(audio_a, audio_b, sample_rate)
        
        assert isinstance(comparison, VoiceComparison)
        assert "duration" in comparison.differences


class TestABTesting:
    """Tests for A/B testing."""
    
    def test_ab_test_equivalent(self):
        sample_rate = 22050
        audio = (np.sin(np.linspace(0, 10, sample_rate)) * 32767).astype(np.int16)
        
        result = ab_test(audio, audio.copy(), "Hello world", sample_rate)
        
        assert result.result == ComparisonResult.EQUIVALENT
        assert abs(result.quality_diff) < 0.1
        
    def test_ab_test_result_summary(self):
        sample_rate = 22050
        audio_a = (np.random.randn(sample_rate) * 16000).astype(np.int16)
        audio_b = (np.random.randn(sample_rate) * 16000).astype(np.int16)
        
        result = ab_test(audio_a, audio_b, "Test", sample_rate)
        
        summary = result.summary()
        assert isinstance(summary, str)
        assert len(summary) > 0


class TestRegressionDetection:
    """Tests for regression detection."""
    
    def test_detect_no_regression(self):
        sample_rate = 22050
        audio = (np.sin(np.linspace(0, 10, sample_rate)) * 32767).astype(np.int16)
        
        result = detect_regression(
            audio,
            audio.copy(),
            "Hello world",
            sample_rate,
        )
        
        assert not result.has_regression
        assert len(result.regressed_metrics) == 0
        
    def test_detect_regression_returns_details(self):
        sample_rate = 22050
        
        # Good baseline
        baseline = (np.sin(np.linspace(0, 10, sample_rate)) * 32767).astype(np.int16)
        
        # Degraded current (noise)
        current = (np.random.randn(sample_rate // 2) * 8000).astype(np.int16)
        
        result = detect_regression(
            baseline,
            current,
            "Hello world",
            sample_rate,
        )
        
        # Should have regression info
        assert result.delta == result.current_quality - result.baseline_quality
