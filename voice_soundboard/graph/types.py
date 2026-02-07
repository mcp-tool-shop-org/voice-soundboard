"""
Graph Types - The Canonical Intermediate Representation.

The ControlGraph is the single source of truth between compilation and synthesis.
All features (emotion, SSML, style) compile down to this representation.
Engine backends lower this to their specific format.

Design principle: Expressive, not minimal. Backends ignore fields they don't support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from enum import Enum


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
class TokenEvent:
    """Single unit of speech intent.
    
    Represents a segment of text with prosody modifiers.
    The compiler produces these; the engine consumes them.
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
    
    Types:
        voice_id: A known voice identifier (e.g., "af_bella")
        embedding: A speaker embedding vector (from voice cloning)
        preset: A named preset that maps to voice + settings
    """
    type: Literal["voice_id", "embedding", "preset"]
    value: str | list[float]
    
    # Metadata (for debugging/logging)
    name: str | None = None
    
    @classmethod
    def from_voice(cls, voice_id: str) -> SpeakerRef:
        return cls(type="voice_id", value=voice_id, name=voice_id)
    
    @classmethod
    def from_embedding(cls, embedding: list[float], name: str = "cloned") -> SpeakerRef:
        return cls(type="embedding", value=embedding, name=name)
    
    @classmethod
    def from_preset(cls, preset_name: str) -> SpeakerRef:
        return cls(type="preset", value=preset_name, name=preset_name)


@dataclass
class ControlGraph:
    """The canonical IR. Compiler emits this; engine backends consume it.
    
    This is the contract between the feature layer and the synthesis layer.
    All SSML, emotion, style interpretation happens BEFORE this object exists.
    After compilation, those concepts are gone - only data remains.
    
    Example:
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello world!")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        pcm = engine.synthesize(graph)
    """
    tokens: list[TokenEvent]
    speaker: SpeakerRef
    
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
        
        if self.global_pitch <= 0:
            issues.append(f"Invalid global_pitch: {self.global_pitch}")
        
        for i, token in enumerate(self.tokens):
            if token.pitch_scale <= 0:
                issues.append(f"Token {i}: invalid pitch_scale {token.pitch_scale}")
            if token.duration_scale <= 0:
                issues.append(f"Token {i}: invalid duration_scale {token.duration_scale}")
        
        return issues
