"""
Scene Builder - Fluent scene construction.

Features:
    - Fluent API for building scenes
    - Automatic timing calculations
    - Transition effects
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from enum import Enum

from voice_soundboard.scenes.scene import Scene, SceneConfig, AudioLayer, LayerType


class TransitionType(Enum):
    """Type of transition between segments."""
    
    CUT = "cut"           # Immediate cut
    CROSSFADE = "crossfade"  # Fade out/in
    FADE_OUT = "fade_out"    # Fade out then cut
    FADE_IN = "fade_in"      # Cut then fade in


@dataclass
class SceneSegment:
    """A segment in the scene timeline."""
    
    audio: bytes | str
    layer_type: LayerType
    duration: float | None
    volume: float
    transition: TransitionType
    transition_duration: float


class SceneBuilder:
    """
    Fluent builder for audio scenes.
    
    Example:
        scene = (
            SceneBuilder("My Podcast")
            .set_music("intro.mp3", volume=0.3)
            .add_speech(intro_audio)
            .crossfade(2.0)
            .add_speech(main_content)
            .add_effect("ding.wav", at=30.0)
            .fade_out(3.0)
            .build()
        )
    """
    
    def __init__(self, name: str = ""):
        self.name = name
        self._segments: list[SceneSegment] = []
        self._music: AudioLayer | None = None
        self._ambiance: AudioLayer | None = None
        self._effects: list[tuple[float, AudioLayer]] = []
        self._config = SceneConfig()
        self._cursor: float = 0.0  # Current timeline position
    
    def configure(
        self,
        sample_rate: int = 24000,
        channels: int = 2,
        normalize: bool = True,
        duck_music: bool = True,
    ) -> "SceneBuilder":
        """Configure scene settings."""
        self._config.sample_rate = sample_rate
        self._config.channels = channels
        self._config.normalize = normalize
        self._config.duck_music_for_speech = duck_music
        return self
    
    def set_music(
        self,
        audio: bytes | str,
        volume: float = 0.25,
        fade_in: float = 2.0,
        fade_out: float = 2.0,
    ) -> "SceneBuilder":
        """Set background music."""
        self._music = AudioLayer(
            audio=audio,
            layer_type=LayerType.MUSIC,
            volume=volume,
            fade_in=fade_in,
            fade_out=fade_out,
            loop=True,
        )
        return self
    
    def set_ambiance(
        self,
        audio: bytes | str,
        volume: float = 0.15,
    ) -> "SceneBuilder":
        """Set ambient background audio."""
        self._ambiance = AudioLayer(
            audio=audio,
            layer_type=LayerType.AMBIANCE,
            volume=volume,
            loop=True,
        )
        return self
    
    def add_speech(
        self,
        audio: bytes | str,
        volume: float = 1.0,
        duration: float | None = None,
    ) -> "SceneBuilder":
        """Add speech segment at current position."""
        segment = SceneSegment(
            audio=audio,
            layer_type=LayerType.SPEECH,
            duration=duration,
            volume=volume,
            transition=TransitionType.CUT,
            transition_duration=0.0,
        )
        self._segments.append(segment)
        return self
    
    def add_narration(
        self,
        audio: bytes | str,
        volume: float = 0.9,
        duration: float | None = None,
    ) -> "SceneBuilder":
        """Add narration segment."""
        segment = SceneSegment(
            audio=audio,
            layer_type=LayerType.NARRATION,
            duration=duration,
            volume=volume,
            transition=TransitionType.CUT,
            transition_duration=0.0,
        )
        self._segments.append(segment)
        return self
    
    def add_effect(
        self,
        audio: bytes | str,
        at: float | None = None,
        volume: float = 0.8,
        pan: float = 0.0,
    ) -> "SceneBuilder":
        """Add sound effect at specific time."""
        effect = AudioLayer(
            audio=audio,
            layer_type=LayerType.EFFECT,
            volume=volume,
            pan=pan,
            start_time=at if at is not None else self._cursor,
        )
        self._effects.append((effect.start_time, effect))
        return self
    
    def pause(self, duration: float) -> "SceneBuilder":
        """Add a pause/silence."""
        self._cursor += duration
        return self
    
    def crossfade(self, duration: float = 1.0) -> "SceneBuilder":
        """Set crossfade transition for next segment."""
        if self._segments:
            self._segments[-1].transition = TransitionType.CROSSFADE
            self._segments[-1].transition_duration = duration
        return self
    
    def fade_out(self, duration: float = 2.0) -> "SceneBuilder":
        """Set fade out transition for last segment."""
        if self._segments:
            self._segments[-1].transition = TransitionType.FADE_OUT
            self._segments[-1].transition_duration = duration
        return self
    
    def fade_in(self, duration: float = 2.0) -> "SceneBuilder":
        """Set fade in transition for next segment."""
        # This affects the next added segment
        return self
    
    def build(self) -> Scene:
        """Build the final scene."""
        scene = Scene(
            config=self._config,
            name=self.name,
        )
        
        # Add background layers
        if self._music:
            scene.add_layer(self._music)
        
        if self._ambiance:
            scene.add_layer(self._ambiance)
        
        # Add speech/narration segments
        current_time = 0.0
        
        for i, segment in enumerate(self._segments):
            layer = AudioLayer(
                audio=segment.audio,
                layer_type=segment.layer_type,
                volume=segment.volume,
                start_time=current_time,
                duration=segment.duration,
            )
            
            # Apply transitions
            if i > 0:
                prev_segment = self._segments[i - 1]
                if prev_segment.transition == TransitionType.CROSSFADE:
                    layer = layer.with_fade(
                        fade_in=prev_segment.transition_duration,
                        fade_out=0.0,
                    )
                    current_time -= prev_segment.transition_duration
                    layer = layer.with_timing(current_time, layer.duration)
            
            if segment.transition == TransitionType.FADE_OUT:
                layer = layer.with_fade(
                    fade_in=layer.fade_in,
                    fade_out=segment.transition_duration,
                )
            
            scene.add_layer(layer)
            
            # Advance timeline
            if segment.duration:
                current_time += segment.duration
            else:
                # Estimate from audio if possible
                if isinstance(segment.audio, bytes):
                    samples = len(segment.audio) // 2  # 16-bit
                    current_time += samples / self._config.sample_rate
                else:
                    current_time += 5.0  # Default assumption
        
        # Add effects
        for _, effect in self._effects:
            scene.add_layer(effect)
        
        return scene


def create_podcast_scene(
    intro: bytes | str,
    content: list[bytes | str],
    outro: bytes | str,
    music: bytes | str,
) -> Scene:
    """
    Create a podcast-style scene.
    
    Args:
        intro: Introduction audio
        content: List of content segments
        outro: Outro audio
        music: Background music
        
    Returns:
        Configured Scene
    """
    builder = (
        SceneBuilder("Podcast")
        .set_music(music, volume=0.2)
        .add_speech(intro)
        .crossfade(1.0)
    )
    
    for segment in content:
        builder.add_speech(segment)
        builder.pause(0.5)
    
    builder.crossfade(1.0)
    builder.add_speech(outro)
    builder.fade_out(3.0)
    
    return builder.build()


def create_audiobook_scene(
    chapters: list[bytes | str],
    chapter_titles: list[str] | None = None,
    ambiance: bytes | str | None = None,
) -> Scene:
    """
    Create an audiobook-style scene.
    
    Args:
        chapters: List of chapter audio
        chapter_titles: Optional chapter titles
        ambiance: Optional background ambiance
        
    Returns:
        Configured Scene
    """
    builder = SceneBuilder("Audiobook")
    
    if ambiance:
        builder.set_ambiance(ambiance, volume=0.1)
    
    for i, chapter in enumerate(chapters):
        builder.add_narration(chapter)
        if i < len(chapters) - 1:
            builder.pause(2.0)  # Pause between chapters
    
    return builder.build()
