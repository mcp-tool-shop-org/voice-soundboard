"""
Cloning Module - Voice cloning infrastructure for v2.1.

v2.1 Feature (P2): Foundation for v3 voice cloning.

This module provides:
- Embedding extraction from reference audio
- Embedding storage format
- SpeakerRef.from_embedding() integration

In scope (v2.1):
    - Embedding extraction API
    - Embedding storage format
    - Integration with SpeakerRef

Out of scope (deferred to v3):
    - Production-quality cloning
    - Quality guarantees
    - Fine-tuning

Usage:
    from voice_soundboard.cloning import extract_embedding
    
    embedding = extract_embedding("reference.wav")
    graph = compile_request("Hello!", speaker=SpeakerRef.from_embedding(embedding))
"""

from voice_soundboard.cloning.extractor import (
    extract_embedding,
    EmbeddingExtractor,
    EmbeddingFormat,
)
from voice_soundboard.cloning.storage import (
    save_embedding,
    load_embedding,
    EmbeddingFile,
)

__all__ = [
    "extract_embedding",
    "EmbeddingExtractor",
    "EmbeddingFormat",
    "save_embedding",
    "load_embedding",
    "EmbeddingFile",
]
