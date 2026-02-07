"""
Spatial Scene - 3D audio scene with multiple sources.

Features:
    - Multiple positioned sources
    - Scene serialization
    - Animation support
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from voice_soundboard.spatial.position import (
    SpatialPosition,
    ListenerPosition,
    Coordinates,
)
from voice_soundboard.spatial.mixer import SpatialMixer, SpatialConfig, SpatialSource


@dataclass
class SpatialAudioLayer:
    """
    Audio layer with spatial position.
    
    Attributes:
        audio: Audio data (PCM bytes or path)
        position: 3D position
        name: Layer identifier
        volume: Volume multiplier
        start_time: Start time in scene (seconds)
        duration: Duration (None = full length)
    """
    
    audio: bytes | str
    position: SpatialPosition
    name: str = ""
    volume: float = 1.0
    start_time: float = 0.0
    duration: float | None = None
    
    # Animation keyframes (time -> position)
    keyframes: list[tuple[float, SpatialPosition]] = field(default_factory=list)
    
    def with_position(self, position: SpatialPosition) -> "SpatialAudioLayer":
        """Return copy with new position."""
        return SpatialAudioLayer(
            audio=self.audio,
            position=position,
            name=self.name,
            volume=self.volume,
            start_time=self.start_time,
            duration=self.duration,
            keyframes=self.keyframes[:],
        )
    
    def add_keyframe(self, time: float, position: SpatialPosition) -> "SpatialAudioLayer":
        """Add animation keyframe."""
        self.keyframes.append((time, position))
        self.keyframes.sort(key=lambda k: k[0])
        return self
    
    def get_position_at(self, time: float) -> SpatialPosition:
        """Get interpolated position at time."""
        if not self.keyframes:
            return self.position
        
        # Find surrounding keyframes
        prev_key = None
        next_key = None
        
        for kf_time, kf_pos in self.keyframes:
            if kf_time <= time:
                prev_key = (kf_time, kf_pos)
            if kf_time >= time and next_key is None:
                next_key = (kf_time, kf_pos)
        
        if prev_key is None:
            return self.keyframes[0][1]
        if next_key is None:
            return self.keyframes[-1][1]
        if prev_key[0] == next_key[0]:
            return prev_key[1]
        
        # Linear interpolation
        t = (time - prev_key[0]) / (next_key[0] - prev_key[0])
        
        return SpatialPosition(
            x=prev_key[1].x + t * (next_key[1].x - prev_key[1].x),
            y=prev_key[1].y + t * (next_key[1].y - prev_key[1].y),
            z=prev_key[1].z + t * (next_key[1].z - prev_key[1].z),
        )


@dataclass
class SpatialScene:
    """
    3D audio scene with multiple positioned sources.
    
    Example:
        scene = SpatialScene(name="Conference")
        
        # Add speakers at positions
        scene.add_layer(
            voice1_pcm,
            SpatialPosition.left(1.5),
            name="speaker1",
        )
        scene.add_layer(
            voice2_pcm,
            SpatialPosition.right(1.5),
            name="speaker2",
        )
        
        # Render the scene
        mixer = SpatialMixer()
        stereo = scene.render(mixer)
    """
    
    layers: list[SpatialAudioLayer] = field(default_factory=list)
    listener: ListenerPosition = field(default_factory=ListenerPosition)
    config: SpatialConfig = field(default_factory=SpatialConfig)
    
    name: str = ""
    description: str = ""
    
    def add_layer(
        self,
        audio: bytes | str,
        position: SpatialPosition,
        name: str = "",
        volume: float = 1.0,
        start_time: float = 0.0,
    ) -> "SpatialScene":
        """Add an audio layer to the scene."""
        layer = SpatialAudioLayer(
            audio=audio,
            position=position,
            name=name,
            volume=volume,
            start_time=start_time,
        )
        self.layers.append(layer)
        return self
    
    def add_voice(
        self,
        audio: bytes | str,
        position: SpatialPosition,
        name: str = "",
    ) -> "SpatialScene":
        """Add a voice at a position."""
        return self.add_layer(audio, position, name=name, volume=1.0)
    
    def add_ambient(
        self,
        audio: bytes | str,
        position: SpatialPosition,
        volume: float = 0.3,
    ) -> "SpatialScene":
        """Add ambient audio at a position."""
        return self.add_layer(audio, position, name="ambient", volume=volume)
    
    def get_layer(self, name: str) -> SpatialAudioLayer | None:
        """Get a layer by name."""
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None
    
    def remove_layer(self, name: str) -> bool:
        """Remove a layer by name."""
        for i, layer in enumerate(self.layers):
            if layer.name == name:
                self.layers.pop(i)
                return True
        return False
    
    def move_layer(self, name: str, position: SpatialPosition) -> bool:
        """Move a layer to a new position."""
        layer = self.get_layer(name)
        if layer:
            layer.position = position
            return True
        return False
    
    def render(
        self,
        mixer: SpatialMixer | None = None,
    ) -> bytes:
        """
        Render the scene to stereo audio.
        
        Args:
            mixer: SpatialMixer to use (optional)
            
        Returns:
            Stereo PCM audio
        """
        if mixer is None:
            mixer = SpatialMixer(config=self.config)
        
        mixer.set_listener(self.listener)
        
        # Convert layers to sources (for layers with bytes audio)
        sources = []
        for layer in self.layers:
            if isinstance(layer.audio, bytes):
                source = SpatialSource(
                    audio=layer.audio,
                    position=layer.position,
                    name=layer.name,
                    gain=layer.volume,
                )
                sources.append(source)
        
        if not sources:
            return b""
        
        return mixer.mix(sources)
    
    def render_animated(
        self,
        duration: float,
        frame_rate: float = 30.0,
        mixer: SpatialMixer | None = None,
    ) -> bytes:
        """
        Render scene with animated positions.
        
        Args:
            duration: Scene duration in seconds
            frame_rate: Animation frame rate
            mixer: SpatialMixer to use
            
        Returns:
            Stereo PCM audio
        """
        if mixer is None:
            mixer = SpatialMixer(config=self.config)
        
        mixer.set_listener(self.listener)
        
        # Render frame by frame
        sample_rate = self.config.sample_rate
        samples_per_frame = int(sample_rate / frame_rate)
        total_samples = int(duration * sample_rate)
        
        result = bytearray()
        
        for frame in range(int(duration * frame_rate)):
            time = frame / frame_rate
            frame_start = frame * samples_per_frame
            frame_end = min(frame_start + samples_per_frame, total_samples)
            
            # Get animated positions
            sources = []
            for layer in self.layers:
                if isinstance(layer.audio, bytes):
                    # Get position at current time
                    position = layer.get_position_at(time)
                    
                    # Extract audio segment for this frame
                    bytes_start = frame_start * 2  # 16-bit mono
                    bytes_end = frame_end * 2
                    
                    if bytes_start < len(layer.audio):
                        audio_segment = layer.audio[bytes_start:bytes_end]
                        
                        source = SpatialSource(
                            audio=audio_segment,
                            position=position,
                            name=layer.name,
                            gain=layer.volume,
                        )
                        sources.append(source)
            
            if sources:
                frame_audio = mixer.mix(sources)
                result.extend(frame_audio)
        
        return bytes(result)
    
    def calculate_duration(self) -> float:
        """Calculate total scene duration."""
        max_end = 0.0
        
        for layer in self.layers:
            if isinstance(layer.audio, bytes):
                # Calculate from PCM length (16-bit mono)
                layer_duration = len(layer.audio) / (2 * self.config.sample_rate)
            else:
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
            "listener": {
                "position": {
                    "x": self.listener.position.x,
                    "y": self.listener.position.y,
                    "z": self.listener.position.z,
                },
                "forward": {
                    "x": self.listener.forward.x,
                    "y": self.listener.forward.y,
                    "z": self.listener.forward.z,
                },
            },
            "layers": [
                {
                    "name": layer.name,
                    "position": {
                        "x": layer.position.x,
                        "y": layer.position.y,
                        "z": layer.position.z,
                    },
                    "volume": layer.volume,
                    "start_time": layer.start_time,
                    "keyframes": [
                        {
                            "time": t,
                            "position": {"x": p.x, "y": p.y, "z": p.z}
                        }
                        for t, p in layer.keyframes
                    ],
                }
                for layer in self.layers
            ],
        }
    
    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        audio_resolver: Any = None,
    ) -> "SpatialScene":
        """Create scene from dictionary."""
        scene = cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
        )
        
        # Restore listener
        if "listener" in data:
            listener_data = data["listener"]
            pos = listener_data.get("position", {})
            fwd = listener_data.get("forward", {"z": 1})
            
            scene.listener = ListenerPosition(
                position=Coordinates(
                    pos.get("x", 0),
                    pos.get("y", 0),
                    pos.get("z", 0),
                ),
                forward=Coordinates(
                    fwd.get("x", 0),
                    fwd.get("y", 0),
                    fwd.get("z", 1),
                ),
            )
        
        # Restore layers
        for layer_data in data.get("layers", []):
            audio = b""  # Placeholder
            if audio_resolver:
                audio = audio_resolver(layer_data)
            
            pos_data = layer_data.get("position", {})
            position = SpatialPosition(
                x=pos_data.get("x", 0),
                y=pos_data.get("y", 0),
                z=pos_data.get("z", 1),
            )
            
            layer = SpatialAudioLayer(
                audio=audio,
                position=position,
                name=layer_data.get("name", ""),
                volume=layer_data.get("volume", 1.0),
                start_time=layer_data.get("start_time", 0.0),
            )
            
            # Restore keyframes
            for kf_data in layer_data.get("keyframes", []):
                kf_pos = kf_data.get("position", {})
                layer.add_keyframe(
                    kf_data.get("time", 0),
                    SpatialPosition(
                        x=kf_pos.get("x", 0),
                        y=kf_pos.get("y", 0),
                        z=kf_pos.get("z", 1),
                    ),
                )
            
            scene.layers.append(layer)
        
        return scene


# Convenience functions
def create_conversation_scene(
    voices: list[tuple[bytes, str]],  # (audio, speaker_name)
    positions: list[SpatialPosition] | None = None,
) -> SpatialScene:
    """
    Create a scene for a multi-speaker conversation.
    
    Args:
        voices: List of (audio, speaker_name) tuples
        positions: Optional positions (default: arranged in arc)
        
    Returns:
        Configured SpatialScene
    """
    scene = SpatialScene(name="Conversation")
    
    if positions is None:
        # Arrange in an arc
        import math
        positions = []
        for i in range(len(voices)):
            angle = -0.5 + i / (len(voices) - 1) if len(voices) > 1 else 0
            positions.append(SpatialPosition.from_polar(
                azimuth=angle,
                distance=2.0,
            ))
    
    for (audio, name), position in zip(voices, positions):
        scene.add_voice(audio, position, name=name)
    
    return scene


def create_surround_scene(
    center: bytes | None = None,
    left: bytes | None = None,
    right: bytes | None = None,
    rear_left: bytes | None = None,
    rear_right: bytes | None = None,
) -> SpatialScene:
    """
    Create a 5.0 surround-style scene.
    
    Args:
        center: Center channel audio
        left: Front left audio
        right: Front right audio
        rear_left: Rear left audio
        rear_right: Rear right audio
        
    Returns:
        Configured SpatialScene
    """
    import math
    
    scene = SpatialScene(name="Surround")
    
    if center:
        scene.add_layer(center, SpatialPosition.center(), name="center")
    
    if left:
        scene.add_layer(left, SpatialPosition.from_polar(-math.pi/6, 2.0), name="front_left")
    
    if right:
        scene.add_layer(right, SpatialPosition.from_polar(math.pi/6, 2.0), name="front_right")
    
    if rear_left:
        scene.add_layer(rear_left, SpatialPosition.from_polar(-2*math.pi/3, 2.0), name="rear_left")
    
    if rear_right:
        scene.add_layer(rear_right, SpatialPosition.from_polar(2*math.pi/3, 2.0), name="rear_right")
    
    return scene
