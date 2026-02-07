"""
Graph Types - The Canonical Intermediate Representation.

The ControlGraph is the single source of truth between compilation and synthesis.
All features (emotion, SSML, style) compile down to this representation.
Engine backends lower this to their specific format.

Design principle: Expressive, not minimal. Backends ignore fields they don't support.

STABILITY (v1 - Frozen):
    This schema is STABLE as of v2.0.0. It has been validated against multiple
    backends (Kokoro, Piper) with different characteristics:
    - Sample rates (22kHz, 24kHz)
    - Speed semantics (multiplier vs length_scale)
    - Voice systems (ID-based, multi-speaker)
    
    Changes to ControlGraph, TokenEvent, or SpeakerRef are breaking changes.
    Bump GRAPH_VERSION if you must modify these types.
    Treat modifications as v3 material unless absolutely necessary.
    
    The graph captures INTENT, not execution details:
    - speed is semantic (2.0 = faster)
    - sample_rate belongs to backends
    - voice resolution is backend-specific
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from enum import Enum

# Graph schema version. Bump on breaking changes to ControlGraph/TokenEvent/SpeakerRef.
# Backends can check this to ensure compatibility.
GRAPH_VERSION = 1


class Paralinguistic(str, Enum):
    """Non-speech vocalizations that some engines support."""
    LAUGH = "laugh"
    SIGH = "sigh"
    BREATH = "breath"
    GASP = "gasp"
    CRY = "cry"
    COUGH = "cough"
    YAWN = "yawn"
    HUM = "hum"


@dataclass
class ParalinguisticEvent:
    """A time-bound non-speech event on the timeline.
    
    IMPORTANT: Events are NOT tokens. They occupy timeline positions
    and must never overlap with tokens. This distinction is critical:
    
        Tokens = speech content with prosody
        Events = non-speech sounds at specific times
    
    Backends lower these differently:
        - Chatterbox: native tags (<laugh intensity="0.8"/>)
        - Piper: silence + prosody shaping (lossy)
        - Kokoro: special token IDs or energy curves
        - F5-TTS: embedding modulation
    
    Lossy lowering is acceptable. Unsupported events become pauses.
    """
    type: Paralinguistic
    
    # Timeline position (seconds from graph start)
    start_time: float
    duration: float = 0.2  # Default 200ms
    
    # Intensity/expressiveness (0.0-1.0, backends interpret freely)
    intensity: float = 1.0
    
    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


@dataclass
class TokenEvent:
    """Single unit of speech intent.
    
    Represents a segment of text with prosody modifiers.
    The compiler produces these; the engine consumes them.
    
    FROZEN (v2.0.0): Changes to this class require GRAPH_VERSION bump.
    """
    text: str
    
    # Prosody modifiers (1.0 = neutral, applied multiplicatively)
    pitch_scale: float = 1.0
    energy_scale: float = 1.0
    duration_scale: float = 1.0
    
    # Optional annotations
    phonemes: list[str] | None = None     # Pre-phonemized (if available)
    paralinguistic: Paralinguistic | None = None
    emphasis: float = 1.0                  # From SSML <emphasis>
    
    # Pause after this token (seconds, 0 = no pause)
    pause_after: float = 0.0


@dataclass
class SpeakerRef:
    """Speaker identity - resolved at compile time.
    
    FROZEN (v2.0.0): Changes to this class require GRAPH_VERSION bump.
    
    Types:
        voice_id: A known voice identifier (e.g., "af_bella")
        embedding: A speaker embedding vector (from voice cloning)
        preset: A named preset that maps to voice + settings
    
    IMPORTANT - Voice Cloning Boundary:
        This type holds EMBEDDINGS ONLY, never raw audio.
        The compiler extracts embeddings from reference audio.
        The engine receives only the embedding vector.
        Raw waveforms must never cross this boundary.
        
        This constraint is critical for:
        - Security (no arbitrary audio in synthesis path)
        - Performance (embeddings are small, audio is large)
        - Testability (embeddings are deterministic)
    """
    type: Literal["voice_id", "embedding", "preset"]
    value: str | list[float]  # voice_id/preset: str, embedding: list[float]
    
    # Metadata (for debugging/logging)
    name: str | None = None
    
    @classmethod
    def from_voice(cls, voice_id: str) -> SpeakerRef:
        """Create reference from a known voice ID."""
        return cls(type="voice_id", value=voice_id, name=voice_id)
    
    @classmethod
    def from_embedding(cls, embedding: list[float], name: str = "cloned") -> SpeakerRef:
        """Create reference from a speaker embedding vector.
        
        The embedding should be extracted by the compiler from reference audio.
        The engine never sees the original audio - only this vector.
        """
        return cls(type="embedding", value=embedding, name=name)
    
    @classmethod
    def from_preset(cls, preset_name: str) -> SpeakerRef:
        """Create reference from a named preset."""
        return cls(type="preset", value=preset_name, name=preset_name)


@dataclass
class ControlGraph:
    """The canonical IR. Compiler emits this; engine backends consume it.
    
    FROZEN (v2.0.0): Changes to this class require GRAPH_VERSION bump.
    
    This is the contract between the feature layer and the synthesis layer.
    All SSML, emotion, style interpretation happens BEFORE this object exists.
    After compilation, those concepts are gone - only data remains.
    
    Timeline Model:
        The graph has two parallel tracks:
        1. tokens: Sequential speech content
        2. events: Time-positioned non-speech events (laughs, sighs, etc.)
        
        INVARIANT: Events must not overlap with tokens.
        Events may precede, follow, or fill pauses between tokens.
        This keeps lowering deterministic across backends.
    
    Example:
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello world!")],
            speaker=SpeakerRef.from_voice("af_bella"),
            events=[ParalinguisticEvent(Paralinguistic.LAUGH, start_time=0.0)],
        )
        pcm = engine.synthesize(graph)
    """
    tokens: list[TokenEvent]
    speaker: SpeakerRef
    
    # Timeline events (paralinguistics, non-speech sounds)
    events: list[ParalinguisticEvent] = field(default_factory=list)
    
    # Global prosody (applied on top of per-token modifiers)
    global_speed: float = 1.0
    global_pitch: float = 1.0
    
    # Output settings
    sample_rate: int = 24000
    
    # Metadata (not used by engine, for debugging)
    source_text: str | None = field(default=None, repr=False)
    
    @property
    def text(self) -> str:
        """Reconstruct full text from tokens."""
        return " ".join(t.text for t in self.tokens)
    
    @property
    def total_pause(self) -> float:
        """Total explicit pause time in the graph."""
        return sum(t.pause_after for t in self.tokens)
    
    def validate(self) -> list[str]:
        """Check graph integrity. Returns list of issues (empty = valid)."""
        issues = []
        
        if not self.tokens:
            issues.append("Graph has no tokens")
        
        if self.global_speed <= 0:
            issues.append(f"Invalid global_speed: {self.global_speed}")
        
        # Validate events don't overlap (events have explicit times)
        for i, event in enumerate(self.events):
            if event.start_time < 0:
                issues.append(f"Event {i} has negative start_time: {event.start_time}")
            if event.duration <= 0:
                issues.append(f"Event {i} has invalid duration: {event.duration}")
            if not 0.0 <= event.intensity <= 1.0:
                issues.append(f"Event {i} has invalid intensity: {event.intensity}")
            
            # Check for overlapping events
            for j, other in enumerate(self.events[i+1:], start=i+1):
                if event.start_time < other.end_time and other.start_time < event.end_time:
                    issues.append(f"Events {i} and {j} overlap")
        
        if self.global_pitch <= 0:
            issues.append(f"Invalid global_pitch: {self.global_pitch}")
        
        for i, token in enumerate(self.tokens):
            if token.pitch_scale <= 0:
                issues.append(f"Token {i}: invalid pitch_scale {token.pitch_scale}")
            if token.duration_scale <= 0:
                issues.append(f"Token {i}: invalid duration_scale {token.duration_scale}")
        
        return issues
