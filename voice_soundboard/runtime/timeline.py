"""
Timeline Abstraction - Unified timeline streaming model.

This module provides a clean abstraction for streaming timelines that contain
events (non-speech audio) and speech tokens. It's designed for testing and
for applications that need precise timing control.

Key abstractions:
    - TimelineItem: Base for all timeline elements
    - Event: Non-speech audio (laugh, sigh, breath)
    - Token: Speech content with duration
    - Pause: Silence that can be replaced by events
    - stream_timeline: Renders timeline to StreamItem sequence

Invariants enforced:
    1. No overlap ever - items are sequential
    2. Total duration is predictable
    3. Deterministic output for identical input
    4. Pauses may be replaced by events (no double gaps)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Sequence
from enum import Enum


class ItemKind(str, Enum):
    """Kind of timeline item."""
    EVENT = "event"
    SPEECH = "speech"
    PAUSE = "pause"


@dataclass(frozen=True)
class Event:
    """Non-speech audio event.
    
    Events represent paralinguistic sounds like laughs, sighs, breaths.
    They insert time into the timeline - speech after an event is delayed.
    """
    type: str
    duration: float
    intensity: float = 1.0
    
    @property
    def kind(self) -> ItemKind:
        return ItemKind.EVENT


@dataclass(frozen=True)
class Token:
    """Speech content with duration.
    
    Represents synthesized speech. Duration is determined by TTS backend.
    """
    text: str
    duration: float
    
    @property
    def kind(self) -> ItemKind:
        return ItemKind.SPEECH


@dataclass(frozen=True)
class Pause:
    """Explicit silence in the timeline.
    
    Pauses may be replaced by events (ducking scenario).
    If an event spans a pause, the pause is absorbed, not added.
    """
    duration: float
    
    @property
    def kind(self) -> ItemKind:
        return ItemKind.PAUSE


# Union type for timeline items
TimelineItem = Event | Token | Pause


@dataclass
class StreamItem:
    """Item in the output stream.
    
    This is what stream_timeline yields - time-positioned audio segments.
    """
    kind: str  # "event" or "speech"
    duration: float
    start: float = 0.0
    
    # For events
    event_type: str | None = None
    intensity: float = 1.0
    
    # For speech
    text: str | None = None
    
    @property
    def end(self) -> float:
        return self.start + self.duration


def stream_timeline(
    timeline: Sequence[TimelineItem],
) -> Iterator[StreamItem]:
    """Stream a timeline to positioned audio items.
    
    Implements the canonical timeline rendering algorithm:
    
    1. Events are inserted (they consume time)
    2. Speech follows events (delayed by event duration)
    3. Pauses may be replaced by events (no double gaps)
    4. Output is deterministic
    
    Args:
        timeline: Sequence of Event, Token, or Pause items
    
    Yields:
        StreamItem instances with timing information
    
    Invariants:
        - No overlaps: each item.start >= previous.end
        - Deterministic: same input → same output
        - Total duration is sum of non-replaced items
    
    Example:
        >>> timeline = [Event("laugh", 0.25), Token("hello", 0.40)]
        >>> items = list(stream_timeline(timeline))
        >>> sum(i.duration for i in items)
        0.65
    """
    cursor = 0.0
    pending_event: Event | None = None
    
    for item in timeline:
        if isinstance(item, Event):
            # Events insert time and are yielded directly
            yield StreamItem(
                kind="event",
                duration=item.duration,
                start=cursor,
                event_type=item.type,
                intensity=item.intensity,
            )
            cursor += item.duration
            pending_event = item
            
        elif isinstance(item, Pause):
            # Pauses are absorbed if preceded by event (no double gap)
            # Otherwise they're silent gaps
            if pending_event is not None:
                # Pause absorbed by event - don't add time
                pending_event = None
            else:
                # No preceding event - pause adds time (silence)
                # We don't yield pauses as stream items - they're implicit
                cursor += item.duration
            
        elif isinstance(item, Token):
            # Speech is yielded after any events
            yield StreamItem(
                kind="speech",
                duration=item.duration,
                start=cursor,
                text=item.text,
            )
            cursor += item.duration
            pending_event = None
    
    # Timeline complete


def total_duration_ms(items: Sequence[StreamItem]) -> int:
    """Calculate total duration in milliseconds.
    
    Args:
        items: Sequence of StreamItem instances
    
    Returns:
        Total duration in milliseconds (rounded)
    """
    return int(sum(item.duration for item in items) * 1000)


def validate_no_overlap(items: Sequence[StreamItem]) -> bool:
    """Validate that no items overlap in time.
    
    Args:
        items: Sequence of StreamItem instances
    
    Returns:
        True if no overlaps, raises AssertionError otherwise
    """
    cursor = 0.0
    for item in items:
        assert item.start >= cursor, f"Overlap detected: {item.start} < {cursor}"
        cursor = item.end
    return True
