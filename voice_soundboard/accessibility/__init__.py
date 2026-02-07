"""
Accessibility & Inclusive Audio for Voice Soundboard v2.6.

Modular accessibility features that can be expanded independently:

Modules:
    bridge          - Core accessibility bridge and AT detection
    screen_readers  - NVDA, JAWS, VoiceOver, Narrator adapters
    descriptions    - Audio description generation and tracks
    captions        - Caption/transcript generation and display
    motor           - Voice commands, switch control, reduced interaction
    visual          - Waveforms, indicators, haptics
    cognitive       - Plain language, reading assistance
    navigation      - Landmarks, table nav, document structure
    testing         - Accessibility auditing and testing tools
    i18n            - Internationalization accessibility (RTL, multi-lang)

Example:
    from voice_soundboard.accessibility import AccessibilityBridge
    
    bridge = AccessibilityBridge()
    engine = VoiceEngine(Config(accessibility=bridge))
    
    # Screen reader aware synthesis
    result = engine.speak("Hello world!")
"""

from voice_soundboard.accessibility.bridge import (
    AccessibilityBridge,
    AccessibilityConfig,
    Announcement,
    AnnouncementPriority,
)
from voice_soundboard.accessibility.screen_readers import (
    ScreenReaderMode,
    ScreenReaderAdapter,
)
from voice_soundboard.accessibility.descriptions import (
    AudioDescriber,
    DescriptionTrack,
    DescriptionStyle,
)
from voice_soundboard.accessibility.captions import (
    CaptionGenerator,
    CaptionFormat,
    LiveCaptions,
    TranscriptExporter,
)

__all__ = [
    # Bridge (core)
    "AccessibilityBridge",
    "AccessibilityConfig",
    "Announcement",
    "AnnouncementPriority",
    # Screen readers
    "ScreenReaderMode",
    "ScreenReaderAdapter",
    # Descriptions
    "AudioDescriber",
    "DescriptionTrack",
    "DescriptionStyle",
    # Captions
    "CaptionGenerator",
    "CaptionFormat",
    "LiveCaptions",
    "TranscriptExporter",
]
