"""
Emotion Compiler - Transform emotion names into prosody modifiers.

Emotions are compile-time concepts. After apply_emotion(), the emotion
name is gone - only pitch/speed/energy modifiers remain in the graph.
"""

from __future__ import annotations

from dataclasses import dataclass

from voice_soundboard.graph import TokenEvent


@dataclass(frozen=True)
class EmotionProfile:
    """How an emotion affects prosody."""
    name: str
    
    # Prosody multipliers (1.0 = neutral)
    speed: float = 1.0
    pitch: float = 1.0
    energy: float = 1.0
    
    # Voice preference (optional)
    voice_style_prefer: tuple[str, ...] = ()
    
    # Pause modifier
    pause_multiplier: float = 1.0


EMOTIONS: dict[str, EmotionProfile] = {
    # Neutral
    "neutral": EmotionProfile("neutral"),
    
    # Positive / High energy
    "happy": EmotionProfile(
        "happy",
        speed=1.1,
        pitch=1.05,
        energy=1.1,
        voice_style_prefer=("warm", "friendly", "bright"),
    ),
    "excited": EmotionProfile(
        "excited",
        speed=1.2,
        pitch=1.1,
        energy=1.2,
        voice_style_prefer=("bright", "energetic"),
    ),
    "joyful": EmotionProfile(
        "joyful",
        speed=1.15,
        pitch=1.08,
        energy=1.15,
        voice_style_prefer=("warm", "bright"),
    ),
    "enthusiastic": EmotionProfile(
        "enthusiastic",
        speed=1.15,
        pitch=1.05,
        energy=1.15,
        voice_style_prefer=("bright", "friendly"),
    ),
    
    # Calm / Low energy
    "calm": EmotionProfile(
        "calm",
        speed=0.9,
        pitch=0.98,
        energy=0.85,
        pause_multiplier=1.2,
        voice_style_prefer=("calm", "soft", "gentle"),
    ),
    "peaceful": EmotionProfile(
        "peaceful",
        speed=0.85,
        pitch=0.95,
        energy=0.8,
        pause_multiplier=1.3,
        voice_style_prefer=("soft", "gentle"),
    ),
    "relaxed": EmotionProfile(
        "relaxed",
        speed=0.9,
        pitch=0.98,
        energy=0.9,
        pause_multiplier=1.1,
        voice_style_prefer=("calm", "warm"),
    ),
    
    # Negative
    "sad": EmotionProfile(
        "sad",
        speed=0.85,
        pitch=0.92,
        energy=0.75,
        pause_multiplier=1.3,
        voice_style_prefer=("soft", "gentle"),
    ),
    "melancholy": EmotionProfile(
        "melancholy",
        speed=0.8,
        pitch=0.9,
        energy=0.7,
        pause_multiplier=1.4,
        voice_style_prefer=("deep", "soft"),
    ),
    "angry": EmotionProfile(
        "angry",
        speed=1.1,
        pitch=1.05,
        energy=1.3,
        voice_style_prefer=("powerful", "authoritative"),
    ),
    "frustrated": EmotionProfile(
        "frustrated",
        speed=1.05,
        pitch=1.02,
        energy=1.15,
        voice_style_prefer=("confident",),
    ),
    
    # Tense
    "fearful": EmotionProfile(
        "fearful",
        speed=1.15,
        pitch=1.1,
        energy=0.9,
        pause_multiplier=0.8,
        voice_style_prefer=("soft",),
    ),
    "anxious": EmotionProfile(
        "anxious",
        speed=1.1,
        pitch=1.05,
        energy=0.95,
        pause_multiplier=0.9,
        voice_style_prefer=("soft", "youthful"),
    ),
    "surprised": EmotionProfile(
        "surprised",
        speed=1.15,
        pitch=1.12,
        energy=1.1,
        voice_style_prefer=("bright",),
    ),
    
    # Professional
    "confident": EmotionProfile(
        "confident",
        speed=1.0,
        pitch=1.0,
        energy=1.1,
        voice_style_prefer=("confident", "professional", "authoritative"),
    ),
    "serious": EmotionProfile(
        "serious",
        speed=0.95,
        pitch=0.98,
        energy=1.0,
        pause_multiplier=1.1,
        voice_style_prefer=("authoritative", "deep"),
    ),
}


def get_emotion(name: str) -> EmotionProfile:
    """Get emotion profile by name. Returns neutral if not found."""
    return EMOTIONS.get(name.lower(), EMOTIONS["neutral"])


def apply_emotion(tokens: list[TokenEvent], emotion: str) -> list[TokenEvent]:
    """Apply emotion prosody modifiers to tokens.
    
    This is a compile-time transformation. After this function,
    the emotion name is gone - only numeric modifiers remain.
    """
    profile = get_emotion(emotion)
    
    result = []
    for token in tokens:
        result.append(TokenEvent(
            text=token.text,
            phonemes=token.phonemes,
            pitch_scale=token.pitch_scale * profile.pitch,
            energy_scale=token.energy_scale * profile.energy,
            duration_scale=token.duration_scale / profile.speed,  # Slower = longer duration
            paralinguistic=token.paralinguistic,
            emphasis=token.emphasis,
            pause_after=token.pause_after * profile.pause_multiplier,
        ))
    
    return result


def list_emotions() -> list[str]:
    """List all available emotion names."""
    return list(EMOTIONS.keys())
