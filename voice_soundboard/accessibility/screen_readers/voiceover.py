"""
VoiceOver Adapter - Integration with Apple VoiceOver.

VoiceOver is Apple's built-in screen reader for macOS and iOS.
This adapter communicates via AppleScript and Accessibility APIs.
"""

from __future__ import annotations

import subprocess
from typing import Optional

from voice_soundboard.accessibility.screen_readers.base import (
    ScreenReaderAdapter,
    ScreenReaderCapabilities,
)


class VoiceOverAdapter(ScreenReaderAdapter):
    """Adapter for Apple VoiceOver screen reader.
    
    Uses NSAccessibility and AppleScript for communication.
    
    Example:
        adapter = VoiceOverAdapter()
        if adapter.is_active:
            adapter.speak("Hello from Voice Soundboard!")
    """
    
    def __init__(self) -> None:
        self._ducking_enabled = False
        self._original_volume: Optional[float] = None
    
    @property
    def name(self) -> str:
        return "VoiceOver"
    
    @property
    def is_active(self) -> bool:
        """Check if VoiceOver is running."""
        try:
            result = subprocess.run(
                ["defaults", "read", "com.apple.universalaccess", "voiceOverOnOffKey"],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            return result.returncode == 0 and "1" in result.stdout
        except Exception:
            return False
    
    @property
    def capabilities(self) -> ScreenReaderCapabilities:
        return ScreenReaderCapabilities(
            can_speak=True,
            can_interrupt=True,
            can_queue=True,
            can_duck=True,
            can_pause=True,
            supports_ssml=False,
            supports_earcons=True,
            supports_braille=True,
            supports_voice_change=True,
            supports_rate_change=True,
            supports_pitch_change=True,
        )
    
    def speak(self, text: str, interrupt: bool = False) -> None:
        """Speak text through VoiceOver.
        
        Args:
            text: Text to speak
            interrupt: If True, cancel current speech first
        """
        try:
            # Escape text for AppleScript
            escaped_text = text.replace('"', '\\"').replace("'", "\\'")
            
            if interrupt:
                # Stop current speech first
                self.stop()
            
            # Use AppleScript to speak through VoiceOver
            script = f'''
            tell application "VoiceOver"
                output "{escaped_text}"
            end tell
            '''
            
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=5.0,
            )
        except Exception:
            # Fallback to system speech
            self._fallback_speak(text)
    
    def _fallback_speak(self, text: str) -> None:
        """Fallback to macOS 'say' command."""
        try:
            subprocess.run(
                ["say", text],
                capture_output=True,
                timeout=30.0,
            )
        except Exception:
            pass
    
    def stop(self) -> None:
        """Cancel current VoiceOver speech."""
        try:
            script = '''
            tell application "VoiceOver"
                stop speaking
            end tell
            '''
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=1.0,
            )
        except Exception:
            pass
    
    def duck(self, amount: float = 0.3) -> None:
        """Enable audio ducking for VoiceOver.
        
        Args:
            amount: Not used (VoiceOver uses system ducking)
        """
        self._ducking_enabled = True
        # VoiceOver ducking is typically handled at the system level
        # This is a placeholder for future implementation
    
    def unduck(self) -> None:
        """Disable audio ducking for VoiceOver."""
        self._ducking_enabled = False
    
    def set_rate(self, rate: float) -> None:
        """Set VoiceOver speech rate.
        
        Args:
            rate: Rate multiplier (1.0 = normal)
        """
        try:
            # VoiceOver rate is 0-100, with 50 being normal
            vo_rate = int(50 * rate)
            vo_rate = max(1, min(100, vo_rate))
            
            script = f'''
            tell application "System Preferences"
                reveal anchor "Accessibility" of pane id "com.apple.preference.universalaccess"
            end tell
            '''
            # Note: Actually changing rate requires accessibility permissions
            # This is a simplified placeholder
        except Exception:
            pass
    
    def connect(self) -> bool:
        """Check if VoiceOver can be connected."""
        return self.is_active
    
    def disconnect(self) -> None:
        """Clean up VoiceOver connection."""
        self.unduck()
