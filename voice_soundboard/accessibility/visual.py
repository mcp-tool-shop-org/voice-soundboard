"""
Visual Feedback - Waveforms, indicators, and haptics.

This module provides visual and tactile feedback for users who
benefit from non-auditory cues during audio playback.

Components:
    WaveformVisualizer  - Audio waveform display
    SpeechIndicator     - Visual speech activity indicator
    HapticFeedback      - Tactile feedback sync
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional


class VisualizationStyle(Enum):
    """Style of audio visualization."""
    WAVEFORM = auto()     # Traditional waveform
    SPECTROGRAM = auto()  # Frequency over time
    BARS = auto()         # Frequency bars
    CIRCLE = auto()       # Circular visualizer


class ColorScheme(Enum):
    """Color scheme for visualizations."""
    DEFAULT = auto()
    HIGH_CONTRAST = auto()
    MONOCHROME = auto()
    COLORBLIND_SAFE = auto()


@dataclass
class VisualizerConfig:
    """Configuration for waveform visualizer."""
    style: VisualizationStyle = VisualizationStyle.WAVEFORM
    color_scheme: ColorScheme = ColorScheme.DEFAULT
    show_amplitude: bool = True
    show_frequency: bool = False
    show_playhead: bool = True
    width: int = 800
    height: int = 200
    background_color: str = "#000000"
    foreground_color: str = "#00FF00"


class WaveformVisualizer:
    """Visual waveform display for audio.
    
    Provides real-time and static waveform visualizations,
    useful for deaf/hard-of-hearing users to see audio activity.
    
    Example:
        visualizer = WaveformVisualizer(style=VisualizationStyle.WAVEFORM)
        visualizer.attach(engine)
        
        # Export static visualization
        image = visualizer.render(result.audio, width=800, height=200)
        image.save("waveform.png")
    """
    
    def __init__(self, config: Optional[VisualizerConfig] = None) -> None:
        """Initialize waveform visualizer.
        
        Args:
            config: Visualizer configuration
        """
        self.config = config or VisualizerConfig()
        self._engine: Optional[Any] = None
        self._audio_data: Optional[bytes] = None
    
    def attach(self, engine: Any) -> None:
        """Attach to a VoiceEngine for real-time visualization.
        
        Args:
            engine: VoiceEngine to visualize
        """
        self._engine = engine
    
    def detach(self) -> None:
        """Detach from current engine."""
        self._engine = None
    
    def render(
        self,
        audio: bytes,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Any:
        """Render a static waveform image.
        
        Args:
            audio: Audio data bytes
            width: Image width (uses config if None)
            height: Image height (uses config if None)
            
        Returns:
            PIL Image or similar
        """
        w = width or self.config.width
        h = height or self.config.height
        
        # Placeholder for actual rendering
        # Would use matplotlib, PIL, or similar
        return {"width": w, "height": h, "data": audio[:100]}
    
    def get_current_amplitude(self) -> float:
        """Get current audio amplitude (0.0-1.0)."""
        # Placeholder for real-time amplitude
        return 0.0
    
    def get_current_frequency(self) -> float:
        """Get dominant frequency in Hz."""
        # Placeholder for frequency analysis
        return 0.0


class IndicatorStyle(Enum):
    """Style of speech indicator."""
    PULSING_CIRCLE = auto()
    BOUNCING_BARS = auto()
    TEXT_HIGHLIGHT = auto()
    AVATAR = auto()


@dataclass
class IndicatorConfig:
    """Configuration for speech indicator."""
    style: IndicatorStyle = IndicatorStyle.PULSING_CIRCLE
    sync_to_words: bool = True
    color_by_speaker: bool = True
    size: int = 64
    colors: dict[str, str] = field(default_factory=dict)


class SpeechIndicator:
    """Visual indicator of speech activity.
    
    Shows who is speaking and speech activity through visual
    cues, helping deaf/hard-of-hearing users follow conversations.
    
    Example:
        indicator = SpeechIndicator(
            style=IndicatorStyle.PULSING_CIRCLE,
            sync_to_words=True,
        )
        
        indicator.attach(conversation)
        # Shows visual indication of who's speaking
    """
    
    def __init__(self, config: Optional[IndicatorConfig] = None) -> None:
        """Initialize speech indicator.
        
        Args:
            config: Indicator configuration
        """
        self.config = config or IndicatorConfig()
        self._current_speaker: Optional[str] = None
        self._is_speaking = False
    
    def attach(self, target: Any) -> None:
        """Attach to a conversation or engine.
        
        Args:
            target: Conversation or VoiceEngine to indicate
        """
        # Placeholder for attachment
        pass
    
    def detach(self) -> None:
        """Detach from current target."""
        self._current_speaker = None
        self._is_speaking = False
    
    def set_speaking(self, speaker: Optional[str], is_speaking: bool) -> None:
        """Update speaking state.
        
        Args:
            speaker: Speaker name (or None)
            is_speaking: Whether currently speaking
        """
        self._current_speaker = speaker
        self._is_speaking = is_speaking
    
    @property
    def current_speaker(self) -> Optional[str]:
        """Get current speaker name."""
        return self._current_speaker
    
    @property
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._is_speaking
    
    def get_color(self, speaker: str) -> str:
        """Get color for a speaker.
        
        Args:
            speaker: Speaker name
            
        Returns:
            Hex color code
        """
        if speaker in self.config.colors:
            return self.config.colors[speaker]
        
        # Generate consistent color from speaker name
        hash_val = hash(speaker) % 360
        return f"hsl({hash_val}, 70%, 50%)"


class HapticPattern(Enum):
    """Haptic feedback patterns."""
    TAP = auto()
    DOUBLE_TAP = auto()
    LONG_PRESS = auto()
    BUZZ = auto()
    PULSE = auto()


@dataclass
class HapticConfig:
    """Configuration for haptic feedback."""
    enabled: bool = True
    device: str = "auto"  # auto, controller, phone, wearable
    intensity: float = 1.0  # 0.0-1.0
    patterns: dict[str, HapticPattern] = field(default_factory=lambda: {
        "word_boundary": HapticPattern.TAP,
        "sentence_end": HapticPattern.DOUBLE_TAP,
        "speaker_change": HapticPattern.BUZZ,
        "emphasis": HapticPattern.PULSE,
    })


class HapticFeedback:
    """Tactile feedback synchronized with speech.
    
    Provides haptic cues for audio events, useful for deaf/deafblind
    users to follow speech patterns through touch.
    
    Example:
        haptics = HapticFeedback(device="controller")
        engine = VoiceEngine(Config(haptics=haptics))
        
        # Haptic feedback synced to speech
        result = engine.speak("Hello world!")
    """
    
    def __init__(self, config: Optional[HapticConfig] = None) -> None:
        """Initialize haptic feedback.
        
        Args:
            config: Haptic configuration
        """
        self.config = config or HapticConfig()
        self._device: Optional[Any] = None
    
    def connect(self) -> bool:
        """Connect to haptic device.
        
        Returns:
            True if connection successful
        """
        # Placeholder for device connection
        return True
    
    def disconnect(self) -> None:
        """Disconnect from haptic device."""
        self._device = None
    
    def trigger(self, event: str) -> None:
        """Trigger haptic feedback for an event.
        
        Args:
            event: Event name (word_boundary, sentence_end, etc.)
        """
        if not self.config.enabled:
            return
        
        pattern = self.config.patterns.get(event, HapticPattern.TAP)
        self._play_pattern(pattern)
    
    def _play_pattern(self, pattern: HapticPattern) -> None:
        """Play a haptic pattern.
        
        Args:
            pattern: Pattern to play
        """
        # Placeholder for actual haptic playback
        pass
    
    def custom_pattern(self, durations: list[int], intensities: list[float]) -> None:
        """Play a custom haptic pattern.
        
        Args:
            durations: List of duration in ms
            intensities: List of intensities (0.0-1.0)
        """
        # Placeholder for custom patterns
        pass
