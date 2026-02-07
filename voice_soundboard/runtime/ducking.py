"""
Ducking System - Gain envelope processing for speech following events.

Ducking creates the perceptual effect of audio mixing without actually
overlapping audio in time. This preserves all timeline invariants while
adding expressiveness.

Core insight: Ducking is a gain envelope, not an overlap permission.

Semantics:
    - Events can specify a DuckingEnvelope
    - Speech following the event has gain applied
    - Fade-out/fade-in create smooth transitions
    - Timeline remains strictly sequential

Example:
    An event with ducking: {"gain": 0.5, "fade_out_ms": 50, "fade_in_ms": 150}
    
    Means: Lower speech volume to 50%, fade out over 50ms after event,
    fade back in over 150ms. Speech is still sequential, not overlapped.

Invariants preserved:
    - No overlap (audio is sequential)
    - Deterministic (same input → same output)
    - Engine untouched (this is adapter-level)
    - Event atomicity (events are not modified)
    - Total duration unchanged (gain doesn't change timing)

This belongs in runtime/, not engine/, as it's an optional audio effect
applied during final rendering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Sequence

import numpy as np


@dataclass(frozen=True)
class DuckingEnvelope:
    """Gain envelope to apply to speech following an event.
    
    Fields:
        gain: Target gain level (0.0 - 1.0). 0.5 = 50% volume.
        fade_out_ms: Time to fade from 1.0 to gain after event ends.
        fade_in_ms: Time to fade from gain back to 1.0.
    
    The envelope is applied to speech immediately following the event:
    
        1. Event plays at full volume
        2. Speech starts at reduced gain
        3. Fade-in ramps gain back to 1.0
    
    Total duration is unchanged - ducking only affects amplitude.
    """
    gain: float = 0.5
    fade_out_ms: int = 50
    fade_in_ms: int = 150
    
    def __post_init__(self):
        if not 0.0 <= self.gain <= 1.0:
            raise ValueError(f"gain must be 0.0-1.0, got {self.gain}")
        if self.fade_out_ms < 0:
            raise ValueError(f"fade_out_ms must be >= 0, got {self.fade_out_ms}")
        if self.fade_in_ms < 0:
            raise ValueError(f"fade_in_ms must be >= 0, got {self.fade_in_ms}")


@dataclass
class DuckedEvent:
    """An event with optional ducking specification.
    
    This wraps event data with ducking information for the gain processor.
    """
    duration: float
    ducking: DuckingEnvelope | None = None


@dataclass  
class DuckedSpeech:
    """Speech audio with gain applied.
    
    After processing through DuckingProcessor, speech items have
    gain information attached.
    """
    pcm: np.ndarray
    applied_gain: float = 1.0
    fade_applied: bool = False


def apply_gain_envelope(
    pcm: np.ndarray,
    gain: float,
    fade_in_samples: int,
    sample_rate: int = 24000,
) -> np.ndarray:
    """Apply gain envelope to PCM audio.
    
    Args:
        pcm: Float32 PCM audio samples
        gain: Target gain level (0.0-1.0)
        fade_in_samples: Number of samples to fade from gain to 1.0
        sample_rate: Audio sample rate (for reference)
    
    Returns:
        PCM audio with gain envelope applied
    
    The envelope:
        1. Starts at `gain` level
        2. Linearly fades to 1.0 over `fade_in_samples`
        3. Remains at 1.0 for the rest of the audio
    
    This creates the perception that audio is "emerging" from
    a ducked state, even though it's strictly sequential.
    """
    if gain >= 1.0 or len(pcm) == 0:
        return pcm  # No ducking needed
    
    result = pcm.copy()
    
    # Apply fade-in envelope
    if fade_in_samples > 0:
        fade_length = min(fade_in_samples, len(result))
        # Linear ramp from gain to 1.0
        envelope = np.linspace(gain, 1.0, fade_length, dtype=np.float32)
        result[:fade_length] *= envelope
        # Apply constant gain to remaining samples (if fade is shorter than audio)
        if fade_length < len(result):
            # No additional gain needed after fade completes (already at 1.0)
            pass
    else:
        # No fade - apply constant gain then ramp to 1.0
        # Actually, if no fade, we should still have the ducking effect
        # Apply gain to entire audio
        result *= gain
    
    return result


def apply_constant_gain(
    pcm: np.ndarray,
    gain: float,
) -> np.ndarray:
    """Apply constant gain to PCM audio.
    
    Args:
        pcm: Float32 PCM audio samples
        gain: Gain level (0.0-1.0)
    
    Returns:
        PCM audio with gain applied
    """
    if gain >= 1.0 or len(pcm) == 0:
        return pcm
    
    return pcm * gain


class DuckingProcessor:
    """Stateful processor that applies ducking to timeline streams.
    
    Usage:
        processor = DuckingProcessor(sample_rate=24000)
        
        for item in timeline:
            if is_event(item):
                processor.set_ducking(item.ducking)
                output(item.pcm)
            elif is_speech(item):
                ducked_pcm = processor.process_speech(item.pcm)
                output(ducked_pcm)
    
    The processor maintains state about the current ducking envelope
    and applies it to subsequent speech items.
    """
    
    def __init__(self, sample_rate: int = 24000):
        self._sample_rate = sample_rate
        self._current_ducking: DuckingEnvelope | None = None
    
    @property
    def sample_rate(self) -> int:
        return self._sample_rate
    
    @property
    def is_ducking(self) -> bool:
        """True if we're currently in a ducked state."""
        return self._current_ducking is not None
    
    def set_ducking(self, envelope: DuckingEnvelope | None) -> None:
        """Set the current ducking envelope (from an event)."""
        self._current_ducking = envelope
    
    def clear_ducking(self) -> None:
        """Clear the current ducking state."""
        self._current_ducking = None
    
    def process_speech(self, pcm: np.ndarray) -> np.ndarray:
        """Process speech audio through current ducking state.
        
        If ducking is active:
            1. Apply gain envelope to speech
            2. Clear ducking state (single-shot)
        
        If no ducking:
            Return speech unchanged
        
        Args:
            pcm: Speech audio samples (float32)
        
        Returns:
            Processed audio (may have gain envelope applied)
        """
        if self._current_ducking is None:
            return pcm
        
        envelope = self._current_ducking
        fade_in_samples = int(envelope.fade_in_ms * self._sample_rate / 1000)
        
        result = apply_gain_envelope(
            pcm=pcm,
            gain=envelope.gain,
            fade_in_samples=fade_in_samples,
            sample_rate=self._sample_rate,
        )
        
        # Clear ducking after applying (single-shot)
        self._current_ducking = None
        
        return result
    
    def reset(self) -> None:
        """Reset processor state."""
        self._current_ducking = None


def process_timeline_with_ducking(
    timeline: Sequence[tuple[str, np.ndarray, DuckingEnvelope | None]],
    sample_rate: int = 24000,
) -> Iterator[np.ndarray]:
    """Process a timeline with ducking applied.
    
    Convenience function that processes a sequence of (kind, pcm, ducking)
    tuples and yields ducked audio.
    
    Args:
        timeline: Sequence of (kind, pcm, ducking) where:
            - kind: "event" or "speech"
            - pcm: Audio samples
            - ducking: DuckingEnvelope (only for events) or None
        sample_rate: Audio sample rate
    
    Yields:
        Processed PCM audio chunks
    
    Example:
        timeline = [
            ("event", laugh_pcm, DuckingEnvelope(gain=0.5)),
            ("speech", hello_pcm, None),
        ]
        for chunk in process_timeline_with_ducking(timeline):
            play(chunk)
    """
    processor = DuckingProcessor(sample_rate=sample_rate)
    
    for kind, pcm, ducking in timeline:
        if kind == "event":
            processor.set_ducking(ducking)
            yield pcm
        elif kind == "speech":
            yield processor.process_speech(pcm)
        else:
            # Unknown kind - pass through
            yield pcm


# =============================================================================
# Presets
# =============================================================================

# Standard ducking presets for common use cases

DUCKING_SUBTLE = DuckingEnvelope(gain=0.8, fade_out_ms=30, fade_in_ms=100)
"""Subtle ducking - barely noticeable volume reduction."""

DUCKING_STANDARD = DuckingEnvelope(gain=0.5, fade_out_ms=50, fade_in_ms=150)
"""Standard ducking - noticeable but not dramatic."""

DUCKING_DRAMATIC = DuckingEnvelope(gain=0.3, fade_out_ms=75, fade_in_ms=250)
"""Dramatic ducking - strong volume reduction."""

DUCKING_PODCAST = DuckingEnvelope(gain=0.6, fade_out_ms=40, fade_in_ms=200)
"""Podcast-style ducking - smooth and professional."""


__all__ = [
    "DuckingEnvelope",
    "DuckedEvent",
    "DuckedSpeech",
    "apply_gain_envelope",
    "apply_constant_gain",
    "DuckingProcessor",
    "process_timeline_with_ducking",
    # Presets
    "DUCKING_SUBTLE",
    "DUCKING_STANDARD",
    "DUCKING_DRAMATIC",
    "DUCKING_PODCAST",
]
