"""
Audio plugin for processing and effects.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import numpy as np

from voice_soundboard.plugins.base import Plugin, PluginType


class AudioPlugin(Plugin):
    """Plugin for audio processing and effects.
    
    Audio plugins process synthesized audio:
    - Normalization
    - Effects (echo, reverb, etc.)
    - Format conversion
    - Quality enhancement
    
    Pipeline:
        synthesis → process() → output
    
    Example:
        @plugin
        class NormalizationPlugin(AudioPlugin):
            name = "normalizer"
            
            def process(self, audio, sample_rate, context):
                # Normalize to target LUFS
                return normalize_loudness(audio, target_lufs=-16)
    """
    
    plugin_type = PluginType.AUDIO
    
    # Plugin priority (lower = runs earlier)
    priority: int = 100
    
    @abstractmethod
    def process(
        self,
        audio: np.ndarray,
        sample_rate: int,
        context: dict[str, Any],
    ) -> np.ndarray:
        """Process audio data.
        
        Args:
            audio: Audio samples as float32 array.
            sample_rate: Sample rate in Hz.
            context: Processing context (metadata, settings).
        
        Returns:
            Processed audio as float32 array.
        """
        ...
    
    def can_process(self, context: dict[str, Any]) -> bool:
        """Check if this plugin should process the audio.
        
        Override to conditionally apply processing.
        
        Args:
            context: Processing context.
        
        Returns:
            True if plugin should process.
        """
        return True
    
    def on_load(self, registry) -> None:
        """Register the audio plugin."""
        registry.register_audio_plugin(self)


class EffectPlugin(AudioPlugin):
    """Base class for audio effect plugins.
    
    Effects modify the audio signal (reverb, delay, etc.).
    
    Example:
        @plugin
        class SimpleReverbPlugin(EffectPlugin):
            name = "reverb"
            
            def apply_effect(self, audio, sample_rate):
                # Add simple reverb
                delay_samples = int(0.03 * sample_rate)
                decay = 0.3
                output = audio.copy()
                output[delay_samples:] += audio[:-delay_samples] * decay
                return output
    """
    
    # Effect parameters
    wet_dry_mix: float = 0.5  # 0 = dry, 1 = wet
    
    @abstractmethod
    def apply_effect(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> np.ndarray:
        """Apply the effect to audio.
        
        Args:
            audio: Input audio.
            sample_rate: Sample rate.
        
        Returns:
            Processed audio (wet signal only).
        """
        ...
    
    def process(
        self,
        audio: np.ndarray,
        sample_rate: int,
        context: dict,
    ) -> np.ndarray:
        """Process audio with wet/dry mixing."""
        wet = self.apply_effect(audio, sample_rate)
        
        # Mix wet and dry signals
        mix = self.wet_dry_mix
        return audio * (1 - mix) + wet * mix


class NormalizationPlugin(AudioPlugin):
    """Plugin for audio normalization.
    
    Normalizes audio to consistent levels.
    
    Example:
        plugin = NormalizationPlugin(target_lufs=-16)
    """
    
    name = "normalizer"
    
    def __init__(
        self,
        config=None,
        target_lufs: float = -16.0,
        true_peak: float = -1.0,
    ):
        super().__init__(config)
        self.target_lufs = target_lufs
        self.true_peak = true_peak
    
    def process(
        self,
        audio: np.ndarray,
        sample_rate: int,
        context: dict,
    ) -> np.ndarray:
        """Normalize audio to target loudness."""
        # Simple peak normalization for now
        # Full LUFS normalization would require more sophisticated analysis
        peak = np.max(np.abs(audio))
        
        if peak > 0:
            # Normalize to true peak
            target_linear = 10 ** (self.true_peak / 20)
            audio = audio * (target_linear / peak)
        
        return audio


class DuckingPlugin(AudioPlugin):
    """Plugin for audio ducking (lowering music during speech).
    
    Reduces background audio level when speech is detected.
    
    Example:
        plugin = DuckingPlugin(duck_amount_db=-12)
    """
    
    name = "ducker"
    
    def __init__(
        self,
        config=None,
        duck_amount_db: float = -12.0,
        attack_ms: float = 10.0,
        release_ms: float = 100.0,
    ):
        super().__init__(config)
        self.duck_amount_db = duck_amount_db
        self.attack_ms = attack_ms
        self.release_ms = release_ms
    
    def process(
        self,
        audio: np.ndarray,
        sample_rate: int,
        context: dict,
    ) -> np.ndarray:
        """Apply ducking based on context."""
        should_duck = context.get("duck", False)
        
        if not should_duck:
            return audio
        
        # Apply gain reduction
        gain = 10 ** (self.duck_amount_db / 20)
        
        # Create envelope for smooth transition
        attack_samples = int(self.attack_ms * sample_rate / 1000)
        release_samples = int(self.release_ms * sample_rate / 1000)
        
        envelope = np.ones(len(audio))
        
        # Simple linear envelope
        if attack_samples > 0:
            envelope[:attack_samples] = np.linspace(1, gain, attack_samples)
        envelope[attack_samples:-release_samples] = gain
        if release_samples > 0:
            envelope[-release_samples:] = np.linspace(gain, 1, release_samples)
        
        return audio * envelope
