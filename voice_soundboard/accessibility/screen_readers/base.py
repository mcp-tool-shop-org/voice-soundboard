"""
Screen Reader Base - Abstract adapter and common types.

This module defines the protocol that all screen reader adapters must
implement, ensuring consistent behavior across different assistive
technologies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class ScreenReaderMode(Enum):
    """Screen reader detection/selection mode."""
    AUTO = auto()      # Auto-detect active screen reader
    NVDA = auto()      # Force NVDA
    JAWS = auto()      # Force JAWS
    VOICEOVER = auto() # Force VoiceOver
    NARRATOR = auto()  # Force Windows Narrator
    ORCA = auto()      # Force Orca (Linux)
    NONE = auto()      # Disable screen reader integration


@dataclass
class ScreenReaderCapabilities:
    """Capabilities of a screen reader adapter.
    
    Used to determine what features are available with the
    current screen reader.
    """
    # Speech
    can_speak: bool = True
    can_interrupt: bool = True
    can_queue: bool = True
    
    # Audio
    can_duck: bool = False
    can_pause: bool = False
    
    # Advanced
    supports_ssml: bool = False
    supports_earcons: bool = False
    supports_braille: bool = False
    
    # Customization
    supports_voice_change: bool = False
    supports_rate_change: bool = True
    supports_pitch_change: bool = False


class ScreenReaderAdapter(ABC):
    """Abstract base class for screen reader adapters.
    
    Each screen reader (NVDA, JAWS, VoiceOver, etc.) should have
    its own adapter that implements this interface.
    
    Adapters handle:
    - Detection of the screen reader
    - Speaking text to the user
    - Managing audio focus (ducking)
    - Screen reader-specific features
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the screen reader."""
        ...
    
    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Check if this screen reader is currently running."""
        ...
    
    @property
    def capabilities(self) -> ScreenReaderCapabilities:
        """Get the capabilities of this adapter."""
        return ScreenReaderCapabilities()
    
    @abstractmethod
    def speak(self, text: str, interrupt: bool = False) -> None:
        """Speak text through the screen reader.
        
        Args:
            text: Text to speak
            interrupt: If True, interrupt current speech
        """
        ...
    
    def stop(self) -> None:
        """Stop current speech."""
        pass  # Optional: not all screen readers support this
    
    def duck(self, amount: float = 0.3) -> None:
        """Reduce screen reader volume temporarily.
        
        Args:
            amount: Volume multiplier (0.0-1.0)
        """
        pass  # Optional: not all screen readers support this
    
    def unduck(self) -> None:
        """Restore screen reader volume to normal."""
        pass  # Optional: not all screen readers support this
    
    def set_rate(self, rate: float) -> None:
        """Set speech rate.
        
        Args:
            rate: Rate multiplier (1.0 = normal)
        """
        pass  # Optional
    
    def connect(self) -> bool:
        """Establish connection to the screen reader.
        
        Returns:
            True if connection successful
        """
        return True
    
    def disconnect(self) -> None:
        """Clean up connection to the screen reader."""
        pass


class NullScreenReaderAdapter(ScreenReaderAdapter):
    """No-op adapter when no screen reader is active.
    
    Used as a fallback to avoid null checks throughout the code.
    """
    
    @property
    def name(self) -> str:
        return "None"
    
    @property
    def is_active(self) -> bool:
        return False
    
    def speak(self, text: str, interrupt: bool = False) -> None:
        pass  # No-op
