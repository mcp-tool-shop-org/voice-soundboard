"""
Voice Soundboard v2.4 - Audio Intelligence Module

Context-aware audio features that enhance speech synthesis.

Components:
    EmotionDetector - Text-based emotion inference with auto-prosody
    AdaptivePacer   - Content-aware speech rate adjustment
    SmartSilence    - Semantic pause insertion

All intelligence operates at the graph level, not inside the engine.

Usage:
    from voice_soundboard.intelligence import EmotionDetector

    detector = EmotionDetector()
    emotion = detector.analyze("I can't believe we won!")
    # EmotionResult(primary="joy", intensity=0.85)

    # Auto-apply to engine
    engine.speak("I can't believe we won!", auto_emotion=True)
"""

from voice_soundboard.intelligence.emotion import (
    EmotionDetector,
    EmotionResult,
    EmotionCategory,
    EmotionConfig,
    ProsodyParams,
)

from voice_soundboard.intelligence.pacing import (
    AdaptivePacer,
    PacingConfig,
    ContentType,
    PacingResult,
)

from voice_soundboard.intelligence.silence import (
    SmartSilence,
    SilenceConfig,
    PauseType,
    SilenceResult,
)

__all__ = [
    # Emotion
    "EmotionDetector",
    "EmotionResult",
    "EmotionCategory",
    "EmotionConfig",
    "ProsodyParams",
    # Pacing
    "AdaptivePacer",
    "PacingConfig",
    "ContentType",
    "PacingResult",
    # Silence
    "SmartSilence",
    "SilenceConfig",
    "PauseType",
    "SilenceResult",
]
