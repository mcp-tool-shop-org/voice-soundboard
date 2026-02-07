"""
Emotion Detection - Text-based emotion inference for prosody adjustment.

Detects emotional content in text and suggests voice parameters:
    - Primary emotion (joy, sadness, anger, fear, surprise, neutral)
    - Intensity (0.0 to 1.0)
    - Secondary emotion (optional)
    - Suggested prosody parameters

Uses transformer-based models for accurate detection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class EmotionCategory(Enum):
    """Emotion categories for TTS prosody adjustment."""
    
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    NEUTRAL = "neutral"
    
    # Additional nuanced emotions
    EXCITEMENT = "excitement"
    ANXIETY = "anxiety"
    CONTENTMENT = "contentment"
    FRUSTRATION = "frustration"


@dataclass
class ProsodyParams:
    """Voice prosody parameters suggested by emotion detection."""
    
    pitch: float = 1.0  # Pitch modifier (1.0 = normal)
    speed: float = 1.0  # Speed modifier (1.0 = normal)
    energy: float = 1.0  # Energy/volume modifier (1.0 = normal)
    
    # Advanced parameters
    pitch_variation: float = 1.0  # Amount of pitch variation
    pause_scale: float = 1.0  # Scale factor for pauses
    
    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary for engine config."""
        return {
            "pitch": self.pitch,
            "speed": self.speed,
            "energy": self.energy,
            "pitch_variation": self.pitch_variation,
            "pause_scale": self.pause_scale,
        }
    
    def apply(self, base: "ProsodyParams") -> "ProsodyParams":
        """Apply these params as modifiers to base params."""
        return ProsodyParams(
            pitch=base.pitch * self.pitch,
            speed=base.speed * self.speed,
            energy=base.energy * self.energy,
            pitch_variation=base.pitch_variation * self.pitch_variation,
            pause_scale=base.pause_scale * self.pause_scale,
        )


@dataclass
class EmotionResult:
    """Result of emotion analysis."""
    
    primary: EmotionCategory
    intensity: float  # 0.0 to 1.0
    secondary: EmotionCategory | None = None
    secondary_intensity: float = 0.0
    confidence: float = 0.0
    suggested_params: ProsodyParams = field(default_factory=ProsodyParams)
    
    # Analysis metadata
    trigger_words: list[str] = field(default_factory=list)
    sentiment_score: float = 0.0  # -1.0 (negative) to 1.0 (positive)


@dataclass
class EmotionConfig:
    """Configuration for emotion detection."""
    
    # Model settings
    model_name: str = "j-hartmann/emotion-english-distilroberta-base"
    use_gpu: bool = True
    
    # Detection settings
    min_confidence: float = 0.3
    intensity_threshold: float = 0.1
    detect_secondary: bool = True
    
    # Prosody mapping
    use_default_mapping: bool = True
    custom_mapping: dict[str, ProsodyParams] | None = None
    
    # Performance
    batch_size: int = 8
    cache_results: bool = True
    max_cache_size: int = 1000


# Default prosody mappings for each emotion
DEFAULT_PROSODY_MAP: dict[EmotionCategory, ProsodyParams] = {
    EmotionCategory.JOY: ProsodyParams(
        pitch=1.10,
        speed=1.05,
        energy=1.20,
        pitch_variation=1.15,
    ),
    EmotionCategory.SADNESS: ProsodyParams(
        pitch=0.95,
        speed=0.90,
        energy=0.85,
        pitch_variation=0.85,
        pause_scale=1.2,
    ),
    EmotionCategory.ANGER: ProsodyParams(
        pitch=1.05,
        speed=1.10,
        energy=1.30,
        pitch_variation=1.2,
    ),
    EmotionCategory.FEAR: ProsodyParams(
        pitch=1.15,
        speed=1.15,
        energy=0.90,
        pitch_variation=1.3,
    ),
    EmotionCategory.SURPRISE: ProsodyParams(
        pitch=1.20,
        speed=1.05,
        energy=1.10,
        pitch_variation=1.25,
    ),
    EmotionCategory.DISGUST: ProsodyParams(
        pitch=0.95,
        speed=0.95,
        energy=1.05,
        pitch_variation=0.9,
    ),
    EmotionCategory.NEUTRAL: ProsodyParams(
        pitch=1.0,
        speed=1.0,
        energy=1.0,
    ),
    EmotionCategory.EXCITEMENT: ProsodyParams(
        pitch=1.15,
        speed=1.10,
        energy=1.25,
        pitch_variation=1.3,
    ),
    EmotionCategory.ANXIETY: ProsodyParams(
        pitch=1.10,
        speed=1.15,
        energy=0.95,
        pitch_variation=1.2,
    ),
    EmotionCategory.CONTENTMENT: ProsodyParams(
        pitch=1.0,
        speed=0.95,
        energy=0.95,
        pitch_variation=0.9,
    ),
    EmotionCategory.FRUSTRATION: ProsodyParams(
        pitch=1.05,
        speed=1.05,
        energy=1.15,
        pitch_variation=1.1,
    ),
}


# Simple keyword-based detection for fallback
EMOTION_KEYWORDS: dict[EmotionCategory, list[str]] = {
    EmotionCategory.JOY: [
        "happy", "joy", "excited", "wonderful", "amazing", "great", "love",
        "fantastic", "awesome", "brilliant", "delighted", "thrilled", "glad",
        "cheerful", "ecstatic", "elated", "pleased", "yay", "hurray", "woohoo",
    ],
    EmotionCategory.SADNESS: [
        "sad", "unhappy", "depressed", "sorry", "disappointed", "unfortunate",
        "grief", "sorrow", "miserable", "heartbroken", "lonely", "gloomy",
        "melancholy", "tragic", "crying", "tears", "loss", "mourn",
    ],
    EmotionCategory.ANGER: [
        "angry", "furious", "mad", "annoyed", "irritated", "frustrated",
        "outraged", "enraged", "hostile", "hate", "despise", "rage",
        "infuriated", "livid", "bitter", "resentful",
    ],
    EmotionCategory.FEAR: [
        "afraid", "scared", "terrified", "frightened", "worried", "anxious",
        "nervous", "panic", "dread", "horror", "alarmed", "uneasy",
        "apprehensive", "paranoid", "phobia", "terror",
    ],
    EmotionCategory.SURPRISE: [
        "surprised", "shocked", "amazed", "astonished", "startled", "wow",
        "unexpected", "unbelievable", "incredible", "stunning", "remarkable",
        "extraordinary", "mind-blown", "speechless",
    ],
    EmotionCategory.DISGUST: [
        "disgusted", "gross", "revolting", "nauseating", "repulsive", "vile",
        "horrible", "awful", "appalling", "sickening", "repugnant",
    ],
}


class EmotionDetector:
    """
    Detect emotion from text to auto-select voice parameters.
    
    Example:
        detector = EmotionDetector()
        
        text = "I can't believe we won! This is amazing!"
        emotion = detector.analyze(text)
        # EmotionResult(
        #   primary=EmotionCategory.JOY,
        #   intensity=0.85,
        #   secondary=EmotionCategory.SURPRISE,
        #   suggested_params={"pitch": 1.1, "speed": 1.05, "energy": 1.2}
        # )
        
        # Auto-apply emotion
        engine.speak(text, auto_emotion=True)
    """
    
    def __init__(self, config: EmotionConfig | None = None):
        self.config = config or EmotionConfig()
        self._model = None
        self._tokenizer = None
        self._cache: dict[str, EmotionResult] = {}
        self._prosody_map = (
            self.config.custom_mapping
            if self.config.custom_mapping
            else DEFAULT_PROSODY_MAP
        )
    
    def _load_model(self) -> None:
        """Lazy-load the emotion detection model."""
        if self._model is not None:
            return
        
        try:
            from transformers import pipeline
            
            device = 0 if self.config.use_gpu else -1
            self._model = pipeline(
                "text-classification",
                model=self.config.model_name,
                top_k=5,
                device=device,
            )
        except ImportError:
            # Fall back to keyword-based detection
            self._model = "keyword"
    
    def analyze(self, text: str) -> EmotionResult:
        """
        Analyze text for emotional content.
        
        Args:
            text: Input text to analyze
            
        Returns:
            EmotionResult with detected emotions and suggested parameters
        """
        # Check cache
        if self.config.cache_results and text in self._cache:
            return self._cache[text]
        
        # Load model if needed
        self._load_model()
        
        # Analyze
        if self._model == "keyword":
            result = self._analyze_keywords(text)
        else:
            result = self._analyze_transformer(text)
        
        # Add suggested prosody params
        result.suggested_params = self._get_prosody_params(result)
        
        # Cache result
        if self.config.cache_results:
            if len(self._cache) >= self.config.max_cache_size:
                # Simple cache eviction - remove first item
                self._cache.pop(next(iter(self._cache)))
            self._cache[text] = result
        
        return result
    
    def _analyze_transformer(self, text: str) -> EmotionResult:
        """Analyze using transformer model."""
        predictions = self._model(text)
        
        if not predictions or not predictions[0]:
            return EmotionResult(
                primary=EmotionCategory.NEUTRAL,
                intensity=0.0,
                confidence=1.0,
            )
        
        # Map model labels to our categories
        top_pred = predictions[0][0]
        primary = self._map_label(top_pred["label"])
        intensity = top_pred["score"]
        
        # Secondary emotion
        secondary = None
        secondary_intensity = 0.0
        
        if self.config.detect_secondary and len(predictions[0]) > 1:
            second_pred = predictions[0][1]
            if second_pred["score"] > self.config.intensity_threshold:
                secondary = self._map_label(second_pred["label"])
                secondary_intensity = second_pred["score"]
        
        return EmotionResult(
            primary=primary,
            intensity=intensity,
            secondary=secondary,
            secondary_intensity=secondary_intensity,
            confidence=top_pred["score"],
            sentiment_score=self._calculate_sentiment(primary, intensity),
        )
    
    def _analyze_keywords(self, text: str) -> EmotionResult:
        """Fallback keyword-based analysis."""
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        emotion_scores: dict[EmotionCategory, list[str]] = {
            em: [] for em in EMOTION_KEYWORDS
        }
        
        for word in words:
            for emotion, keywords in EMOTION_KEYWORDS.items():
                if word in keywords:
                    emotion_scores[emotion].append(word)
        
        # Find dominant emotion
        best_emotion = EmotionCategory.NEUTRAL
        best_count = 0
        trigger_words = []
        
        for emotion, matched in emotion_scores.items():
            if len(matched) > best_count:
                best_count = len(matched)
                best_emotion = emotion
                trigger_words = matched
        
        # Calculate intensity based on keyword count
        intensity = min(1.0, best_count * 0.2) if best_count > 0 else 0.0
        
        # Check for intensifiers
        intensifiers = ["very", "so", "extremely", "really", "absolutely", "totally"]
        for intensifier in intensifiers:
            if intensifier in words:
                intensity = min(1.0, intensity * 1.3)
        
        # Check for punctuation emphasis
        if "!" in text:
            intensity = min(1.0, intensity * 1.2)
        if text.isupper() and len(text) > 3:
            intensity = min(1.0, intensity * 1.3)
        
        return EmotionResult(
            primary=best_emotion,
            intensity=intensity,
            confidence=0.7 if best_count > 0 else 1.0,
            trigger_words=trigger_words,
            sentiment_score=self._calculate_sentiment(best_emotion, intensity),
        )
    
    def _map_label(self, label: str) -> EmotionCategory:
        """Map model labels to EmotionCategory."""
        label_mapping = {
            "joy": EmotionCategory.JOY,
            "happiness": EmotionCategory.JOY,
            "sadness": EmotionCategory.SADNESS,
            "anger": EmotionCategory.ANGER,
            "fear": EmotionCategory.FEAR,
            "surprise": EmotionCategory.SURPRISE,
            "disgust": EmotionCategory.DISGUST,
            "neutral": EmotionCategory.NEUTRAL,
        }
        return label_mapping.get(label.lower(), EmotionCategory.NEUTRAL)
    
    def _get_prosody_params(self, result: EmotionResult) -> ProsodyParams:
        """Get prosody parameters based on emotion result."""
        base_params = self._prosody_map.get(
            result.primary,
            ProsodyParams(),
        )
        
        # Scale by intensity
        scaled = ProsodyParams(
            pitch=1.0 + (base_params.pitch - 1.0) * result.intensity,
            speed=1.0 + (base_params.speed - 1.0) * result.intensity,
            energy=1.0 + (base_params.energy - 1.0) * result.intensity,
            pitch_variation=1.0 + (base_params.pitch_variation - 1.0) * result.intensity,
            pause_scale=1.0 + (base_params.pause_scale - 1.0) * result.intensity,
        )
        
        # Blend with secondary emotion if present
        if result.secondary and result.secondary_intensity > 0.2:
            secondary_params = self._prosody_map.get(
                result.secondary,
                ProsodyParams(),
            )
            blend_factor = result.secondary_intensity * 0.3
            
            scaled = ProsodyParams(
                pitch=scaled.pitch * (1 - blend_factor) + secondary_params.pitch * blend_factor,
                speed=scaled.speed * (1 - blend_factor) + secondary_params.speed * blend_factor,
                energy=scaled.energy * (1 - blend_factor) + secondary_params.energy * blend_factor,
                pitch_variation=scaled.pitch_variation * (1 - blend_factor) + secondary_params.pitch_variation * blend_factor,
                pause_scale=scaled.pause_scale * (1 - blend_factor) + secondary_params.pause_scale * blend_factor,
            )
        
        return scaled
    
    def _calculate_sentiment(self, emotion: EmotionCategory, intensity: float) -> float:
        """Calculate sentiment score from emotion."""
        sentiment_map = {
            EmotionCategory.JOY: 1.0,
            EmotionCategory.EXCITEMENT: 0.9,
            EmotionCategory.CONTENTMENT: 0.6,
            EmotionCategory.SURPRISE: 0.3,
            EmotionCategory.NEUTRAL: 0.0,
            EmotionCategory.ANXIETY: -0.3,
            EmotionCategory.FEAR: -0.5,
            EmotionCategory.SADNESS: -0.7,
            EmotionCategory.FRUSTRATION: -0.6,
            EmotionCategory.ANGER: -0.8,
            EmotionCategory.DISGUST: -0.9,
        }
        return sentiment_map.get(emotion, 0.0) * intensity
    
    def batch_analyze(self, texts: list[str]) -> list[EmotionResult]:
        """Analyze multiple texts efficiently."""
        results = []
        for text in texts:
            results.append(self.analyze(text))
        return results
