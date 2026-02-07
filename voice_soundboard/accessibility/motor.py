"""
Motor Accessibility - Voice commands, switch control, reduced interaction.

This module provides accessibility features for users with motor
impairments, enabling hands-free and reduced-interaction control.

Components:
    VoiceCommands       - Voice-activated control
    SwitchControl       - Single/two-switch scanning interface
    ReducedInteraction  - Minimize required user actions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional


class SwitchMode(Enum):
    """Switch control mode."""
    SINGLE = auto()  # One switch: auto-scan + press to select
    TWO = auto()     # Two switches: scan + select
    STEP = auto()    # Press to advance, hold to select


@dataclass
class VoiceCommandConfig:
    """Configuration for voice commands."""
    wake_word: Optional[str] = None  # None = always listening
    language: str = "en-US"
    confirmation_mode: str = "audio"  # audio, visual, both, none
    timeout_seconds: float = 10.0
    continuous: bool = True


class VoiceCommands:
    """Voice-activated control for hands-free operation.
    
    Allows users to control Voice Soundboard entirely by voice,
    without needing keyboard or mouse input.
    
    Example:
        commands = VoiceCommands()
        
        commands.register("speak this", lambda: engine.speak(clipboard.get()))
        commands.register("stop", engine.stop)
        commands.register("slower", lambda: engine.set_speed(0.8))
        
        @commands.command("read {filename}")
        def read_file(filename: str):
            with open(filename) as f:
                engine.speak(f.read())
    """
    
    def __init__(self, config: Optional[VoiceCommandConfig] = None) -> None:
        """Initialize voice commands.
        
        Args:
            config: Voice command configuration
        """
        self.config = config or VoiceCommandConfig()
        self._commands: dict[str, Callable] = {}
        self._listening = False
        self._recognizer: Optional[Any] = None
    
    def register(self, phrase: str, callback: Callable) -> None:
        """Register a voice command.
        
        Args:
            phrase: Phrase to recognize (supports {param} placeholders)
            callback: Function to call when phrase is recognized
        """
        self._commands[phrase.lower()] = callback
    
    def unregister(self, phrase: str) -> None:
        """Unregister a voice command.
        
        Args:
            phrase: Phrase to unregister
        """
        self._commands.pop(phrase.lower(), None)
    
    def command(self, phrase: str) -> Callable:
        """Decorator to register a voice command.
        
        Args:
            phrase: Phrase to recognize
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            self.register(phrase, func)
            return func
        return decorator
    
    def start(self) -> None:
        """Start listening for voice commands."""
        self._listening = True
        # Placeholder for speech recognition integration
    
    def stop(self) -> None:
        """Stop listening for voice commands."""
        self._listening = False
    
    @property
    def is_listening(self) -> bool:
        """Check if currently listening."""
        return self._listening
    
    def get_commands(self) -> list[str]:
        """Get list of registered commands."""
        return list(self._commands.keys())


@dataclass
class SwitchAction:
    """An action available in switch control."""
    name: str
    callback: Callable[[], None]
    icon: Optional[str] = None


class SwitchControl:
    """Switch-based scanning interface for motor accessibility.
    
    Provides a scanning interface that can be controlled with
    one or two switches, suitable for users with severe motor
    impairments.
    
    Example:
        switch = SwitchControl(mode=SwitchMode.SINGLE, scan_speed_ms=1500)
        
        switch.add_action("Play", engine.play)
        switch.add_action("Pause", engine.pause)
        switch.add_action("Stop", engine.stop)
        
        switch.start()  # Begin auto-scanning
        switch.select()  # Called when switch is pressed
    """
    
    def __init__(
        self,
        mode: SwitchMode = SwitchMode.SINGLE,
        scan_speed_ms: int = 1500,
        auto_scan: bool = True,
    ) -> None:
        """Initialize switch control.
        
        Args:
            mode: Switch control mode
            scan_speed_ms: Time per item during scanning
            auto_scan: Whether to auto-advance
        """
        self.mode = mode
        self.scan_speed_ms = scan_speed_ms
        self.auto_scan = auto_scan
        self._actions: list[SwitchAction] = []
        self._current_index = 0
        self._scanning = False
    
    def add_action(
        self,
        name: str,
        callback: Callable[[], None],
        icon: Optional[str] = None,
    ) -> "SwitchControl":
        """Add an action to the scanning interface.
        
        Args:
            name: Action name (announced during scan)
            callback: Function to call when selected
            icon: Optional icon identifier
            
        Returns:
            Self for chaining
        """
        self._actions.append(SwitchAction(name, callback, icon))
        return self
    
    def remove_action(self, name: str) -> None:
        """Remove an action by name."""
        self._actions = [a for a in self._actions if a.name != name]
    
    def start(self) -> None:
        """Start scanning."""
        self._scanning = True
        self._current_index = 0
    
    def stop(self) -> None:
        """Stop scanning."""
        self._scanning = False
    
    def next(self) -> Optional[str]:
        """Advance to next action.
        
        Returns:
            Name of newly highlighted action
        """
        if not self._actions:
            return None
        
        self._current_index = (self._current_index + 1) % len(self._actions)
        return self._actions[self._current_index].name
    
    def previous(self) -> Optional[str]:
        """Go to previous action.
        
        Returns:
            Name of newly highlighted action
        """
        if not self._actions:
            return None
        
        self._current_index = (self._current_index - 1) % len(self._actions)
        return self._actions[self._current_index].name
    
    def select(self) -> None:
        """Select the current action."""
        if self._actions and 0 <= self._current_index < len(self._actions):
            self._actions[self._current_index].callback()
    
    @property
    def current_action(self) -> Optional[str]:
        """Get currently highlighted action name."""
        if self._actions and 0 <= self._current_index < len(self._actions):
            return self._actions[self._current_index].name
        return None
    
    @property
    def actions(self) -> list[str]:
        """Get list of action names."""
        return [a.name for a in self._actions]


@dataclass
class ReducedInteractionConfig:
    """Configuration for reduced interaction mode."""
    auto_play: bool = True
    auto_advance: bool = True
    pause_on_focus_loss: bool = False
    large_targets: bool = True
    dwell_click_ms: int = 1000
    confirm_destructive: bool = True
    timeout_warnings: bool = True
    timeout_extension_ms: int = 30000


class ReducedInteraction:
    """Minimize required user actions for motor accessibility.
    
    Provides settings and behaviors that reduce the number of
    actions users need to take, suitable for users with limited
    motor control.
    
    Example:
        reduced = ReducedInteraction(
            auto_play=True,
            dwell_click_ms=1000,
        )
        
        engine = VoiceEngine(Config(reduced_interaction=reduced))
    """
    
    def __init__(self, config: Optional[ReducedInteractionConfig] = None) -> None:
        """Initialize reduced interaction mode.
        
        Args:
            config: Configuration options
        """
        self.config = config or ReducedInteractionConfig()
    
    @property
    def auto_play(self) -> bool:
        """Whether to auto-play after synthesis."""
        return self.config.auto_play
    
    @property
    def auto_advance(self) -> bool:
        """Whether to auto-advance in sequences."""
        return self.config.auto_advance
    
    @property
    def large_targets(self) -> bool:
        """Whether to use larger click targets."""
        return self.config.large_targets
    
    @property
    def dwell_time_ms(self) -> int:
        """Dwell time before activation."""
        return self.config.dwell_click_ms
    
    def should_confirm(self, action: str) -> bool:
        """Check if action requires confirmation.
        
        Args:
            action: Action being performed
            
        Returns:
            True if confirmation needed
        """
        destructive_actions = {"delete", "clear", "reset", "stop_all"}
        return self.config.confirm_destructive and action.lower() in destructive_actions
