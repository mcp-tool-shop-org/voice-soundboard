"""
Screen Reader Adapters - Modular AT integration.

Each screen reader has its own adapter module that can be developed
and tested independently:

- nvda.py      - NVDA (Windows)
- jaws.py      - JAWS (Windows)  
- voiceover.py - VoiceOver (macOS/iOS)
- narrator.py  - Windows Narrator
- orca.py      - Orca (Linux)

The adapters follow a common protocol, making it easy to add new
screen readers without modifying existing code.
"""

from voice_soundboard.accessibility.screen_readers.base import (
    ScreenReaderAdapter,
    ScreenReaderMode,
    ScreenReaderCapabilities,
)
from voice_soundboard.accessibility.screen_readers.detection import (
    detect_screen_reader,
    get_available_adapters,
)

__all__ = [
    "ScreenReaderAdapter",
    "ScreenReaderMode",
    "ScreenReaderCapabilities",
    "detect_screen_reader",
    "get_available_adapters",
]
