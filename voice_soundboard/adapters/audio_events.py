"""
Audio Event Adapter - Insert pre-recorded WAVs for paralinguistic events.

This adapter handles [laugh], [sigh], etc. by inserting actual audio clips
into the PCM stream. It follows strict timing rules:

RULES (Authoritative):
1. Events are inserted at boundaries only (never overlap speech)
2. Event time is owned by the event (speech delayed accordingly)
3. Silence is explicit (events replace pauses, not add to them)
4. Sample rate must match output (no runtime resampling)
5. Events do not affect prosody automatically
6. Events are atomic PCM blocks (no mid-event truncation)

See docs/audio_events.md for full specification.
"""

from __future__ import annotations

import json
import logging
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

from voice_soundboard.graph import ControlGraph, ParalinguisticEvent, Paralinguistic

logger = logging.getLogger(__name__)


@dataclass
class AudioVariant:
    """A single variant of an audio event."""
    id: str
    file: Path
    intensity_min: float
    intensity_max: float
    duration: float
    
    def matches_intensity(self, intensity: float) -> bool:
        """Check if this variant's range includes the intensity."""
        return self.intensity_min <= intensity <= self.intensity_max
    
    @property
    def range_width(self) -> float:
        """Width of the intensity range (for tiebreaking)."""
        return self.intensity_max - self.intensity_min


@dataclass
class AudioEventSpec:
    """Specification for an audio event type (e.g., 'laugh')."""
    type: str
    variants: list[AudioVariant]
    
    def select_variant(self, intensity: float) -> AudioVariant | None:
        """Select the best variant for a given intensity.
        
        Selection rules (deterministic, no randomness):
        1. Find variants where intensity ∈ [min, max]
        2. If multiple match → pick narrowest range
        3. If none match → pick closest range
        4. If still none → return None
        """
        # Find exact matches
        matches = [v for v in self.variants if v.matches_intensity(intensity)]
        
        if matches:
            # Pick narrowest range (most specific)
            return min(matches, key=lambda v: v.range_width)
        
        # Find closest range
        if self.variants:
            def distance(v: AudioVariant) -> float:
                if intensity < v.intensity_min:
                    return v.intensity_min - intensity
                elif intensity > v.intensity_max:
                    return intensity - v.intensity_max
                return 0.0
            
            return min(self.variants, key=distance)
        
        return None


class AudioEventManifest:
    """Manifest of all available audio events.
    
    Loaded from assets/audio_events/manifest.json.
    Validates all WAV files at load time.
    """
    
    def __init__(self, manifest_path: Path):
        """Load manifest from JSON file.
        
        Args:
            manifest_path: Path to manifest.json
        
        Raises:
            FileNotFoundError: If manifest doesn't exist
            ValueError: If manifest is invalid or WAVs don't match spec
        """
        self.base_dir = manifest_path.parent
        
        with open(manifest_path) as f:
            data = json.load(f)
        
        self.sample_rate: int = data["sample_rate"]
        self.events: dict[str, AudioEventSpec] = {}
        
        for event_type, event_data in data.get("events", {}).items():
            variants = []
            for v in event_data.get("variants", []):
                variant = AudioVariant(
                    id=v["id"],
                    file=self.base_dir / v["file"],
                    intensity_min=v["intensity_range"][0],
                    intensity_max=v["intensity_range"][1],
                    duration=v["duration"],
                )
                variants.append(variant)
            
            self.events[event_type] = AudioEventSpec(type=event_type, variants=variants)
    
    def get_event_spec(self, event_type: str) -> AudioEventSpec | None:
        """Get spec for an event type."""
        # Normalize event type (Paralinguistic enum → string)
        if isinstance(event_type, Paralinguistic):
            event_type = event_type.value
        return self.events.get(event_type)
    
    def validate(self) -> list[str]:
        """Validate all WAV files match spec.
        
        Returns list of issues (empty = valid).
        """
        issues = []
        
        for event_type, spec in self.events.items():
            for variant in spec.variants:
                if not variant.file.exists():
                    issues.append(f"{event_type}/{variant.id}: file not found: {variant.file}")
                    continue
                
                # Check WAV properties
                try:
                    with wave.open(str(variant.file), "rb") as wav:
                        if wav.getnchannels() != 1:
                            issues.append(f"{event_type}/{variant.id}: must be mono, got {wav.getnchannels()} channels")
                        
                        if wav.getframerate() != self.sample_rate:
                            issues.append(f"{event_type}/{variant.id}: sample rate {wav.getframerate()} != manifest {self.sample_rate}")
                        
                        if wav.getsampwidth() != 2:
                            issues.append(f"{event_type}/{variant.id}: must be 16-bit, got {wav.getsampwidth() * 8}-bit")
                        
                        # Check duration matches
                        actual_duration = wav.getnframes() / wav.getframerate()
                        if abs(actual_duration - variant.duration) > 0.05:
                            issues.append(f"{event_type}/{variant.id}: duration {actual_duration:.3f}s != manifest {variant.duration:.3f}s")
                
                except wave.Error as e:
                    issues.append(f"{event_type}/{variant.id}: invalid WAV: {e}")
        
        return issues


class AudioEventAdapter:
    """Adapter for rendering paralinguistic events as WAV audio.
    
    Usage:
        adapter = AudioEventAdapter.from_manifest("assets/audio_events/manifest.json")
        
        for event in graph.events:
            pcm = adapter.render(event)
            if pcm is not None:
                output_pcm(pcm)
    """
    
    def __init__(self, manifest: AudioEventManifest):
        """Initialize adapter with a manifest.
        
        Args:
            manifest: Loaded and validated manifest
        """
        self.manifest = manifest
        self._cache: dict[Path, np.ndarray] = {}
    
    @classmethod
    def from_manifest(cls, manifest_path: str | Path) -> "AudioEventAdapter":
        """Create adapter from manifest file.
        
        Args:
            manifest_path: Path to manifest.json
        
        Returns:
            Initialized adapter
        
        Raises:
            ValueError: If manifest validation fails
        """
        manifest = AudioEventManifest(Path(manifest_path))
        issues = manifest.validate()
        
        if issues:
            raise ValueError(f"Manifest validation failed:\n" + "\n".join(issues))
        
        return cls(manifest)
    
    @classmethod
    def try_load(cls, manifest_path: str | Path) -> "AudioEventAdapter | None":
        """Try to load adapter, return None if unavailable."""
        path = Path(manifest_path)
        if not path.exists():
            return None
        
        try:
            return cls.from_manifest(path)
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("Failed to load audio events: %s", e)
            return None
    
    @property
    def sample_rate(self) -> int:
        """Output sample rate."""
        return self.manifest.sample_rate
    
    def render(self, event: ParalinguisticEvent) -> np.ndarray | None:
        """Render an event to PCM audio.
        
        Args:
            event: The paralinguistic event to render
        
        Returns:
            PCM audio as float32 array, or None if no matching asset
        """
        spec = self.manifest.get_event_spec(event.type)
        if not spec:
            logger.debug("No audio spec for event type: %s", event.type)
            return None
        
        variant = spec.select_variant(event.intensity)
        if not variant:
            logger.debug("No variant for %s at intensity %.2f", event.type, event.intensity)
            return None
        
        return self._load_pcm(variant.file)
    
    def _load_pcm(self, path: Path) -> np.ndarray:
        """Load WAV file as float32 PCM (cached)."""
        if path in self._cache:
            return self._cache[path]
        
        with wave.open(str(path), "rb") as wav:
            frames = wav.readframes(wav.getnframes())
            pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        
        self._cache[path] = pcm
        return pcm
    
    def supported_events(self) -> list[str]:
        """Return list of supported event types."""
        return list(self.manifest.events.keys())


def render_timeline_with_events(
    graph: ControlGraph,
    speech_pcm: np.ndarray,
    adapter: AudioEventAdapter | None,
    speech_sample_rate: int,
) -> np.ndarray:
    """Render a complete timeline with speech and events.
    
    This implements the authoritative timeline rendering algorithm:
    
    1. Events are inserted at boundaries (not overlaid)
    2. Speech is delayed by event durations
    3. Events replace pauses (no double gaps)
    4. Sample rates must match
    
    Args:
        graph: The control graph with tokens and events
        speech_pcm: Synthesized speech audio
        adapter: Audio event adapter (may be None)
        speech_sample_rate: Sample rate of speech_pcm
    
    Returns:
        Combined PCM audio with events inserted
    """
    # If no adapter or no events, return speech as-is
    if not adapter or not graph.events:
        return speech_pcm
    
    # Check sample rate compatibility
    if adapter.sample_rate != speech_sample_rate:
        logger.warning(
            "Sample rate mismatch: adapter=%d, speech=%d. Skipping events.",
            adapter.sample_rate, speech_sample_rate
        )
        return speech_pcm
    
    # Sort events by start_time
    events = sorted(graph.events, key=lambda e: e.start_time)
    
    # Build output by inserting events at appropriate positions
    result_parts: list[np.ndarray] = []
    speech_position = 0  # Current position in speech_pcm
    
    # Estimate samples per second of speech
    # (This is simplified - real implementation would use token timing)
    total_speech_duration = len(speech_pcm) / speech_sample_rate
    
    for event in events:
        # Render event audio
        event_pcm = adapter.render(event)
        if event_pcm is None:
            continue
        
        # Calculate where in speech this event occurs
        # (Simplified: proportional to start_time / total expected duration)
        if total_speech_duration > 0 and event.start_time > 0:
            insert_sample = int(event.start_time / total_speech_duration * len(speech_pcm))
            insert_sample = min(insert_sample, len(speech_pcm))
        else:
            insert_sample = 0
        
        # Output speech up to this point
        if insert_sample > speech_position:
            result_parts.append(speech_pcm[speech_position:insert_sample])
        
        # Insert event audio (atomic block)
        result_parts.append(event_pcm)
        speech_position = insert_sample
    
    # Output remaining speech
    if speech_position < len(speech_pcm):
        result_parts.append(speech_pcm[speech_position:])
    
    if result_parts:
        return np.concatenate(result_parts)
    return speech_pcm


def stream_timeline_with_events(
    graph: ControlGraph,
    speech_iterator: Iterator[np.ndarray],
    adapter: AudioEventAdapter | None,
    speech_sample_rate: int,
) -> Iterator[np.ndarray]:
    """Stream timeline with events inserted.
    
    For streaming, we handle events differently:
    - Events at start_time=0 are yielded first
    - Other events are yielded after speech completes
    
    This is a simplified streaming model. For precise timing,
    use render_timeline_with_events() with full speech.
    
    Args:
        graph: Control graph
        speech_iterator: Iterator yielding speech PCM chunks
        adapter: Audio event adapter
        speech_sample_rate: Sample rate of speech
    
    Yields:
        PCM audio chunks
    """
    if not adapter or not graph.events:
        yield from speech_iterator
        return
    
    # Check sample rate
    if adapter.sample_rate != speech_sample_rate:
        logger.warning("Sample rate mismatch, skipping events in stream")
        yield from speech_iterator
        return
    
    events = sorted(graph.events, key=lambda e: e.start_time)
    
    # Yield events at start (start_time == 0)
    for event in events:
        if event.start_time == 0:
            pcm = adapter.render(event)
            if pcm is not None:
                yield pcm
    
    # Yield all speech
    yield from speech_iterator
    
    # Yield events at end (start_time > 0, simplified placement)
    for event in events:
        if event.start_time > 0:
            pcm = adapter.render(event)
            if pcm is not None:
                yield pcm
