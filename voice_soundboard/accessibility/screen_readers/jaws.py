"""
JAWS Adapter - Integration with JAWS screen reader.

JAWS (Job Access With Speech) is a commercial screen reader for Windows.
This adapter communicates via the JAWS COM automation interface.
"""

from __future__ import annotations

from typing import Any, Optional

from voice_soundboard.accessibility.screen_readers.base import (
    ScreenReaderAdapter,
    ScreenReaderCapabilities,
)


class JAWSAdapter(ScreenReaderAdapter):
    """Adapter for JAWS screen reader.
    
    Uses COM automation to communicate with JAWS.
    
    Example:
        adapter = JAWSAdapter()
        if adapter.is_active:
            adapter.speak("Hello from Voice Soundboard!")
    """
    
    def __init__(self) -> None:
        self._jaws: Optional[Any] = None
        self._connected = False
        self._load_jaws()
    
    def _load_jaws(self) -> None:
        """Attempt to connect to JAWS via COM."""
        try:
            import comtypes.client
            self._jaws = comtypes.client.CreateObject("FreedomSci.JawsApi")
            self._connected = True
        except Exception:
            # JAWS not installed or COM not available
            self._jaws = None
            self._connected = False
    
    @property
    def name(self) -> str:
        return "JAWS"
    
    @property
    def is_active(self) -> bool:
        """Check if JAWS is running."""
        if not self._jaws:
            return False
        
        try:
            # Try to call a method to verify JAWS is responsive
            return self._jaws.IsRunning()
        except Exception:
            return False
    
    @property
    def capabilities(self) -> ScreenReaderCapabilities:
        return ScreenReaderCapabilities(
            can_speak=True,
            can_interrupt=True,
            can_queue=True,
            can_duck=True,  # JAWS supports ducking
            can_pause=True,
            supports_ssml=False,
            supports_earcons=True,
            supports_braille=True,
            supports_voice_change=True,
            supports_rate_change=True,
            supports_pitch_change=True,
        )
    
    def speak(self, text: str, interrupt: bool = False) -> None:
        """Speak text through JAWS.
        
        Args:
            text: Text to speak
            interrupt: If True, cancel current speech first
        """
        if not self._jaws:
            return
        
        try:
            if interrupt:
                self._jaws.StopSpeech()
            
            # SayString(text, flush)
            # flush=True means interrupt, flush=False means queue
            self._jaws.SayString(text, interrupt)
        except Exception:
            pass
    
    def stop(self) -> None:
        """Cancel current JAWS speech."""
        if self._jaws:
            try:
                self._jaws.StopSpeech()
            except Exception:
                pass
    
    def duck(self, amount: float = 0.3) -> None:
        """Reduce JAWS volume.
        
        Args:
            amount: Volume level (0.0-1.0)
        """
        if self._jaws:
            try:
                # JAWS volume is 0-100
                volume = int(amount * 100)
                self._jaws.SetVolume(volume)
            except Exception:
                pass
    
    def unduck(self) -> None:
        """Restore JAWS volume to 100%."""
        if self._jaws:
            try:
                self._jaws.SetVolume(100)
            except Exception:
                pass
    
    def run_script(self, script_name: str) -> None:
        """Run a JAWS script by name.
        
        Args:
            script_name: Name of the JAWS script to execute
        """
        if self._jaws:
            try:
                self._jaws.RunScript(script_name)
            except Exception:
                pass
    
    def connect(self) -> bool:
        """Ensure connection to JAWS."""
        if not self._connected:
            self._load_jaws()
        return self._connected
    
    def disconnect(self) -> None:
        """Release JAWS COM object."""
        self._jaws = None
        self._connected = False
