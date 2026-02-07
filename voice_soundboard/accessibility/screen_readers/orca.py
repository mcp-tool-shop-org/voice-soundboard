"""
Orca Adapter - Integration with Orca screen reader.

Orca is the primary screen reader for Linux/GNOME desktops.
This adapter uses D-Bus for communication.
"""

from __future__ import annotations

from typing import Any, Optional

from voice_soundboard.accessibility.screen_readers.base import (
    ScreenReaderAdapter,
    ScreenReaderCapabilities,
)


class OrcaAdapter(ScreenReaderAdapter):
    """Adapter for Orca screen reader (Linux/GNOME).
    
    Uses D-Bus and AT-SPI for communication.
    
    Example:
        adapter = OrcaAdapter()
        if adapter.is_active:
            adapter.speak("Hello from Voice Soundboard!")
    """
    
    def __init__(self) -> None:
        self._bus: Optional[Any] = None
        self._speech: Optional[Any] = None
        self._connected = False
        self._connect_dbus()
    
    def _connect_dbus(self) -> None:
        """Connect to D-Bus for AT-SPI communication."""
        try:
            import dbus
            self._bus = dbus.SessionBus()
            
            # Connect to speech-dispatcher
            self._speech = self._bus.get_object(
                "org.freedesktop.Speech.Dispatcher",
                "/org/freedesktop/Speech/Dispatcher"
            )
            self._connected = True
        except Exception:
            self._bus = None
            self._speech = None
            self._connected = False
    
    @property
    def name(self) -> str:
        return "Orca"
    
    @property
    def is_active(self) -> bool:
        """Check if Orca is running."""
        try:
            import subprocess
            result = subprocess.run(
                ["pgrep", "-x", "orca"],
                capture_output=True,
                timeout=1.0,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @property
    def capabilities(self) -> ScreenReaderCapabilities:
        return ScreenReaderCapabilities(
            can_speak=True,
            can_interrupt=True,
            can_queue=True,
            can_duck=False,
            can_pause=True,
            supports_ssml=False,
            supports_earcons=False,
            supports_braille=True,
            supports_voice_change=True,
            supports_rate_change=True,
            supports_pitch_change=True,
        )
    
    def speak(self, text: str, interrupt: bool = False) -> None:
        """Speak text through Orca/speech-dispatcher.
        
        Args:
            text: Text to speak
            interrupt: If True, cancel current speech first
        """
        # Try speech-dispatcher first
        if self._speak_via_spd(text, interrupt):
            return
        
        # Fallback to espeak
        self._speak_via_espeak(text)
    
    def _speak_via_spd(self, text: str, interrupt: bool) -> bool:
        """Speak via speech-dispatcher."""
        try:
            import speechd
            client = speechd.SSIPClient("voice-soundboard")
            
            if interrupt:
                client.cancel()
            
            client.speak(text)
            client.close()
            return True
        except Exception:
            return False
    
    def _speak_via_espeak(self, text: str) -> None:
        """Fallback to espeak command."""
        try:
            import subprocess
            subprocess.run(
                ["espeak", text],
                capture_output=True,
                timeout=30.0,
            )
        except Exception:
            pass
    
    def stop(self) -> None:
        """Cancel current speech."""
        try:
            import speechd
            client = speechd.SSIPClient("voice-soundboard")
            client.cancel()
            client.close()
        except Exception:
            pass
    
    def set_rate(self, rate: float) -> None:
        """Set speech rate.
        
        Args:
            rate: Rate multiplier (1.0 = normal)
        """
        try:
            import speechd
            client = speechd.SSIPClient("voice-soundboard")
            # speech-dispatcher rate is -100 to 100
            spd_rate = int((rate - 1.0) * 100)
            spd_rate = max(-100, min(100, spd_rate))
            client.set_rate(spd_rate)
            client.close()
        except Exception:
            pass
    
    def connect(self) -> bool:
        """Ensure D-Bus connection."""
        if not self._connected:
            self._connect_dbus()
        return self._connected
    
    def disconnect(self) -> None:
        """Clean up D-Bus connection."""
        self._bus = None
        self._speech = None
        self._connected = False
