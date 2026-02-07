"""
v3.1 Conversation Helpers - Multi-Speaker Polishing.

Makes multi-track natural for conversation use cases with:
- Turn-taking helpers (automatic speaker sequencing)
- Automatic crossfades (smooth transitions)
- Per-speaker defaults (voice-specific settings)
- Scene-level mixing (conversation-wide config)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


@dataclass
class Position:
    """3D position for spatial audio positioning."""
    x: float = 0.0   # -1 (left) to 1 (right)
    y: float = 0.0   # -1 (below) to 1 (above)  
    z: float = 1.0   # Distance (>0)


@dataclass
class Speaker:
    """A speaker in a conversation with defaults.
    
    Encapsulates:
    - Identity (name, voice)
    - Spatial position
    - Default audio settings
    """
    name: str
    voice: str  # Voice ID
    
    # Spatial positioning
    position: Position | None = None
    
    # Default settings (applied to all turns by this speaker)
    defaults: dict[str, Any] = field(default_factory=dict)
    
    # Volume adjustment for this speaker
    gain_db: float = 0.0


@dataclass
class Turn:
    """A single dialogue turn in a conversation."""
    speaker: str       # Speaker name
    text: str          # What they say
    
    # Timing
    start_time: float | None = None  # Auto-calculated if None
    duration: float | None = None    # Auto-calculated from TTS
    
    # Overlap with previous turn
    overlap_ms: float = 0.0  # Positive = starts before previous ends
    
    # Emotion/style override for this turn
    emotion: str | None = None
    style: dict[str, Any] = field(default_factory=dict)
    
    # Custom metadata
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationDefaults:
    """Default settings for a conversation."""
    
    # Automatic ducking
    ducking: bool = True
    duck_amount: float = 0.7        # How much to reduce non-speaker volume
    duck_attack_ms: float = 50.0    # How fast to duck
    duck_release_ms: float = 200.0  # How fast to restore
    
    # Transition handling
    crossfade_ms: float = 100.0     # Crossfade duration between turns
    turn_gap_ms: float = 200.0      # Natural pause between turns
    
    # Scene settings
    auto_pan_speakers: bool = True  # Automatically pan based on position
    normalize_loudness: bool = True # Normalize speaker loudness
    target_lufs: float = -16.0      # Target loudness in LUFS


@dataclass
class ConversationConfig:
    """Configuration for a conversation."""
    ducking: bool = True
    duck_amount: float = 0.7
    crossfade_ms: float = 100.0
    turn_gap_ms: float = 200.0
    auto_pan: bool = True
    normalize: bool = True
    target_lufs: float = -16.0


class Conversation:
    """Multi-speaker conversation with automatic helpers.
    
    Handles:
    - Turn sequencing with automatic timing
    - Crossfades between speakers
    - Per-speaker audio defaults
    - Spatial positioning
    - Automatic ducking
    
    Example:
        alice = Speaker("Alice", "af_bella", Position(x=-0.5, y=0, z=1))
        bob = Speaker("Bob", "am_adam", Position(x=0.5, y=0, z=1))
        
        conversation = Conversation(
            speakers=[alice, bob],
            config=ConversationConfig(ducking=True, crossfade_ms=100),
        )
        
        conversation.add_turn("Alice", "Welcome to the podcast!")
        conversation.add_turn("Bob", "Thanks for having me.")
        
        audio = conversation.render(engine)
    """
    
    def __init__(
        self,
        speakers: list[Speaker] | None = None,
        config: ConversationConfig | None = None,
    ):
        self._speakers: dict[str, Speaker] = {}
        self._turns: list[Turn] = []
        self.config = config or ConversationConfig()
        
        # Register speakers
        if speakers:
            for speaker in speakers:
                self.add_speaker(speaker)
    
    # =========================================================================
    # Speaker Management
    # =========================================================================
    
    def add_speaker(self, speaker: Speaker) -> None:
        """Add a speaker to the conversation."""
        self._speakers[speaker.name] = speaker
    
    def get_speaker(self, name: str) -> Speaker | None:
        """Get speaker by name."""
        return self._speakers.get(name)
    
    def remove_speaker(self, name: str) -> bool:
        """Remove speaker by name. Returns True if removed."""
        if name in self._speakers:
            del self._speakers[name]
            return True
        return False
    
    @property
    def speakers(self) -> list[Speaker]:
        """Get all speakers."""
        return list(self._speakers.values())
    
    # =========================================================================
    # Turn Management
    # =========================================================================
    
    def add_turn(
        self,
        speaker: str,
        text: str,
        overlap_ms: float = 0.0,
        emotion: str | None = None,
        **style: Any,
    ) -> Turn:
        """Add a dialogue turn.
        
        Args:
            speaker: Speaker name (must be registered)
            text: Dialogue text
            overlap_ms: Overlap with previous turn (positive = interruption)
            emotion: Optional emotion override
            **style: Additional style parameters
        
        Returns:
            The created Turn object
        """
        if speaker not in self._speakers:
            raise ValueError(f"Unknown speaker: {speaker}")
        
        turn = Turn(
            speaker=speaker,
            text=text,
            overlap_ms=overlap_ms,
            emotion=emotion,
            style=dict(style),
        )
        self._turns.append(turn)
        return turn
    
    def get_turn(self, index: int) -> Turn | None:
        """Get turn by index."""
        if 0 <= index < len(self._turns):
            return self._turns[index]
        return None
    
    @property
    def turns(self) -> list[Turn]:
        """Get all turns."""
        return self._turns.copy()
    
    @property
    def turn_count(self) -> int:
        """Number of turns."""
        return len(self._turns)
    
    # =========================================================================
    # Timeline Calculation
    # =========================================================================
    
    def calculate_timeline(self, durations: dict[int, float]) -> list[tuple[int, float, float]]:
        """Calculate turn timings given durations.
        
        Args:
            durations: Map of turn index to estimated duration in seconds
        
        Returns:
            List of (turn_index, start_time, end_time) tuples
        """
        timeline = []
        current_time = 0.0
        
        for i, turn in enumerate(self._turns):
            # Get duration for this turn
            duration = durations.get(i, 1.0)  # Default 1 second
            
            # Calculate start time
            if i == 0:
                start_time = 0.0
            else:
                # Previous turn end minus overlap plus gap
                prev_end = timeline[-1][2]
                overlap_sec = turn.overlap_ms / 1000.0
                gap_sec = self.config.turn_gap_ms / 1000.0
                
                if turn.overlap_ms > 0:
                    # Interruption: start before previous ends
                    start_time = prev_end - overlap_sec
                else:
                    # Normal: add gap after previous
                    start_time = prev_end + gap_sec
            
            end_time = start_time + duration
            timeline.append((i, start_time, end_time))
            current_time = end_time
        
        return timeline
    
    # =========================================================================
    # Rendering
    # =========================================================================
    
    def to_audio_graph(self) -> Any:
        """Convert conversation to an AudioGraph.
        
        Creates a multi-track graph with:
        - One track per speaker
        - Proper timing and crossfades
        - Ducking configuration
        """
        from voice_soundboard.v3.audio_graph import AudioGraph, TrackType
        
        graph = AudioGraph(name=f"conversation_{len(self._turns)}_turns")
        
        # Create track per speaker
        for speaker in self._speakers.values():
            track = graph.add_track(speaker.name, TrackType.DIALOGUE)
            
            # Apply spatial positioning
            if speaker.position:
                track.pan = speaker.position.x
            
            # Apply defaults
            if "volume" in speaker.defaults:
                track.volume = speaker.defaults["volume"]
            
            # Setup ducking
            if self.config.ducking:
                # This speaker ducks for all other speakers
                other_speakers = [s.name for s in self._speakers.values() if s.name != speaker.name]
                track.duck_for = other_speakers
                track.duck_amount = self.config.duck_amount
        
        return graph
    
    def render(self, engine: Any) -> Any:
        """Render the conversation to audio.
        
        Args:
            engine: VoiceEngine instance
        
        Returns:
            Rendered audio (format depends on engine)
        """
        # This would integrate with the actual synthesis engine
        # For now, return the graph structure
        return self.to_audio_graph()
    
    # =========================================================================
    # Serialization
    # =========================================================================
    
    def to_dict(self) -> dict:
        """Serialize conversation to dictionary."""
        return {
            "speakers": [
                {
                    "name": s.name,
                    "voice": s.voice,
                    "position": {"x": s.position.x, "y": s.position.y, "z": s.position.z}
                    if s.position else None,
                    "defaults": s.defaults,
                    "gain_db": s.gain_db,
                }
                for s in self._speakers.values()
            ],
            "turns": [
                {
                    "speaker": t.speaker,
                    "text": t.text,
                    "overlap_ms": t.overlap_ms,
                    "emotion": t.emotion,
                    "style": t.style,
                }
                for t in self._turns
            ],
            "config": {
                "ducking": self.config.ducking,
                "duck_amount": self.config.duck_amount,
                "crossfade_ms": self.config.crossfade_ms,
                "turn_gap_ms": self.config.turn_gap_ms,
            },
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Conversation:
        """Deserialize conversation from dictionary."""
        speakers = [
            Speaker(
                name=s["name"],
                voice=s["voice"],
                position=Position(**s["position"]) if s.get("position") else None,
                defaults=s.get("defaults", {}),
                gain_db=s.get("gain_db", 0.0),
            )
            for s in data.get("speakers", [])
        ]
        
        config_data = data.get("config", {})
        config = ConversationConfig(
            ducking=config_data.get("ducking", True),
            duck_amount=config_data.get("duck_amount", 0.7),
            crossfade_ms=config_data.get("crossfade_ms", 100.0),
            turn_gap_ms=config_data.get("turn_gap_ms", 200.0),
        )
        
        conversation = cls(speakers=speakers, config=config)
        
        for turn_data in data.get("turns", []):
            conversation.add_turn(
                speaker=turn_data["speaker"],
                text=turn_data["text"],
                overlap_ms=turn_data.get("overlap_ms", 0.0),
                emotion=turn_data.get("emotion"),
                **turn_data.get("style", {}),
            )
        
        return conversation
    
    # =========================================================================
    # Script Loading
    # =========================================================================
    
    @classmethod
    def from_script(cls, script: str) -> Conversation:
        """Parse a simple script format.
        
        Format:
            ALICE: Welcome to the show!
            BOB: Thanks for having me.
            ALICE: Let's get started.
        
        Speakers are auto-created with default voices.
        """
        conversation = cls()
        
        voice_mapping = {
            "ALICE": "af_bella",
            "BOB": "am_adam",
            "CHARLIE": "af_sarah",
            "DAVID": "am_michael",
        }
        
        for line in script.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if ":" not in line:
                continue
            
            speaker_name, text = line.split(":", 1)
            speaker_name = speaker_name.strip().upper()
            text = text.strip()
            
            # Auto-create speaker if not exists
            if speaker_name not in [s.name.upper() for s in conversation._speakers.values()]:
                voice = voice_mapping.get(speaker_name, "af_bella")
                conversation.add_speaker(Speaker(
                    name=speaker_name.title(),
                    voice=voice,
                ))
            
            # Add turn
            actual_name = speaker_name.title()
            conversation.add_turn(actual_name, text)
        
        return conversation
    
    def __repr__(self) -> str:
        return f"Conversation(speakers={len(self._speakers)}, turns={len(self._turns)})"


# ============================================================================
# Turn-Taking Helpers
# ============================================================================

class TurnTakingStyle(str, Enum):
    """Style of turn-taking in conversation."""
    SEQUENTIAL = "sequential"     # One at a time, no overlap
    NATURAL = "natural"           # Small overlaps at turn boundaries
    FORMAL = "formal"             # Longer gaps, no interruptions
    CASUAL = "casual"             # More interruptions, less formal


def apply_turn_taking_style(
    conversation: Conversation,
    style: TurnTakingStyle,
) -> None:
    """Apply a turn-taking style to a conversation.
    
    Modifies the conversation config and turn timings to match the style.
    """
    if style == TurnTakingStyle.SEQUENTIAL:
        conversation.config.turn_gap_ms = 300.0
        conversation.config.crossfade_ms = 0.0
    elif style == TurnTakingStyle.NATURAL:
        conversation.config.turn_gap_ms = 150.0
        conversation.config.crossfade_ms = 100.0
    elif style == TurnTakingStyle.FORMAL:
        conversation.config.turn_gap_ms = 500.0
        conversation.config.crossfade_ms = 50.0
    elif style == TurnTakingStyle.CASUAL:
        conversation.config.turn_gap_ms = 100.0
        conversation.config.crossfade_ms = 150.0


# ============================================================================
# Crossfade Helpers
# ============================================================================

@dataclass
class CrossfadeConfig:
    """Configuration for crossfades between turns."""
    duration_ms: float = 100.0
    curve: str = "linear"  # "linear", "equal_power", "logarithmic"
    
    # When to apply
    apply_on_speaker_change: bool = True
    apply_on_overlap: bool = True
    apply_always: bool = False


def calculate_crossfades(
    conversation: Conversation,
    config: CrossfadeConfig,
) -> list[tuple[int, int, float]]:
    """Calculate crossfade points for a conversation.
    
    Returns:
        List of (turn_index_a, turn_index_b, crossfade_duration_ms)
    """
    crossfades = []
    
    for i in range(len(conversation._turns) - 1):
        turn_a = conversation._turns[i]
        turn_b = conversation._turns[i + 1]
        
        should_crossfade = False
        
        if config.apply_always:
            should_crossfade = True
        elif config.apply_on_speaker_change and turn_a.speaker != turn_b.speaker:
            should_crossfade = True
        elif config.apply_on_overlap and turn_b.overlap_ms > 0:
            should_crossfade = True
        
        if should_crossfade:
            crossfades.append((i, i + 1, config.duration_ms))
    
    return crossfades
