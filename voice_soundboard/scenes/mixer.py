"""
Scene Mixer - Mix multiple audio layers into final output.

Features:
    - Multi-layer mixing
    - Volume normalization
    - Music ducking for speech
    - Fade in/out
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Iterator

from voice_soundboard.scenes.scene import Scene, AudioLayer, LayerType


@dataclass
class MixConfig:
    """Configuration for mixing."""
    
    sample_rate: int = 24000
    channels: int = 2
    bit_depth: int = 16
    
    # Normalization
    normalize: bool = True
    headroom_db: float = -1.0  # Peak level below 0 dB
    
    # Ducking
    enable_ducking: bool = True
    duck_ratio: float = 0.3
    duck_attack_ms: float = 50.0
    duck_release_ms: float = 200.0


@dataclass
class MixResult:
    """Result of mixing a scene."""
    
    audio: bytes
    sample_rate: int
    channels: int
    bit_depth: int
    duration: float
    peak_level: float = 0.0
    
    # Metadata
    layers_mixed: int = 0
    clipping_detected: bool = False


class SceneMixer:
    """
    Mix scene layers into final audio.
    
    Example:
        mixer = SceneMixer(
            sample_rate=24000,
            channels=2,
            normalize=True,
        )
        
        result = mixer.mix(scene)
        # result.audio contains mixed PCM
    """
    
    def __init__(
        self,
        sample_rate: int = 24000,
        channels: int = 2,
        config: MixConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = MixConfig(
                sample_rate=sample_rate,
                channels=channels,
            )
    
    def mix(self, scene: Scene) -> MixResult:
        """
        Mix all scene layers.
        
        Args:
            scene: Scene to mix
            
        Returns:
            MixResult with mixed audio
        """
        # Calculate total duration
        duration = scene.calculate_duration()
        total_samples = int(duration * self.config.sample_rate)
        
        # Create output buffer (float for mixing, convert at end)
        output = [[0.0] * total_samples for _ in range(self.config.channels)]
        
        # Extract speech regions for ducking
        speech_regions = self._extract_speech_regions(scene, total_samples)
        
        # Mix each layer
        for layer in scene.layers:
            self._mix_layer(layer, output, speech_regions)
        
        # Normalize if enabled
        peak_level = self._get_peak_level(output)
        clipping = False
        
        if self.config.normalize:
            target_peak = 10 ** (self.config.headroom_db / 20)
            if peak_level > 0:
                scale = target_peak / peak_level
                for ch in range(len(output)):
                    output[ch] = [s * scale for s in output[ch]]
                peak_level = target_peak
        elif peak_level > 1.0:
            clipping = True
        
        # Convert to PCM bytes
        audio = self._to_pcm(output)
        
        return MixResult(
            audio=audio,
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            bit_depth=self.config.bit_depth,
            duration=duration,
            peak_level=peak_level,
            layers_mixed=len(scene.layers),
            clipping_detected=clipping,
        )
    
    def _extract_speech_regions(
        self,
        scene: Scene,
        total_samples: int,
    ) -> list[bool]:
        """Extract regions where speech is active."""
        speech_active = [False] * total_samples
        
        for layer in scene.layers:
            if layer.layer_type not in (LayerType.SPEECH, LayerType.NARRATION):
                continue
            
            start_sample = int(layer.start_time * self.config.sample_rate)
            
            if isinstance(layer.audio, bytes):
                layer_samples = len(layer.audio) // 2  # 16-bit mono
            else:
                layer_samples = int((layer.duration or 5.0) * self.config.sample_rate)
            
            if layer.duration:
                layer_samples = min(
                    layer_samples,
                    int(layer.duration * self.config.sample_rate)
                )
            
            end_sample = min(start_sample + layer_samples, total_samples)
            
            for i in range(start_sample, end_sample):
                speech_active[i] = True
        
        return speech_active
    
    def _mix_layer(
        self,
        layer: AudioLayer,
        output: list[list[float]],
        speech_regions: list[bool],
    ) -> None:
        """Mix a single layer into output."""
        # Decode layer audio
        if isinstance(layer.audio, bytes):
            samples = self._decode_pcm(layer.audio, layer.sample_rate, layer.channels)
        else:
            # Would load from file
            samples = [[]]
            return
        
        # Calculate timing
        total_samples = len(output[0])
        start_sample = int(layer.start_time * self.config.sample_rate)
        
        layer_samples = len(samples[0]) if samples else 0
        if layer.duration:
            layer_samples = min(
                layer_samples,
                int(layer.duration * self.config.sample_rate)
            )
        
        # Handle looping
        if layer.loop and layer_samples > 0:
            # Extend samples to cover full duration
            original_samples = [ch[:] for ch in samples]
            while len(samples[0]) < total_samples:
                for ch in range(len(samples)):
                    samples[ch].extend(original_samples[ch])
            layer_samples = total_samples - start_sample
        
        # Apply fade in/out
        if layer.fade_in > 0 or layer.fade_out > 0:
            samples = self._apply_fades(
                samples,
                layer.fade_in,
                layer.fade_out,
                self.config.sample_rate,
            )
        
        # Mix into output
        should_duck = (
            self.config.enable_ducking
            and layer.layer_type == LayerType.MUSIC
        )
        
        duck_state = 1.0  # Current duck level
        duck_attack = 1.0 - (self.config.duck_attack_ms / 1000) * self.config.sample_rate
        duck_release = 1.0 - (self.config.duck_release_ms / 1000) * self.config.sample_rate
        
        for i in range(min(layer_samples, total_samples - start_sample)):
            output_idx = start_sample + i
            if output_idx >= total_samples:
                break
            
            # Apply ducking
            if should_duck:
                target_duck = self.config.duck_ratio if speech_regions[output_idx] else 1.0
                if target_duck < duck_state:
                    duck_state = max(target_duck, duck_state * duck_attack)
                else:
                    duck_state = min(target_duck, duck_state + (1.0 - duck_release) * (target_duck - duck_state))
            else:
                duck_state = 1.0
            
            # Calculate panned levels
            volume = layer.volume * duck_state
            left_vol = volume * (1.0 - max(0, layer.pan))
            right_vol = volume * (1.0 + min(0, layer.pan))
            
            # Get sample value
            if i < len(samples[0]):
                if len(samples) == 1:
                    # Mono to stereo
                    sample_val = samples[0][i]
                    if len(output) >= 2:
                        output[0][output_idx] += sample_val * left_vol
                        output[1][output_idx] += sample_val * right_vol
                    else:
                        output[0][output_idx] += sample_val * volume
                else:
                    # Stereo
                    for ch in range(min(len(samples), len(output))):
                        vol = left_vol if ch == 0 else right_vol
                        output[ch][output_idx] += samples[ch][i] * vol
    
    def _decode_pcm(
        self,
        audio: bytes,
        sample_rate: int,
        channels: int,
    ) -> list[list[float]]:
        """Decode PCM bytes to float samples."""
        # Assume 16-bit PCM
        samples_per_channel = len(audio) // (2 * channels)
        
        result = [[] for _ in range(channels)]
        
        for i in range(samples_per_channel):
            for ch in range(channels):
                idx = (i * channels + ch) * 2
                if idx + 2 <= len(audio):
                    value = struct.unpack('<h', audio[idx:idx + 2])[0]
                    result[ch].append(value / 32768.0)
        
        # Resample if needed
        if sample_rate != self.config.sample_rate:
            result = self._resample(result, sample_rate, self.config.sample_rate)
        
        return result
    
    def _resample(
        self,
        samples: list[list[float]],
        from_rate: int,
        to_rate: int,
    ) -> list[list[float]]:
        """Simple linear resampling."""
        if from_rate == to_rate:
            return samples
        
        ratio = to_rate / from_rate
        new_length = int(len(samples[0]) * ratio)
        
        result = []
        for ch_samples in samples:
            new_ch = []
            for i in range(new_length):
                src_idx = i / ratio
                idx_low = int(src_idx)
                idx_high = min(idx_low + 1, len(ch_samples) - 1)
                frac = src_idx - idx_low
                
                value = ch_samples[idx_low] * (1 - frac) + ch_samples[idx_high] * frac
                new_ch.append(value)
            result.append(new_ch)
        
        return result
    
    def _apply_fades(
        self,
        samples: list[list[float]],
        fade_in: float,
        fade_out: float,
        sample_rate: int,
    ) -> list[list[float]]:
        """Apply fade in/out to samples."""
        if not samples or not samples[0]:
            return samples
        
        length = len(samples[0])
        fade_in_samples = int(fade_in * sample_rate)
        fade_out_samples = int(fade_out * sample_rate)
        
        result = [ch[:] for ch in samples]
        
        # Fade in
        for i in range(min(fade_in_samples, length)):
            gain = i / fade_in_samples
            for ch in range(len(result)):
                result[ch][i] *= gain
        
        # Fade out
        for i in range(min(fade_out_samples, length)):
            idx = length - 1 - i
            gain = i / fade_out_samples
            for ch in range(len(result)):
                result[ch][idx] *= gain
        
        return result
    
    def _get_peak_level(self, output: list[list[float]]) -> float:
        """Get peak level across all channels."""
        peak = 0.0
        for ch in output:
            for sample in ch:
                peak = max(peak, abs(sample))
        return peak
    
    def _to_pcm(self, output: list[list[float]]) -> bytes:
        """Convert float samples to PCM bytes."""
        result = bytearray()
        
        length = len(output[0]) if output else 0
        
        for i in range(length):
            for ch in range(len(output)):
                # Clamp and convert to 16-bit
                sample = max(-1.0, min(1.0, output[ch][i]))
                value = int(sample * 32767)
                result.extend(struct.pack('<h', value))
        
        return bytes(result)
    
    def mix_streaming(
        self,
        scene: Scene,
        chunk_size: int = 4096,
    ) -> Iterator[bytes]:
        """
        Mix scene in streaming fashion.
        
        Args:
            scene: Scene to mix
            chunk_size: Samples per chunk
            
        Yields:
            PCM audio chunks
        """
        # For streaming, we need to maintain state
        # Simplified implementation - mix all then chunk
        result = self.mix(scene)
        
        audio = result.audio
        bytes_per_chunk = chunk_size * self.config.channels * 2  # 16-bit
        
        for i in range(0, len(audio), bytes_per_chunk):
            yield audio[i:i + bytes_per_chunk]
