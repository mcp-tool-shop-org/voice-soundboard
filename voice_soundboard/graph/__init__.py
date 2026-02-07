"""
Graph module - The Canonical IR.

The ControlGraph is passed from compiler to engine.

STABILITY: GRAPH_VERSION is bumped on breaking changes.
"""

from voice_soundboard.graph.types import (
    GRAPH_VERSION,
    ControlGraph,
    TokenEvent,
    SpeakerRef,
    Paralinguistic,
    ParalinguisticEvent,
)

__all__ = [
    "GRAPH_VERSION",
    "ControlGraph",
    "TokenEvent",
    "SpeakerRef",
    "Paralinguistic",
    "ParalinguisticEvent",
]
