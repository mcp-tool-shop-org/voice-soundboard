"""
Scene - Multi-layer audio scene composition.

Features:
    - Multiple audio layers (speech, music, effects)
    - Per-layer volume, pan, timing
    - Scene serialization
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class LayerType(Enum):
    """Type of audio layer."""
    
    SPEECH = "speech"
    MUSIC = "music"
    AMBIANCE = "ambiance"
    EFFECT = "effect"
    NARRATION = "narration"


@dataclass
class AudioLayer:
    """
    Audio layer within a scene.
    
    Attributes:
        audio: Raw audio data (PCM bytes or path)
        layer_type: Type of layer
        volume: Volume level (0.0 - 1.0)
        pan: Stereo panning (-1.0 left to 1.0 right)
        start_time: Start time in seconds
        duration: Duration in seconds (None = full length)
        fade_in: Fade in duration in seconds
        fade_out: Fade out duration in seconds
        loop: Whether to loop
    """
    
    audio: bytes | str
    layer_type: LayerType = LayerType.SPEECH
    volume: float = 1.0
    pan: float = 0.0
    start_time: float = 0.0
    duration: float | None = None
    fade_in: float = 0.0
    fade_out: float = 0.0
    loop: bool = False
    
    # Metadata
    name: str = ""
    sample_rate: int = 24000
    channels: int = 1
    
    def with_volume(self, volume: float) -> "AudioLayer":
        """Return copy with new volume."""
        return AudioLayer(
            audio=self.audio,
            layer_type=self.layer_type,
            volume=volume,
            pan=self.pan,
            start_time=self.start_time,
            duration=self.duration,
            fade_in=self.fade_in,
            fade_out=self.fade_out,
            loop=self.loop,
            name=self.name,
            sample_rate=self.sample_rate,
            channels=self.channels,
        )
    
    def with_timing(
        self,
        start_time: float,
        duration: float | None = None,
    ) -> "AudioLayer":
        """Return copy with new timing."""
        return AudioLayer(
            audio=self.audio,
            layer_type=self.layer_type,
            volume=self.volume,
            pan=self.pan,
            start_time=start_time,
            duration=duration,
            fade_in=self.fade_in,
            fade_out=self.fade_out,
            loop=self.loop,
            name=self.name,
            sample_rate=self.sample_rate,
            channels=self.channels,
        )
    
    def with_fade(
        self,
        fade_in: float = 0.0,
        fade_out: float = 0.0,
    ) -> "AudioLayer":
        """Return copy with fade settings."""
        return AudioLayer(
            audio=self.audio,
            layer_type=self.layer_type,
            volume=self.volume,
            pan=self.pan,
            start_time=self.start_time,
            duration=self.duration,
            fade_in=fade_in,
            fade_out=fade_out,
            loop=self.loop,
            name=self.name,
            sample_rate=self.sample_rate,
            channels=self.channels,
        )


@dataclass
class SceneConfig:
    """Configuration for scene mixing."""
    
    # Output format
    sample_rate: int = 24000
    channels: int = 2  # Stereo for panning
    bit_depth: int = 16
    
    # Mixing
    normalize: bool = True
    headroom_db: float = -1.0
    
    # Ducking
    duck_music_for_speech: bool = True
    duck_ratio: float = 0.3  # Duck to 30% during speech


@dataclass
class Scene:
    """
    Multi-layer audio scene.
    
    Example:
        scene = Scene(
            layers=[
                AudioLayer(speech_pcm, LayerType.SPEECH, volume=1.0),
                AudioLayer(music_file, LayerType.MUSIC, volume=0.25, loop=True),
                AudioLayer(rain_effect, LayerType.AMBIANCE, volume=0.15),
            ],
        )
        
        result = scene.mix()
    """
    
    layers: list[AudioLayer] = field(default_factory=list)
    config: SceneConfig = field(default_factory=SceneConfig)
    
    # Metadata
    name: str = ""
    description: str = ""
    duration: float | None = None  # Override total duration
    
    def add_layer(self, layer: AudioLayer) -> "Scene":
        """Add a layer to the scene."""
        self.layers.append(layer)
        return self
    
    def add_speech(
        self,
        audio: bytes | str,
        volume: float = 1.0,
        start_time: float = 0.0,
    ) -> "Scene":
        """Add a speech layer."""
        return self.add_layer(AudioLayer(
            audio=audio,
            layer_type=LayerType.SPEECH,
            volume=volume,
            start_time=start_time,
        ))
    
    def add_music(
        self,
        audio: bytes | str,
        volume: float = 0.25,
        loop: bool = True,
        fade_in: float = 2.0,
        fade_out: float = 2.0,
    ) -> "Scene":
        """Add a music layer."""
        return self.add_layer(AudioLayer(
            audio=audio,
            layer_type=LayerType.MUSIC,
            volume=volume,
            loop=loop,
            fade_in=fade_in,
            fade_out=fade_out,
        ))
    
    def add_ambiance(
        self,
        audio: bytes | str,
        volume: float = 0.2,
        loop: bool = True,
    ) -> "Scene":
        """Add an ambiance layer."""
        return self.add_layer(AudioLayer(
            audio=audio,
            layer_type=LayerType.AMBIANCE,
            volume=volume,
            loop=loop,
        ))
    
    def add_effect(
        self,
        audio: bytes | str,
        start_time: float,
        volume: float = 0.8,
        pan: float = 0.0,
    ) -> "Scene":
        """Add a sound effect layer."""
        return self.add_layer(AudioLayer(
            audio=audio,
            layer_type=LayerType.EFFECT,
            volume=volume,
            pan=pan,
            start_time=start_time,
        ))
    
    def get_layers_by_type(self, layer_type: LayerType) -> list[AudioLayer]:
        """Get all layers of a specific type."""
        return [l for l in self.layers if l.layer_type == layer_type]
    
    def calculate_duration(self) -> float:
        """Calculate total scene duration."""
        if self.duration:
            return self.duration
        
        max_end = 0.0
        
        for layer in self.layers:
            if layer.loop:
                continue  # Looped layers don't contribute to duration
            
            if isinstance(layer.audio, bytes):
                # Calculate duration from PCM
                bytes_per_sample = 2  # 16-bit
                samples = len(layer.audio) // (bytes_per_sample * layer.channels)
                layer_duration = samples / layer.sample_rate
            else:
                # Would need to read file to get duration
                layer_duration = layer.duration or 0.0
            
            if layer.duration:
                layer_duration = min(layer_duration, layer.duration)
            
            end_time = layer.start_time + layer_duration
            max_end = max(max_end, end_time)
        
        return max_end
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize scene to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "duration": self.duration,
            "config": {
                "sample_rate": self.config.sample_rate,
                "channels": self.config.channels,
                "normalize": self.config.normalize,
            },
            "layers": [
                {
                    "type": layer.layer_type.value,
                    "volume": layer.volume,
                    "pan": layer.pan,
                    "start_time": layer.start_time,
                    "duration": layer.duration,
                    "fade_in": layer.fade_in,
                    "fade_out": layer.fade_out,
                    "loop": layer.loop,
                    "name": layer.name,
                }
                for layer in self.layers
            ],
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any], audio_resolver: Any = None) -> "Scene":
        """Create scene from dictionary."""
        config = SceneConfig()
        if "config" in data:
            cfg = data["config"]
            config.sample_rate = cfg.get("sample_rate", 24000)
            config.channels = cfg.get("channels", 2)
            config.normalize = cfg.get("normalize", True)
        
        scene = cls(
            config=config,
            name=data.get("name", ""),
            description=data.get("description", ""),
            duration=data.get("duration"),
        )
        
        for layer_data in data.get("layers", []):
            # Resolve audio from external source if needed
            audio = b""  # Placeholder
            if audio_resolver:
                audio = audio_resolver(layer_data)
            
            layer = AudioLayer(
                audio=audio,
                layer_type=LayerType(layer_data.get("type", "speech")),
                volume=layer_data.get("volume", 1.0),
                pan=layer_data.get("pan", 0.0),
                start_time=layer_data.get("start_time", 0.0),
                duration=layer_data.get("duration"),
                fade_in=layer_data.get("fade_in", 0.0),
                fade_out=layer_data.get("fade_out", 0.0),
                loop=layer_data.get("loop", False),
                name=layer_data.get("name", ""),
            )
            scene.add_layer(layer)
        
        return scene
