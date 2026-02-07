"""
Voice and Preset definitions.

This module contains the canonical voice catalog and preset mappings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class VoiceInfo:
    """Metadata about a voice."""
    id: str
    name: str
    gender: Literal["male", "female", "neutral"]
    accent: str
    style: str
    language: str = "en"


# Kokoro voices (primary engine)
VOICES: dict[str, VoiceInfo] = {
    # American Female
    "af_alloy": VoiceInfo("af_alloy", "Alloy", "female", "american", "balanced"),
    "af_aoede": VoiceInfo("af_aoede", "Aoede", "female", "american", "musical"),
    "af_bella": VoiceInfo("af_bella", "Bella", "female", "american", "warm"),
    "af_heart": VoiceInfo("af_heart", "Heart", "female", "american", "caring"),
    "af_jessica": VoiceInfo("af_jessica", "Jessica", "female", "american", "professional"),
    "af_kore": VoiceInfo("af_kore", "Kore", "female", "american", "youthful"),
    "af_nicole": VoiceInfo("af_nicole", "Nicole", "female", "american", "soft"),
    "af_nova": VoiceInfo("af_nova", "Nova", "female", "american", "bright"),
    "af_river": VoiceInfo("af_river", "River", "female", "american", "calm"),
    "af_sarah": VoiceInfo("af_sarah", "Sarah", "female", "american", "clear"),
    "af_sky": VoiceInfo("af_sky", "Sky", "female", "american", "airy"),

    # American Male
    "am_adam": VoiceInfo("am_adam", "Adam", "male", "american", "neutral"),
    "am_echo": VoiceInfo("am_echo", "Echo", "male", "american", "resonant"),
    "am_eric": VoiceInfo("am_eric", "Eric", "male", "american", "confident"),
    "am_fenrir": VoiceInfo("am_fenrir", "Fenrir", "male", "american", "powerful"),
    "am_liam": VoiceInfo("am_liam", "Liam", "male", "american", "friendly"),
    "am_michael": VoiceInfo("am_michael", "Michael", "male", "american", "deep"),
    "am_onyx": VoiceInfo("am_onyx", "Onyx", "male", "american", "smooth"),
    "am_puck": VoiceInfo("am_puck", "Puck", "male", "american", "playful"),
    "am_santa": VoiceInfo("am_santa", "Santa", "male", "american", "jolly"),

    # British Female
    "bf_alice": VoiceInfo("bf_alice", "Alice", "female", "british", "proper"),
    "bf_emma": VoiceInfo("bf_emma", "Emma", "female", "british", "refined"),
    "bf_isabella": VoiceInfo("bf_isabella", "Isabella", "female", "british", "warm"),
    "bf_lily": VoiceInfo("bf_lily", "Lily", "female", "british", "gentle"),

    # British Male
    "bm_daniel": VoiceInfo("bm_daniel", "Daniel", "male", "british", "sophisticated"),
    "bm_fable": VoiceInfo("bm_fable", "Fable", "male", "british", "storytelling"),
    "bm_george": VoiceInfo("bm_george", "George", "male", "british", "authoritative"),
    "bm_lewis": VoiceInfo("bm_lewis", "Lewis", "male", "british", "friendly"),
}


@dataclass(frozen=True)
class PresetConfig:
    """A named voice preset with defaults."""
    name: str
    voice: str
    speed: float
    description: str


PRESETS: dict[str, PresetConfig] = {
    "assistant": PresetConfig(
        name="assistant",
        voice="af_bella",
        speed=1.0,
        description="Friendly, helpful, conversational",
    ),
    "narrator": PresetConfig(
        name="narrator",
        voice="bm_george",
        speed=0.95,
        description="Calm, clear, documentary style",
    ),
    "announcer": PresetConfig(
        name="announcer",
        voice="am_michael",
        speed=1.1,
        description="Bold, energetic, broadcast style",
    ),
    "storyteller": PresetConfig(
        name="storyteller",
        voice="bf_emma",
        speed=0.9,
        description="Expressive, varied pacing",
    ),
    "whisper": PresetConfig(
        name="whisper",
        voice="af_nicole",
        speed=0.85,
        description="Soft, intimate, gentle",
    ),
}


def find_voice_by_style(
    style_prefer: list[str] | None = None,
    gender: str | None = None,
    accent: str | None = None,
) -> str | None:
    """Find best matching voice based on preferences.
    
    Returns voice ID or None if no match.
    """
    best_voice = None
    best_score = 0
    
    for voice_id, info in VOICES.items():
        score = 0
        
        if gender and info.gender == gender:
            score += 10
        
        if accent and info.accent == accent:
            score += 5
        
        if style_prefer:
            if info.style in style_prefer:
                score += 3
        
        if score > best_score:
            best_score = score
            best_voice = voice_id
    
    return best_voice
