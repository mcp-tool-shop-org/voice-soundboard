"""
Ambiance Generator - Generate ambient background audio.

Features:
    - Procedural ambiance generation
    - Preset environments (rain, cafe, office, etc.)
    - Layered ambient sounds
    - Seamless looping
"""

from __future__ import annotations

import struct
import math
import random
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class NoiseType(Enum):
    """Type of noise generation."""
    
    WHITE = "white"
    PINK = "pink"
    BROWN = "brown"
    BLUE = "blue"


@dataclass
class AmbianceConfig:
    """Configuration for ambiance generation."""
    
    # Audio settings
    sample_rate: int = 24000
    channels: int = 2  # Stereo
    bit_depth: int = 16
    
    # Generation
    base_volume: float = 0.2
    variation: float = 0.1  # Volume variation
    
    # Seamless looping
    crossfade_duration: float = 0.5


@dataclass
class AmbiancePreset:
    """
    Preset configuration for an ambiance type.
    
    Attributes:
        name: Preset name
        description: Human-readable description
        layers: Layer configurations
        base_volume: Default volume
    """
    
    name: str
    description: str = ""
    
    # Noise layers
    noise_type: NoiseType = NoiseType.PINK
    noise_volume: float = 0.1
    
    # Additional layers
    layers: list[dict[str, Any]] = field(default_factory=list)
    
    # Volume
    base_volume: float = 0.2
    
    # Modulation
    modulation_rate: float = 0.0  # Hz, 0 = no modulation
    modulation_depth: float = 0.0


class AmbianceGenerator:
    """
    Generate ambient background audio.
    
    Example:
        generator = AmbianceGenerator(sample_rate=24000)
        
        # Generate rain ambiance
        rain = generator.generate("rain", duration=60.0)
        
        # Custom ambiance
        custom = generator.generate_from_preset(
            AmbiancePreset(
                name="custom",
                noise_type=NoiseType.PINK,
                noise_volume=0.15,
            ),
            duration=30.0,
        )
    """
    
    def __init__(
        self,
        sample_rate: int = 24000,
        config: AmbianceConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = AmbianceConfig(sample_rate=sample_rate)
        
        # State for filtered noise
        self._pink_state = [0.0] * 7
        self._brown_state = 0.0
    
    def generate(
        self,
        preset_name: str,
        duration: float,
        volume: float | None = None,
    ) -> bytes:
        """
        Generate ambiance from a preset name.
        
        Args:
            preset_name: Name of preset (rain, cafe, office, etc.)
            duration: Duration in seconds
            volume: Override volume (0.0 - 1.0)
            
        Returns:
            PCM audio bytes
        """
        from voice_soundboard.ambiance.presets import get_preset
        
        preset = get_preset(preset_name)
        if volume is not None:
            preset.base_volume = volume
        
        return self.generate_from_preset(preset, duration)
    
    def generate_from_preset(
        self,
        preset: AmbiancePreset,
        duration: float,
    ) -> bytes:
        """
        Generate ambiance from a preset.
        
        Args:
            preset: AmbiancePreset configuration
            duration: Duration in seconds
            
        Returns:
            PCM audio bytes
        """
        total_samples = int(duration * self.config.sample_rate)
        
        # Generate base noise
        base_noise = self._generate_noise(
            preset.noise_type,
            total_samples,
            preset.noise_volume * preset.base_volume,
        )
        
        # Apply modulation if configured
        if preset.modulation_rate > 0:
            base_noise = self._apply_modulation(
                base_noise,
                preset.modulation_rate,
                preset.modulation_depth,
            )
        
        # Mix in additional layers
        for layer_config in preset.layers:
            layer_audio = self._generate_layer(layer_config, total_samples)
            for i in range(len(base_noise)):
                base_noise[i] += layer_audio[i] * preset.base_volume
        
        # Apply crossfade for seamless looping
        if self.config.crossfade_duration > 0:
            base_noise = self._apply_crossfade(base_noise)
        
        # Convert to stereo PCM
        return self._to_stereo_pcm(base_noise)
    
    def _generate_noise(
        self,
        noise_type: NoiseType,
        samples: int,
        volume: float,
    ) -> list[float]:
        """Generate noise of specified type."""
        if noise_type == NoiseType.WHITE:
            return self._generate_white_noise(samples, volume)
        elif noise_type == NoiseType.PINK:
            return self._generate_pink_noise(samples, volume)
        elif noise_type == NoiseType.BROWN:
            return self._generate_brown_noise(samples, volume)
        elif noise_type == NoiseType.BLUE:
            return self._generate_blue_noise(samples, volume)
        else:
            return self._generate_white_noise(samples, volume)
    
    def _generate_white_noise(
        self,
        samples: int,
        volume: float,
    ) -> list[float]:
        """Generate white noise."""
        return [
            (random.random() * 2 - 1) * volume
            for _ in range(samples)
        ]
    
    def _generate_pink_noise(
        self,
        samples: int,
        volume: float,
    ) -> list[float]:
        """Generate pink (1/f) noise using Voss-McCartney algorithm."""
        result = []
        
        # Initialize running sums
        b = self._pink_state
        
        for _ in range(samples):
            white = random.random() * 2 - 1
            
            # Update filters at different rates
            b[0] = 0.99886 * b[0] + white * 0.0555179
            b[1] = 0.99332 * b[1] + white * 0.0750759
            b[2] = 0.96900 * b[2] + white * 0.1538520
            b[3] = 0.86650 * b[3] + white * 0.3104856
            b[4] = 0.55000 * b[4] + white * 0.5329522
            b[5] = -0.7616 * b[5] - white * 0.0168980
            
            # Sum and scale
            pink = b[0] + b[1] + b[2] + b[3] + b[4] + b[5] + b[6] + white * 0.5362
            b[6] = white * 0.115926
            
            # Normalize (pink noise is louder than white)
            result.append(pink * volume * 0.11)
        
        self._pink_state = b
        return result
    
    def _generate_brown_noise(
        self,
        samples: int,
        volume: float,
    ) -> list[float]:
        """Generate brown (red/random walk) noise."""
        result = []
        value = self._brown_state
        
        for _ in range(samples):
            white = (random.random() * 2 - 1) * 0.1
            value = max(-1, min(1, value + white))
            result.append(value * volume)
        
        self._brown_state = value
        return result
    
    def _generate_blue_noise(
        self,
        samples: int,
        volume: float,
    ) -> list[float]:
        """Generate blue (differentiated white) noise."""
        white = self._generate_white_noise(samples, 1.0)
        
        result = [0.0]
        for i in range(1, samples):
            result.append((white[i] - white[i - 1]) * volume * 0.5)
        
        return result
    
    def _generate_layer(
        self,
        config: dict[str, Any],
        samples: int,
    ) -> list[float]:
        """Generate a single ambiance layer."""
        layer_type = config.get("type", "noise")
        volume = config.get("volume", 0.1)
        
        if layer_type == "noise":
            noise_type = NoiseType(config.get("noise_type", "pink"))
            return self._generate_noise(noise_type, samples, volume)
        
        elif layer_type == "tone":
            # Generate subtle tone
            frequency = config.get("frequency", 100.0)
            return self._generate_tone(samples, frequency, volume)
        
        elif layer_type == "pulse":
            # Intermittent sounds
            rate = config.get("rate", 0.5)  # per second
            return self._generate_pulse(samples, rate, volume)
        
        else:
            return [0.0] * samples
    
    def _generate_tone(
        self,
        samples: int,
        frequency: float,
        volume: float,
    ) -> list[float]:
        """Generate a subtle tone."""
        result = []
        for i in range(samples):
            t = i / self.config.sample_rate
            value = math.sin(2 * math.pi * frequency * t) * volume
            result.append(value)
        return result
    
    def _generate_pulse(
        self,
        samples: int,
        rate: float,
        volume: float,
    ) -> list[float]:
        """Generate intermittent pulse sounds."""
        result = [0.0] * samples
        
        # Random pulse timing
        pulse_interval = int(self.config.sample_rate / rate)
        pulse_length = int(self.config.sample_rate * 0.05)  # 50ms pulses
        
        i = random.randint(0, pulse_interval)
        while i < samples:
            # Apply pulse
            for j in range(min(pulse_length, samples - i)):
                # Envelope
                env = math.sin(math.pi * j / pulse_length)
                result[i + j] = env * volume * (random.random() * 0.5 + 0.5)
            
            # Next pulse with some randomness
            i += pulse_interval + random.randint(-pulse_interval // 4, pulse_interval // 4)
        
        return result
    
    def _apply_modulation(
        self,
        audio: list[float],
        rate: float,
        depth: float,
    ) -> list[float]:
        """Apply volume modulation."""
        result = []
        for i, sample in enumerate(audio):
            t = i / self.config.sample_rate
            mod = 1.0 - depth * (1.0 + math.sin(2 * math.pi * rate * t)) * 0.5
            result.append(sample * mod)
        return result
    
    def _apply_crossfade(
        self,
        audio: list[float],
    ) -> list[float]:
        """Apply crossfade at start/end for seamless looping."""
        fade_samples = int(self.config.crossfade_duration * self.config.sample_rate)
        
        if len(audio) < fade_samples * 2:
            return audio
        
        result = audio[:]
        
        for i in range(fade_samples):
            fade_in = i / fade_samples
            fade_out = 1.0 - fade_in
            
            # Blend start with end
            start_idx = i
            end_idx = len(audio) - fade_samples + i
            
            result[start_idx] = audio[start_idx] * fade_in + audio[end_idx] * fade_out
        
        return result
    
    def _to_stereo_pcm(
        self,
        mono: list[float],
    ) -> bytes:
        """Convert mono float samples to stereo PCM bytes."""
        result = bytearray()
        
        for sample in mono:
            # Clamp
            sample = max(-1.0, min(1.0, sample))
            
            # Convert to 16-bit
            value = int(sample * 32767)
            
            # Stereo (duplicate to both channels)
            result.extend(struct.pack('<h', value))  # Left
            result.extend(struct.pack('<h', value))  # Right
        
        return bytes(result)
    
    def generate_layered(
        self,
        presets: list[str | AmbiancePreset],
        volumes: list[float] | None = None,
        duration: float = 60.0,
    ) -> bytes:
        """
        Generate layered ambiance from multiple presets.
        
        Args:
            presets: List of preset names or configurations
            volumes: Optional volume for each preset
            duration: Duration in seconds
            
        Returns:
            Mixed PCM audio
        """
        from voice_soundboard.ambiance.presets import get_preset
        
        if volumes is None:
            volumes = [0.3] * len(presets)
        
        total_samples = int(duration * self.config.sample_rate)
        mixed = [0.0] * total_samples
        
        for i, preset in enumerate(presets):
            if isinstance(preset, str):
                preset = get_preset(preset)
            
            preset.base_volume = volumes[i]
            
            # Generate mono float samples
            layer = self._generate_noise(
                preset.noise_type,
                total_samples,
                preset.noise_volume * preset.base_volume,
            )
            
            # Add modulation
            if preset.modulation_rate > 0:
                layer = self._apply_modulation(
                    layer,
                    preset.modulation_rate,
                    preset.modulation_depth,
                )
            
            # Mix
            for j in range(total_samples):
                mixed[j] += layer[j]
        
        # Normalize if needed
        peak = max(abs(s) for s in mixed) if mixed else 0.0
        if peak > 0.9:
            scale = 0.9 / peak
            mixed = [s * scale for s in mixed]
        
        return self._to_stereo_pcm(mixed)
