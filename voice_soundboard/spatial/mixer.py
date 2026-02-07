"""
Spatial Mixer - Apply spatial positioning to audio.

Features:
    - HRTF-based spatialization
    - Distance attenuation
    - Room simulation
"""

from __future__ import annotations

import struct
import math
from dataclasses import dataclass, field
from typing import Any

from voice_soundboard.spatial.position import (
    SpatialPosition,
    ListenerPosition,
    Coordinates,
)


@dataclass
class SpatialConfig:
    """Configuration for spatial audio."""
    
    # Audio settings
    sample_rate: int = 24000
    channels: int = 2  # Always stereo output
    
    # Spatialization
    enable_hrtf: bool = True
    enable_distance_attenuation: bool = True
    enable_doppler: bool = False
    
    # Distance model
    distance_model: str = "inverse"  # inverse, linear, exponential
    reference_distance: float = 1.0
    max_distance: float = 100.0
    rolloff_factor: float = 1.0
    
    # Room acoustics
    enable_reverb: bool = False
    room_size: float = 0.5  # 0-1
    damping: float = 0.5    # 0-1


@dataclass
class SpatialSource:
    """An audio source with spatial properties."""
    
    audio: bytes
    position: SpatialPosition
    name: str = ""
    
    # Dynamic properties
    velocity: Coordinates = None
    gain: float = 1.0
    
    def __post_init__(self):
        if self.velocity is None:
            self.velocity = Coordinates(0, 0, 0)


class SpatialMixer:
    """
    Mix audio with spatial positioning.
    
    Example:
        mixer = SpatialMixer(sample_rate=24000)
        
        # Position audio to the right
        stereo = mixer.position(
            audio=mono_pcm,
            position=SpatialPosition(x=2.0, y=0.0, z=1.0),
        )
        
        # Mix multiple sources
        sources = [
            SpatialSource(voice1, SpatialPosition.left()),
            SpatialSource(voice2, SpatialPosition.right()),
        ]
        mixed = mixer.mix(sources)
    """
    
    def __init__(
        self,
        sample_rate: int = 24000,
        config: SpatialConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = SpatialConfig(sample_rate=sample_rate)
        
        self.listener = ListenerPosition()
        
        # HRTF data (simplified)
        self._hrtf_cache: dict[tuple[int, int], tuple[list[float], list[float]]] = {}
    
    def set_listener(self, position: ListenerPosition) -> None:
        """Set the listener position."""
        self.listener = position
    
    def position(
        self,
        audio: bytes,
        position: SpatialPosition,
        source_sample_rate: int | None = None,
    ) -> bytes:
        """
        Apply spatial positioning to audio.
        
        Args:
            audio: Mono PCM audio bytes
            position: 3D position
            source_sample_rate: Sample rate of source (default: config.sample_rate)
            
        Returns:
            Stereo PCM audio bytes
        """
        source_rate = source_sample_rate or self.config.sample_rate
        
        # Decode mono PCM
        samples = self._decode_pcm(audio)
        
        # Get listener-relative position
        relative_pos = self.listener.relative_position(position.coordinates)
        
        # Calculate spatial parameters
        azimuth, distance, elevation = position.to_polar()
        
        # Apply distance attenuation
        gain = self._calculate_distance_gain(distance, position)
        
        # Apply HRTF or simple panning
        if self.config.enable_hrtf:
            left, right = self._apply_hrtf(samples, azimuth, elevation)
        else:
            left, right = self._apply_simple_panning(samples, azimuth)
        
        # Apply gain
        left = [s * gain for s in left]
        right = [s * gain for s in right]
        
        # Encode to stereo PCM
        return self._encode_stereo_pcm(left, right)
    
    def mix(
        self,
        sources: list[SpatialSource],
    ) -> bytes:
        """
        Mix multiple spatial sources.
        
        Args:
            sources: List of spatial sources
            
        Returns:
            Mixed stereo PCM
        """
        if not sources:
            return b""
        
        # Find maximum length
        max_samples = 0
        positioned = []
        
        for source in sources:
            samples = self._decode_pcm(source.audio)
            max_samples = max(max_samples, len(samples))
            
            # Get spatial parameters
            relative_pos = self.listener.relative_position(source.position.coordinates)
            azimuth, distance, elevation = source.position.to_polar()
            
            # Apply distance attenuation
            gain = self._calculate_distance_gain(distance, source.position) * source.gain
            
            # Apply spatialization
            if self.config.enable_hrtf:
                left, right = self._apply_hrtf(samples, azimuth, elevation)
            else:
                left, right = self._apply_simple_panning(samples, azimuth)
            
            # Apply gain
            left = [s * gain for s in left]
            right = [s * gain for s in right]
            
            positioned.append((left, right))
        
        # Mix all sources
        mixed_left = [0.0] * max_samples
        mixed_right = [0.0] * max_samples
        
        for left, right in positioned:
            for i in range(len(left)):
                if i < max_samples:
                    mixed_left[i] += left[i]
                    mixed_right[i] += right[i]
        
        # Normalize to prevent clipping
        peak = max(
            max(abs(s) for s in mixed_left),
            max(abs(s) for s in mixed_right),
        )
        
        if peak > 0.95:
            scale = 0.95 / peak
            mixed_left = [s * scale for s in mixed_left]
            mixed_right = [s * scale for s in mixed_right]
        
        return self._encode_stereo_pcm(mixed_left, mixed_right)
    
    def _calculate_distance_gain(
        self,
        distance: float,
        position: SpatialPosition,
    ) -> float:
        """Calculate gain based on distance."""
        if not self.config.enable_distance_attenuation:
            return 1.0
        
        # Use source-specific parameters if available
        min_dist = position.min_distance
        max_dist = position.max_distance
        rolloff = position.rolloff * self.config.rolloff_factor
        
        if distance <= min_dist:
            return 1.0
        
        if distance >= max_dist:
            return 0.0
        
        # Apply distance model
        if self.config.distance_model == "linear":
            return 1.0 - rolloff * (distance - min_dist) / (max_dist - min_dist)
        
        elif self.config.distance_model == "exponential":
            return pow(distance / min_dist, -rolloff)
        
        else:  # inverse (default)
            return min_dist / (min_dist + rolloff * (distance - min_dist))
    
    def _apply_simple_panning(
        self,
        samples: list[float],
        azimuth: float,
    ) -> tuple[list[float], list[float]]:
        """Apply constant-power panning."""
        # Convert azimuth to pan position (-1 to 1)
        # azimuth: 0 = front, positive = right
        pan = math.sin(azimuth)
        pan = max(-1.0, min(1.0, pan))
        
        # Constant power panning
        angle = (pan + 1) * math.pi / 4  # 0 to pi/2
        left_gain = math.cos(angle)
        right_gain = math.sin(angle)
        
        left = [s * left_gain for s in samples]
        right = [s * right_gain for s in samples]
        
        return left, right
    
    def _apply_hrtf(
        self,
        samples: list[float],
        azimuth: float,
        elevation: float,
    ) -> tuple[list[float], list[float]]:
        """Apply HRTF-based spatialization."""
        # Simplified HRTF using ITD (interaural time difference)
        # and ILD (interaural level difference)
        
        # Head radius approximation
        head_radius = 0.0875  # meters
        speed_of_sound = 343.0  # m/s
        
        # Calculate ITD (time delay between ears)
        # Woodworth formula
        if abs(azimuth) < math.pi / 2:
            itd = (head_radius / speed_of_sound) * (azimuth + math.sin(azimuth))
        else:
            itd = (head_radius / speed_of_sound) * (math.pi - azimuth + math.sin(azimuth))
        
        # Convert to samples
        delay_samples = int(abs(itd) * self.config.sample_rate)
        
        # Calculate ILD (level difference)
        # Approximation based on azimuth
        ild_db = 10 * math.sin(azimuth)  # Up to 10 dB difference
        ild_ratio = 10 ** (ild_db / 20)
        
        # Apply delay and level difference
        if azimuth >= 0:
            # Source on right - delay left ear, reduce left level
            left_gain = 1.0 / ild_ratio
            right_gain = 1.0
            left = [0.0] * delay_samples + [s * left_gain for s in samples[:-delay_samples or len(samples)]]
            right = [s * right_gain for s in samples]
        else:
            # Source on left - delay right ear, reduce right level
            left_gain = 1.0
            right_gain = ild_ratio
            left = [s * left_gain for s in samples]
            right = [0.0] * delay_samples + [s * right_gain for s in samples[:-delay_samples or len(samples)]]
        
        # Ensure same length
        target_length = len(samples)
        left = left[:target_length] + [0.0] * max(0, target_length - len(left))
        right = right[:target_length] + [0.0] * max(0, target_length - len(right))
        
        return left, right
    
    def _decode_pcm(self, audio: bytes) -> list[float]:
        """Decode PCM bytes to float samples."""
        samples = []
        for i in range(0, len(audio), 2):
            if i + 2 <= len(audio):
                value = struct.unpack('<h', audio[i:i + 2])[0]
                samples.append(value / 32768.0)
        return samples
    
    def _encode_stereo_pcm(
        self,
        left: list[float],
        right: list[float],
    ) -> bytes:
        """Encode stereo float samples to PCM bytes."""
        result = bytearray()
        
        for i in range(len(left)):
            # Clamp and convert
            l_value = max(-1.0, min(1.0, left[i]))
            r_value = max(-1.0, min(1.0, right[i]))
            
            result.extend(struct.pack('<h', int(l_value * 32767)))
            result.extend(struct.pack('<h', int(r_value * 32767)))
        
        return bytes(result)
