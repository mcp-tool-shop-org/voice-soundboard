"""
Speaker configuration for conversations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SpeakerStylePreset(Enum):
    """Pre-defined speaking styles."""
    
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    EXCITED = "excited"
    CALM = "calm"
    AUTHORITATIVE = "authoritative"


@dataclass
class SpeakerStyle:
    """Detailed style configuration for a speaker.
    
    Attributes:
        pitch: Pitch adjustment (1.0 = normal)
        speed: Speech speed multiplier (1.0 = normal)
        emotion: Emotion/style string (e.g., "excited", "calm")
        energy: Energy level (1.0 = normal)
        preset: Optional preset style
    """
    pitch: float = 1.0
    speed: float = 1.0
    emotion: str = "neutral"
    energy: float = 1.0
    preset: SpeakerStylePreset | None = None


@dataclass
class Speaker:
    """Configuration for a conversation speaker.
    
    Attributes:
        name: Display name for the speaker.
        voice: Voice identifier for TTS.
        style: Speaking style configuration.
        language: Language code (e.g., "en").
        speed: Speech speed multiplier.
        pitch: Pitch adjustment.
        volume: Volume level (0-1).
        custom_params: Additional backend-specific parameters.
    
    Example:
        speaker = Speaker(
            name="Alice",
            voice="af_bella",
            style=SpeakerStyle(pitch=1.1, emotion="friendly"),
        )
    """
    
    name: str = ""
    voice: str | None = None
    style: SpeakerStyle | SpeakerStylePreset | str | None = None
    language: str = "en"
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    custom_params: dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    description: str = ""
    avatar_url: str = ""
    
    def __post_init__(self):
        if isinstance(self.style, str):
            try:
                self.style = SpeakerStylePreset(self.style)
            except ValueError:
                # Keep as string for custom styles
                pass
    
    @property
    def emotion(self) -> str:
        """Get emotion string from style."""
        if isinstance(self.style, SpeakerStylePreset):
            return self.style.value
        elif isinstance(self.style, SpeakerStyle):
            return self.style.emotion
        elif self.style is None:
            return "neutral"
        return str(self.style)
    
    def with_style(self, style: SpeakerStyle | str) -> "Speaker":
        """Create a copy with different style.
        
        Args:
            style: New speaking style.
        
        Returns:
            New Speaker instance.
        """
        return Speaker(
            voice=self.voice,
            name=self.name,
            style=style,
            speed=self.speed,
            pitch=self.pitch,
            volume=self.volume,
            custom_params=self.custom_params.copy(),
            description=self.description,
            avatar_url=self.avatar_url,
        )
    
    def with_speed(self, speed: float) -> "Speaker":
        """Create a copy with different speed.
        
        Args:
            speed: New speed multiplier.
        
        Returns:
            New Speaker instance.
        """
        return Speaker(
            voice=self.voice,
            name=self.name,
            style=self.style,
            speed=speed,
            pitch=self.pitch,
            volume=self.volume,
            custom_params=self.custom_params.copy(),
            description=self.description,
            avatar_url=self.avatar_url,
        )
    
    def to_compile_params(self) -> dict[str, Any]:
        """Convert to parameters for compilation.
        
        Returns:
            Dictionary for compile_request().
        """
        params = {
            "voice": self.voice,
            "emotion": self.emotion,
        }
        
        if self.speed != 1.0:
            params["speed"] = self.speed
        
        if self.pitch != 1.0:
            params["pitch"] = self.pitch
        
        params.update(self.custom_params)
        
        return params
