"""
Narrator Adapter - Integration with Windows Narrator.

Narrator is Microsoft's built-in screen reader for Windows.
This adapter uses UI Automation and Windows APIs.
"""

from __future__ import annotations

import ctypes
from typing import Optional

from voice_soundboard.accessibility.screen_readers.base import (
    ScreenReaderAdapter,
    ScreenReaderCapabilities,
)


class NarratorAdapter(ScreenReaderAdapter):
    """Adapter for Windows Narrator screen reader.
    
    Uses Windows UI Automation for communication.
    
    Example:
        adapter = NarratorAdapter()
        if adapter.is_active:
            adapter.speak("Hello from Voice Soundboard!")
    """
    
    def __init__(self) -> None:
        self._sapi_voice: Optional[object] = None
    
    @property
    def name(self) -> str:
        return "Narrator"
    
    @property
    def is_active(self) -> bool:
        """Check if Narrator is running."""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and 'narrator' in proc.info['name'].lower():
                    return True
            return False
        except Exception:
            # Fallback: check via Windows API
            return self._check_narrator_via_api()
    
    def _check_narrator_via_api(self) -> bool:
        """Check Narrator status via Windows API."""
        try:
            # Check if Narrator process exists
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW("NarratorHelperWindow", None)
            return hwnd != 0
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
            supports_ssml=True,  # Narrator supports some SSML
            supports_earcons=True,
            supports_braille=True,
            supports_voice_change=True,
            supports_rate_change=True,
            supports_pitch_change=True,
        )
    
    def _ensure_sapi(self) -> bool:
        """Ensure SAPI voice is initialized."""
        if self._sapi_voice is not None:
            return True
        
        try:
            import win32com.client
            self._sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
            return True
        except Exception:
            return False
    
    def speak(self, text: str, interrupt: bool = False) -> None:
        """Speak text through Narrator/SAPI.
        
        Args:
            text: Text to speak
            interrupt: If True, cancel current speech first
        """
        if not self._ensure_sapi():
            return
        
        try:
            if interrupt:
                # SVSFPurgeBeforeSpeak = 2
                self._sapi_voice.Speak(text, 2)
            else:
                # SVSFlagsAsync = 1
                self._sapi_voice.Speak(text, 1)
        except Exception:
            pass
    
    def stop(self) -> None:
        """Cancel current speech."""
        if self._sapi_voice:
            try:
                # Empty string with purge flag stops speech
                self._sapi_voice.Speak("", 2)
            except Exception:
                pass
    
    def set_rate(self, rate: float) -> None:
        """Set speech rate.
        
        Args:
            rate: Rate multiplier (1.0 = normal)
        """
        if not self._ensure_sapi():
            return
        
        try:
            # SAPI rate is -10 to 10, with 0 being normal
            sapi_rate = int((rate - 1.0) * 10)
            sapi_rate = max(-10, min(10, sapi_rate))
            self._sapi_voice.Rate = sapi_rate
        except Exception:
            pass
    
    def connect(self) -> bool:
        """Initialize SAPI connection."""
        return self._ensure_sapi()
    
    def disconnect(self) -> None:
        """Release SAPI voice."""
        self._sapi_voice = None
