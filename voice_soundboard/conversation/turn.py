"""
Conversation turn representation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TurnType(Enum):
    """Type of conversation turn."""
    
    SPEECH = "speech"
    """Normal speech turn."""
    
    ACTION = "action"
    """Non-speech action (e.g., [laughs])."""
    
    PAUSE = "pause"
    """Intentional pause in conversation."""
    
    OVERLAP = "overlap"
    """Overlapping speech (future feature)."""


@dataclass
class Turn:
    """A single turn in a conversation.
    
    Represents one utterance by one speaker.
    
    Attributes:
        speaker_id: Identifier of the speaker.
        text: The text to speak (or action description).
        turn_type: Type of turn.
        duration_ms: Optional fixed duration for pauses.
        start_time_ms: Optional explicit start time.
        metadata: Additional metadata.
    
    Example:
        # Speech turn
        turn = Turn("alice", "Hello, how are you?")
        
        # Pause turn
        pause = Turn.pause(500)  # 500ms pause
        
        # Action turn
        action = Turn.action("alice", "laughs")
    """
    
    speaker_id: str = ""
    text: str = ""
    turn_type: TurnType = TurnType.SPEECH
    duration_ms: float | None = None
    start_time_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Computed after synthesis
    audio_duration_ms: float | None = None
    end_time_ms: float | None = None
    
    # Aliases for cleaner API
    speaker: str = field(default="", repr=False)
    duration: float | None = field(default=None, repr=False)
    
    def __post_init__(self):
        # Support both speaker and speaker_id
        if self.speaker and not self.speaker_id:
            self.speaker_id = self.speaker
        elif self.speaker_id and not self.speaker:
            self.speaker = self.speaker_id
        
        # Support both duration (seconds) and duration_ms
        if self.duration is not None and self.duration_ms is None:
            self.duration_ms = self.duration * 1000
        elif self.duration_ms is not None and self.duration is None:
            self.duration = self.duration_ms / 1000
    
    @property
    def start_time(self) -> float | None:
        """Start time in seconds."""
        if self.start_time_ms is not None:
            return self.start_time_ms / 1000
        return None
    
    @start_time.setter
    def start_time(self, value: float | None):
        """Set start time in seconds."""
        if value is not None:
            self.start_time_ms = value * 1000
        else:
            self.start_time_ms = None
    
    @classmethod
    def speech(
        cls,
        speaker_id: str,
        text: str,
        **metadata: Any,
    ) -> "Turn":
        """Create a speech turn.
        
        Args:
            speaker_id: Speaker identifier.
            text: Text to speak.
            **metadata: Additional metadata.
        
        Returns:
            Turn instance.
        """
        return cls(
            speaker_id=speaker_id,
            text=text,
            turn_type=TurnType.SPEECH,
            metadata=metadata,
        )
    
    @classmethod
    def action(
        cls,
        speaker_id: str,
        action: str,
        **metadata: Any,
    ) -> "Turn":
        """Create an action turn.
        
        Args:
            speaker_id: Speaker identifier.
            action: Action description.
            **metadata: Additional metadata.
        
        Returns:
            Turn instance.
        """
        return cls(
            speaker_id=speaker_id,
            text=f"[{action}]",
            turn_type=TurnType.ACTION,
            metadata=metadata,
        )
    
    @classmethod
    def pause(
        cls,
        duration_ms: float,
        **metadata: Any,
    ) -> "Turn":
        """Create a pause turn.
        
        Args:
            duration_ms: Pause duration in milliseconds.
            **metadata: Additional metadata.
        
        Returns:
            Turn instance.
        """
        return cls(
            speaker_id="",
            text="",
            turn_type=TurnType.PAUSE,
            duration_ms=duration_ms,
            metadata=metadata,
        )
    
    @property
    def is_speech(self) -> bool:
        """Check if this is a speech turn."""
        return self.turn_type == TurnType.SPEECH
    
    @property
    def is_pause(self) -> bool:
        """Check if this is a pause turn."""
        return self.turn_type == TurnType.PAUSE
    
    @property
    def is_action(self) -> bool:
        """Check if this is an action turn."""
        return self.turn_type == TurnType.ACTION
    
    def with_timing(
        self,
        start_ms: float,
        duration_ms: float,
    ) -> "Turn":
        """Create a copy with timing information.
        
        Args:
            start_ms: Start time in milliseconds.
            duration_ms: Duration in milliseconds.
        
        Returns:
            New Turn with timing.
        """
        turn = Turn(
            speaker_id=self.speaker_id,
            text=self.text,
            turn_type=self.turn_type,
            duration_ms=duration_ms,
            start_time_ms=start_ms,
            metadata=self.metadata.copy(),
        )
        turn.audio_duration_ms = duration_ms
        turn.end_time_ms = start_ms + duration_ms
        return turn


@dataclass
class Timeline:
    """Timeline of conversation turns with timing.
    
    Computes timing for all turns based on audio durations
    and optional gaps between turns.
    
    Attributes:
        turns: List of turns with timing.
        total_duration_ms: Total conversation duration.
    """
    
    turns: list[Turn] = field(default_factory=list)
    gap_ms: float = 100  # Default gap between turns
    _current_time: float = field(default=0.0, repr=False)  # Tracks next start time in seconds
    
    @property
    def total_duration_ms(self) -> float:
        """Total duration in milliseconds."""
        if not self.turns:
            return 0
        last_turn = self.turns[-1]
        if last_turn.end_time_ms is not None:
            return last_turn.end_time_ms
        # Calculate from durations
        total = 0.0
        for turn in self.turns:
            if turn.duration_ms is not None:
                total += turn.duration_ms
        return total
    
    @property
    def total_duration(self) -> float:
        """Total duration in seconds."""
        return self.total_duration_ms / 1000
    
    def add_turn(self, turn: Turn) -> None:
        """Add a turn to the timeline with automatic timing.
        
        Args:
            turn: Turn to add.
        """
        # Set start time
        turn.start_time_ms = self._current_time * 1000
        
        # Calculate duration from turn's duration field
        duration_s = turn.duration if turn.duration is not None else 0.0
        turn.duration_ms = duration_s * 1000
        turn.end_time_ms = turn.start_time_ms + turn.duration_ms
        
        # Advance current time
        self._current_time += duration_s
        
        self.turns.append(turn)
    
    def turn_at(self, time_seconds: float) -> Turn | None:
        """Get the turn at a specific time.
        
        Args:
            time_seconds: Time in seconds.
        
        Returns:
            Turn at that time, or None if no turn.
        """
        time_ms = time_seconds * 1000
        for turn in self.turns:
            start = turn.start_time_ms or 0
            end = turn.end_time_ms or (start + (turn.duration_ms or 0))
            if start <= time_ms < end:
                return turn
        return None
    
    def compute_timing(self, durations: list[float]) -> "Timeline":
        """Compute timing for all turns given audio durations.
        
        Args:
            durations: List of audio durations in ms for each turn.
        
        Returns:
            New Timeline with computed timing.
        """
        timed_turns = []
        current_time = 0.0
        
        for turn, duration in zip(self.turns, durations):
            if turn.is_pause:
                duration = turn.duration_ms or self.gap_ms
            
            timed_turn = turn.with_timing(current_time, duration)
            timed_turns.append(timed_turn)
            
            current_time += duration
            
            # Add gap between speech turns
            if turn.is_speech:
                current_time += self.gap_ms
        
        return Timeline(turns=timed_turns, gap_ms=self.gap_ms)
    
    def get_speaker_timeline(self, speaker_id: str) -> list[Turn]:
        """Get turns for a specific speaker.
        
        Args:
            speaker_id: Speaker identifier.
        
        Returns:
            List of turns for that speaker.
        """
        return [t for t in self.turns if t.speaker_id == speaker_id]
