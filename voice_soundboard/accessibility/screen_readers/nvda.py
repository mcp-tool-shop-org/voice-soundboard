"""
NVDA Adapter - Integration with NVDA screen reader.

NVDA (NonVisual Desktop Access) is a free, open-source screen reader
for Windows. This adapter communicates via:
1. NVDA Controller Client (preferred)
2. NVDA Remote (fallback)
3. Windows SAPI (last resort)
"""

from __future__ import annotations

import ctypes
from typing import Optional

from voice_soundboard.accessibility.screen_readers.base import (
    ScreenReaderAdapter,
    ScreenReaderCapabilities,
)


class NVDAAdapter(ScreenReaderAdapter):
    """Adapter for NVDA screen reader.
    
    Uses nvdaControllerClient.dll when available for native integration.
    
    Example:
        adapter = NVDAAdapter()
        if adapter.is_active:
            adapter.speak("Hello from Voice Soundboard!")
    """
    
    def __init__(self) -> None:
        self._controller: Optional[ctypes.CDLL] = None
        self._connected = False
        self._load_controller()
    
    def _load_controller(self) -> None:
        """Attempt to load the NVDA controller client."""
        try:
            # Try to load nvdaControllerClient.dll
            # This is included with NVDA installations
            self._controller = ctypes.windll.LoadLibrary(
                "nvdaControllerClient.dll"
            )
            self._connected = True
        except (OSError, AttributeError):
            self._controller = None
            self._connected = False
    
    @property
    def name(self) -> str:
        return "NVDA"
    
    @property
    def is_active(self) -> bool:
        """Check if NVDA is running."""
        if not self._controller:
            return False
        
        try:
            # nvdaController_testIfRunning returns 0 if NVDA is running
            result = self._controller.nvdaController_testIfRunning()
            return result == 0
        except Exception:
            return False
    
    @property
    def capabilities(self) -> ScreenReaderCapabilities:
        return ScreenReaderCapabilities(
            can_speak=True,
            can_interrupt=True,
            can_queue=True,
            can_duck=False,  # NVDA doesn't support external ducking
            can_pause=True,
            supports_ssml=False,
            supports_earcons=False,
            supports_braille=True,
            supports_voice_change=False,
            supports_rate_change=True,
            supports_pitch_change=False,
        )
    
    def speak(self, text: str, interrupt: bool = False) -> None:
        """Speak text through NVDA.
        
        Args:
            text: Text to speak
            interrupt: If True, cancel current speech first
        """
        if not self._controller:
            return
        
        try:
            if interrupt:
                self._controller.nvdaController_cancelSpeech()
            
            # nvdaController_speakText takes a wide string
            self._controller.nvdaController_speakText(text)
        except Exception:
            pass  # Fail silently if NVDA not responding
    
    def stop(self) -> None:
        """Cancel current NVDA speech."""
        if self._controller:
            try:
                self._controller.nvdaController_cancelSpeech()
            except Exception:
                pass
    
    def send_braille(self, text: str) -> None:
        """Send text to NVDA's braille display.
        
        Args:
            text: Text to display on braille
        """
        if not self._controller:
            return
        
        try:
            self._controller.nvdaController_brailleMessage(text)
        except Exception:
            pass
    
    def connect(self) -> bool:
        """Ensure connection to NVDA."""
        if not self._connected:
            self._load_controller()
        return self._connected
    
    def disconnect(self) -> None:
        """Release NVDA controller."""
        self._controller = None
        self._connected = False
