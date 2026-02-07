"""
Accessibility Bridge - Core AT integration layer.

This module provides the central coordination point for all accessibility
features. It can be used standalone or composed with specific adapters.

The bridge is designed to be:
- Pluggable: Swap out screen reader adapters without changing code
- Observable: Hook into accessibility events
- Configurable: Fine-tune behavior per use case
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional, Protocol, runtime_checkable
from collections import deque


class AnnouncementPriority(Enum):
    """Priority levels for screen reader announcements.
    
    Based on ARIA live region politeness levels.
    """
    OFF = auto()        # Not announced (decorative)
    POLITE = auto()     # Queued after current speech
    ASSERTIVE = auto()  # Interrupts current speech


@dataclass
class Announcement:
    """A queued announcement for assistive technology.
    
    Attributes:
        text: The text to announce
        priority: How urgently to announce
        clear_queue: Whether to clear pending announcements
        language: Optional language override (BCP-47)
        source: Optional source identifier for debugging
    """
    text: str
    priority: AnnouncementPriority = AnnouncementPriority.POLITE
    clear_queue: bool = False
    language: Optional[str] = None
    source: Optional[str] = None


@dataclass
class AccessibilityConfig:
    """Configuration for the accessibility bridge.
    
    All options have sensible defaults and can be overridden.
    """
    # Screen reader integration
    auto_detect_screen_reader: bool = True
    announce_progress: bool = True
    progress_interval_percent: int = 25
    
    # Audio focus
    duck_screen_reader: bool = True
    duck_amount: float = 0.3
    
    # Announcements
    default_priority: AnnouncementPriority = AnnouncementPriority.POLITE
    announcement_prefix: str = ""  # e.g., "Voice Soundboard: "
    announcement_suffix: str = ""
    
    # Timing
    min_announcement_gap_ms: int = 250
    announcement_timeout_ms: int = 10000


@runtime_checkable
class AccessibilityListener(Protocol):
    """Protocol for accessibility event listeners."""
    
    def on_announcement(self, announcement: Announcement) -> None:
        """Called when an announcement is made."""
        ...
    
    def on_synthesis_start(self, text: str) -> None:
        """Called when synthesis begins."""
        ...
    
    def on_synthesis_end(self, duration_ms: float) -> None:
        """Called when synthesis completes."""
        ...


class AccessibilityBridge:
    """Central coordination point for accessibility features.
    
    The bridge manages:
    - Screen reader detection and communication
    - Announcement queuing and delivery
    - Audio focus management
    - Event distribution to listeners
    
    Example:
        bridge = AccessibilityBridge()
        
        # Auto-detects screen readers
        if bridge.screen_reader_active:
            print(f"Using: {bridge.screen_reader_name}")
        
        # Make announcements
        bridge.announce("Processing started")
        
        # Connect to engine
        engine = VoiceEngine(Config(accessibility=bridge))
    """
    
    def __init__(
        self,
        config: Optional[AccessibilityConfig] = None,
        adapter: Optional["ScreenReaderAdapter"] = None,
    ) -> None:
        """Initialize the accessibility bridge.
        
        Args:
            config: Configuration options (uses defaults if None)
            adapter: Specific screen reader adapter (auto-detects if None)
        """
        self.config = config or AccessibilityConfig()
        self._adapter = adapter
        self._listeners: list[AccessibilityListener] = []
        self._announcement_queue: deque[Announcement] = deque(maxlen=100)
        self._is_speaking = False
        self._last_announcement_time: float = 0
        
        # Lazy initialization of adapter
        self._adapter_initialized = False
    
    @property
    def screen_reader_active(self) -> bool:
        """Check if a screen reader is currently active."""
        self._ensure_adapter()
        return self._adapter is not None and self._adapter.is_active
    
    @property
    def screen_reader_name(self) -> Optional[str]:
        """Get the name of the active screen reader."""
        self._ensure_adapter()
        return self._adapter.name if self._adapter else None
    
    def _ensure_adapter(self) -> None:
        """Lazily initialize the screen reader adapter."""
        if self._adapter_initialized:
            return
        
        self._adapter_initialized = True
        
        if self._adapter is None and self.config.auto_detect_screen_reader:
            self._adapter = _detect_screen_reader()
    
    def announce(
        self,
        text: str,
        priority: Optional[AnnouncementPriority] = None,
        clear_queue: bool = False,
    ) -> None:
        """Queue an announcement for the screen reader.
        
        Args:
            text: Text to announce
            priority: Announcement priority (uses config default if None)
            clear_queue: Whether to clear pending announcements first
        """
        announcement = Announcement(
            text=self._format_announcement(text),
            priority=priority or self.config.default_priority,
            clear_queue=clear_queue,
        )
        
        if clear_queue:
            self._announcement_queue.clear()
        
        self._announcement_queue.append(announcement)
        self._deliver_announcement(announcement)
        
        # Notify listeners
        for listener in self._listeners:
            try:
                listener.on_announcement(announcement)
            except Exception:
                pass  # Don't let listener errors break announcements
    
    def _format_announcement(self, text: str) -> str:
        """Apply prefix/suffix to announcement text."""
        prefix = self.config.announcement_prefix
        suffix = self.config.announcement_suffix
        return f"{prefix}{text}{suffix}"
    
    def _deliver_announcement(self, announcement: Announcement) -> None:
        """Deliver announcement to the screen reader adapter."""
        self._ensure_adapter()
        
        if self._adapter and announcement.priority != AnnouncementPriority.OFF:
            self._adapter.speak(
                announcement.text,
                interrupt=(announcement.priority == AnnouncementPriority.ASSERTIVE),
            )
    
    def add_listener(self, listener: AccessibilityListener) -> None:
        """Add a listener for accessibility events."""
        if listener not in self._listeners:
            self._listeners.append(listener)
    
    def remove_listener(self, listener: AccessibilityListener) -> None:
        """Remove an accessibility event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def on_synthesis_start(self, text: str) -> None:
        """Called when synthesis begins (for engine integration)."""
        self._is_speaking = True
        
        if self.config.duck_screen_reader and self._adapter:
            self._adapter.duck(self.config.duck_amount)
        
        for listener in self._listeners:
            try:
                listener.on_synthesis_start(text)
            except Exception:
                pass
    
    def on_synthesis_end(self, duration_ms: float) -> None:
        """Called when synthesis completes (for engine integration)."""
        self._is_speaking = False
        
        if self.config.duck_screen_reader and self._adapter:
            self._adapter.unduck()
        
        for listener in self._listeners:
            try:
                listener.on_synthesis_end(duration_ms)
            except Exception:
                pass
    
    def on_progress(self, percent: int) -> None:
        """Called during long operations to announce progress."""
        if not self.config.announce_progress:
            return
        
        interval = self.config.progress_interval_percent
        if percent > 0 and percent % interval == 0 and percent < 100:
            self.announce(f"{percent}% complete", AnnouncementPriority.POLITE)


# Lazy import to avoid circular dependencies
def _detect_screen_reader() -> Optional["ScreenReaderAdapter"]:
    """Auto-detect and return appropriate screen reader adapter."""
    from voice_soundboard.accessibility.screen_readers import detect_screen_reader
    return detect_screen_reader()


# Type alias for adapter (defined in screen_readers module)
ScreenReaderAdapter = Any  # Will be properly typed when screen_readers is imported
