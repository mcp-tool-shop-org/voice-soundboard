"""
Quality evaluation functions.

Provides functions to evaluate different aspects of voice quality.
"""

from typing import Optional, List, Dict
import numpy as np

from voice_soundboard.quality.metrics import (
    PronunciationScore,
    TimingMetrics,
    NaturalnessScore,
    QualityMetrics,
)


def evaluate_pronunciation(
    audio: np.ndarray,
    reference_text: str,
    sample_rate: int = 22050,
    language: str = "en",
    word_threshold: float = 0.5,
) -> PronunciationScore:
    """
    Evaluate pronunciation quality of synthesized speech.
    
    Uses signal analysis to estimate pronunciation accuracy.
    For production use, consider integrating with a speech recognition
    service for more accurate word-level scoring.
    
    Args:
        audio: Audio samples as numpy array
        reference_text: The text that was synthesized
        sample_rate: Sample rate of audio
        language: Language code (e.g., "en", "es")
        word_threshold: Threshold below which words are flagged
        
    Returns:
        PronunciationScore with overall and per-word scores
    """
    words = reference_text.split()
    
    # Basic signal quality analysis
    # In production, this would integrate with ASR for word-level scoring
    
    # Estimate based on signal characteristics
    if len(audio) == 0:
        return PronunciationScore(overall=0.0, problem_words=words)
    
    # Analyze audio energy distribution
    audio_float = audio.astype(np.float32) / np.iinfo(audio.dtype).max if audio.dtype != np.float32 else audio
    
    # RMS energy
    rms = np.sqrt(np.mean(audio_float ** 2))
    
    # Check for silence ratio (might indicate missing words)
    silence_threshold = rms * 0.1
    silence_ratio = np.sum(np.abs(audio_float) < silence_threshold) / len(audio_float)
    
    # Estimate duration per word
    duration_s = len(audio) / sample_rate
    avg_word_duration = duration_s / max(len(words), 1)
    
    # Score based on reasonable speech patterns
    # Good speech: ~0.3-0.6s per word, silence ratio 0.1-0.3
    duration_score = 1.0 - abs(avg_word_duration - 0.4) / 0.4
    duration_score = max(0.0, min(1.0, duration_score))
    
    silence_score = 1.0 if 0.1 <= silence_ratio <= 0.3 else max(0.0, 1.0 - abs(silence_ratio - 0.2) * 3)
    
    # Combined score (simplified)
    overall = (duration_score * 0.6 + silence_score * 0.4)
    
    # Generate per-word scores (uniform distribution in this simple impl)
    # In production, ASR alignment would provide actual word scores
    word_scores = {word: overall for word in words}
    
    # Flag problem words (in simple impl, all words get same score)
    problem_words = [w for w, s in word_scores.items() if s < word_threshold]
    
    return PronunciationScore(
        overall=overall,
        word_scores=word_scores,
        problem_words=problem_words,
    )


def evaluate_timing(
    audio: np.ndarray,
    reference_text: str,
    sample_rate: int = 22050,
    target_wpm: float = 150.0,
    expected_pauses: Optional[List[float]] = None,
) -> TimingMetrics:
    """
    Evaluate timing and pacing of synthesized speech.
    
    Args:
        audio: Audio samples as numpy array
        reference_text: The text that was synthesized
        sample_rate: Sample rate of audio
        target_wpm: Target words per minute
        expected_pauses: Expected pause durations in seconds
        
    Returns:
        TimingMetrics with WPM and pacing scores
    """
    # Calculate actual WPM
    word_count = len(reference_text.split())
    duration_s = len(audio) / sample_rate
    
    if duration_s == 0:
        return TimingMetrics(
            words_per_minute=0.0,
            target_wpm=target_wpm,
            pause_accuracy=0.0,
            syllable_timing=0.0,
        )
    
    actual_wpm = (word_count / duration_s) * 60
    
    # Analyze pause patterns
    pause_accuracy = _analyze_pauses(audio, sample_rate, expected_pauses)
    
    # Analyze syllable timing consistency
    syllable_timing = _analyze_syllable_timing(audio, sample_rate)
    
    return TimingMetrics(
        words_per_minute=actual_wpm,
        target_wpm=target_wpm,
        pause_accuracy=pause_accuracy,
        syllable_timing=syllable_timing,
    )


def _analyze_pauses(
    audio: np.ndarray,
    sample_rate: int,
    expected_pauses: Optional[List[float]] = None,
) -> float:
    """Analyze pause distribution in audio."""
    if len(audio) == 0:
        return 0.0
    
    audio_float = audio.astype(np.float32) / np.iinfo(audio.dtype).max if audio.dtype != np.float32 else audio
    
    # Find pauses using energy threshold
    window_size = int(sample_rate * 0.02)  # 20ms windows
    
    if len(audio_float) < window_size:
        return 1.0
    
    # Calculate windowed RMS
    n_windows = len(audio_float) // window_size
    energies = np.array([
        np.sqrt(np.mean(audio_float[i*window_size:(i+1)*window_size] ** 2))
        for i in range(n_windows)
    ])
    
    if len(energies) == 0:
        return 1.0
    
    # Detect pauses (energy below threshold)
    threshold = np.median(energies) * 0.1
    is_pause = energies < threshold
    
    # Calculate pause statistics
    pause_ratio = np.sum(is_pause) / len(is_pause)
    
    # Good speech typically has 10-30% pause ratio
    if 0.1 <= pause_ratio <= 0.3:
        return 1.0
    else:
        return max(0.0, 1.0 - abs(pause_ratio - 0.2) * 3)


def _analyze_syllable_timing(audio: np.ndarray, sample_rate: int) -> float:
    """Analyze consistency of syllable timing."""
    if len(audio) == 0:
        return 0.0
    
    audio_float = audio.astype(np.float32) / np.iinfo(audio.dtype).max if audio.dtype != np.float32 else audio
    
    # Detect syllable boundaries using energy peaks
    window_size = int(sample_rate * 0.025)  # 25ms
    hop_size = int(sample_rate * 0.010)  # 10ms hop
    
    if len(audio_float) < window_size:
        return 1.0
    
    n_windows = (len(audio_float) - window_size) // hop_size
    
    if n_windows < 2:
        return 1.0
    
    energies = np.array([
        np.sqrt(np.mean(audio_float[i*hop_size:i*hop_size+window_size] ** 2))
        for i in range(n_windows)
    ])
    
    # Find peaks (syllable nuclei)
    peaks = []
    for i in range(1, len(energies) - 1):
        if energies[i] > energies[i-1] and energies[i] > energies[i+1]:
            if energies[i] > np.median(energies):
                peaks.append(i)
    
    if len(peaks) < 2:
        return 1.0
    
    # Calculate inter-peak intervals
    intervals = np.diff(peaks) * hop_size / sample_rate
    
    # Consistency = low variance in intervals
    if len(intervals) < 2:
        return 1.0
    
    cv = np.std(intervals) / np.mean(intervals) if np.mean(intervals) > 0 else 0
    
    # CV of 0 = perfect consistency, CV > 1 = very inconsistent
    return max(0.0, 1.0 - cv * 0.5)


def evaluate_naturalness(
    audio: np.ndarray,
    sample_rate: int = 22050,
) -> NaturalnessScore:
    """
    Evaluate naturalness/human-likeness of synthesized speech.
    
    Uses signal analysis to detect robotic artifacts and
    estimate naturalness. For more accurate assessment,
    consider using neural MOS prediction models.
    
    Args:
        audio: Audio samples as numpy array
        sample_rate: Sample rate of audio
        
    Returns:
        NaturalnessScore with component scores
    """
    if len(audio) == 0:
        return NaturalnessScore(overall=0.0)
    
    audio_float = audio.astype(np.float32) / np.iinfo(audio.dtype).max if audio.dtype != np.float32 else audio
    
    # Analyze prosody through pitch variation
    prosody = _analyze_prosody(audio_float, sample_rate)
    
    # Analyze fluency (absence of clicks/pops/discontinuities)
    fluency = _analyze_fluency(audio_float, sample_rate)
    
    # Detect robotic artifacts
    robotic_artifacts = _detect_robotic_artifacts(audio_float, sample_rate)
    
    # Expressiveness (dynamic range)
    expressiveness = _analyze_expressiveness(audio_float)
    
    # Combined naturalness score
    overall = (
        prosody * 0.3 +
        fluency * 0.3 +
        expressiveness * 0.2 +
        (1.0 - robotic_artifacts) * 0.2
    )
    
    return NaturalnessScore(
        overall=overall,
        prosody=prosody,
        fluency=fluency,
        expressiveness=expressiveness,
        robotic_artifacts=robotic_artifacts,
    )


def _analyze_prosody(audio: np.ndarray, sample_rate: int) -> float:
    """Analyze prosodic variation (intonation patterns)."""
    # Simplified analysis using zero-crossing rate variation
    window_size = int(sample_rate * 0.05)  # 50ms
    
    if len(audio) < window_size * 2:
        return 0.5
    
    n_windows = len(audio) // window_size
    
    # Calculate ZCR per window (rough pitch estimate)
    zcrs = []
    for i in range(n_windows):
        window = audio[i*window_size:(i+1)*window_size]
        zcr = np.sum(np.abs(np.diff(np.signbit(window)))) / len(window)
        zcrs.append(zcr)
    
    zcrs = np.array(zcrs)
    
    if len(zcrs) < 2:
        return 0.5
    
    # Good prosody = sufficient variation but not chaotic
    cv = np.std(zcrs) / np.mean(zcrs) if np.mean(zcrs) > 0 else 0
    
    # Ideal CV range for natural speech: 0.2-0.5
    if 0.2 <= cv <= 0.5:
        return 1.0
    elif cv < 0.1:  # Too monotone
        return 0.3
    elif cv > 1.0:  # Too chaotic
        return 0.5
    else:
        return 0.7


def _analyze_fluency(audio: np.ndarray, sample_rate: int) -> float:
    """Detect discontinuities and artifacts."""
    # Look for sudden amplitude jumps (clicks/pops)
    diff = np.abs(np.diff(audio))
    
    if len(diff) == 0:
        return 1.0
    
    # Threshold for detecting artifacts
    threshold = np.std(diff) * 4
    artifacts = np.sum(diff > threshold)
    
    artifact_ratio = artifacts / len(diff)
    
    # Few artifacts = high fluency
    return max(0.0, 1.0 - artifact_ratio * 100)


def _detect_robotic_artifacts(audio: np.ndarray, sample_rate: int) -> float:
    """Detect robotic/mechanical artifacts in audio."""
    # Analyze for unnatural periodicity
    window_size = int(sample_rate * 0.1)  # 100ms
    
    if len(audio) < window_size * 3:
        return 0.0
    
    # Check for unnaturally regular patterns
    # Natural speech has variation; robotic speech is too regular
    
    n_windows = len(audio) // window_size
    energies = []
    
    for i in range(n_windows):
        window = audio[i*window_size:(i+1)*window_size]
        energies.append(np.sqrt(np.mean(window ** 2)))
    
    energies = np.array(energies)
    
    if len(energies) < 3:
        return 0.0
    
    # Check for mechanical regularity
    energy_diff = np.diff(energies)
    regularity = 1.0 - np.std(energy_diff) / (np.mean(np.abs(energy_diff)) + 1e-6)
    
    # Very high regularity suggests robotic quality
    return max(0.0, min(1.0, regularity - 0.5))


def _analyze_expressiveness(audio: np.ndarray) -> float:
    """Analyze dynamic range and expressiveness."""
    if len(audio) == 0:
        return 0.0
    
    # Dynamic range
    peak = np.max(np.abs(audio))
    rms = np.sqrt(np.mean(audio ** 2))
    
    if rms == 0:
        return 0.0
    
    crest_factor = peak / rms
    
    # Good expressiveness: crest factor between 3-10
    # Too low = compressed, too high = sparse/unnatural
    if 3 <= crest_factor <= 10:
        return 1.0
    elif crest_factor < 2:
        return 0.4
    elif crest_factor > 15:
        return 0.5
    else:
        return 0.7


def evaluate_full(
    audio: np.ndarray,
    reference_text: str,
    sample_rate: int = 22050,
    target_wpm: float = 150.0,
) -> QualityMetrics:
    """
    Perform comprehensive quality evaluation.
    
    Runs all evaluation functions and returns combined metrics.
    
    Args:
        audio: Audio samples as numpy array
        reference_text: The text that was synthesized
        sample_rate: Sample rate of audio
        target_wpm: Target words per minute
        
    Returns:
        QualityMetrics with all component scores
    """
    pronunciation = evaluate_pronunciation(audio, reference_text, sample_rate)
    timing = evaluate_timing(audio, reference_text, sample_rate, target_wpm)
    naturalness = evaluate_naturalness(audio, sample_rate)
    
    # Signal quality (basic SNR estimation)
    audio_float = audio.astype(np.float32) / np.iinfo(audio.dtype).max if audio.dtype != np.float32 else audio
    rms = np.sqrt(np.mean(audio_float ** 2))
    signal_quality = min(1.0, rms * 10) if rms > 0 else 0.0
    
    return QualityMetrics(
        pronunciation=pronunciation,
        timing=timing,
        naturalness=naturalness,
        signal_quality=signal_quality,
    )
