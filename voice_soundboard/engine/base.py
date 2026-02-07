"""
Engine Base - TTSBackend protocol.

The engine NEVER imports from compiler. This is enforced architecturally.
All backends implement synthesize(graph) -> PCM.

BACKEND CONTRACT:
    Backends MUST:
        - Accept a ControlGraph (the canonical IR)
        - Perform lowering internally (graph → backend-specific format)
        - Define their own sample_rate (not normalized)
        - Define streaming semantics (chunked vs true streaming)
        - Return float32 PCM audio in range [-1, 1]
    
    Backends MUST NOT:
        - Import from compiler/
        - Parse SSML or interpret emotion (that's compiler work)
        - Modify the input graph
        - Perform voice cloning (embedding comes pre-computed)
        - Normalize sample rates (let adapters resample if needed)
    
    Lowering pattern:
        Each backend implements _lower_*() methods to map graph fields
        to backend-specific parameters. This keeps the mapping explicit
        and backend-contained.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable, Iterator

import numpy as np

from voice_soundboard.graph import ControlGraph


@runtime_checkable
class TTSBackend(Protocol):
    """Protocol for TTS synthesis backends.
    
    Backends accept a ControlGraph (the canonical IR) and produce PCM audio.
    Each backend "lowers" the graph to its specific representation.
    
    The backend MUST NOT import anything from compiler/.
    Feature logic belongs in the compiler, not here.
    """
    
    @property
    def name(self) -> str:
        """Backend identifier (e.g., 'kokoro', 'piper')."""
        ...
    
    @property
    def sample_rate(self) -> int:
        """Output sample rate in Hz."""
        ...
    
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Synthesize audio from a ControlGraph.
        
        Args:
            graph: The compiled control graph
        
        Returns:
            PCM audio as float32 numpy array, shape (samples,)
        """
        ...


class BaseTTSBackend(ABC):
    """Base class for TTS backends with common functionality."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Backend identifier."""
        ...
    
    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Output sample rate."""
        ...
    
    @abstractmethod
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Synthesize audio from graph."""
        ...
    
    def synthesize_stream(self, graph: ControlGraph, chunk_size: int = 4096) -> Iterator[np.ndarray]:
        """Streaming synthesis - override for true streaming backends.
        
        Default implementation synthesizes fully then chunks.
        """
        audio = self.synthesize(graph)
        for i in range(0, len(audio), chunk_size):
            yield audio[i:i + chunk_size]
    
    def get_voices(self) -> list[str]:
        """Return list of supported voice IDs."""
        return []
    
    def supports_voice(self, voice_id: str) -> bool:
        """Check if this backend supports a voice."""
        voices = self.get_voices()
        return not voices or voice_id in voices
