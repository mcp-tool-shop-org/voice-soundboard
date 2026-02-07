"""
Embedding Storage - Save and load speaker embeddings.

Provides standardized storage format for speaker embeddings,
enabling persistence and sharing.

Usage:
    from voice_soundboard.cloning import save_embedding, load_embedding
    
    # Save embedding
    save_embedding(embedding, "speaker_alice.vsemb")
    
    # Load embedding
    embedding = load_embedding("speaker_alice.vsemb")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from voice_soundboard.cloning.extractor import EmbeddingFormat, EmbeddingResult

logger = logging.getLogger(__name__)


# File extension for voice soundboard embeddings
EMBEDDING_EXTENSION = ".vsemb"


@dataclass
class EmbeddingFile:
    """Standardized embedding file format.
    
    Stores embedding with metadata for version tracking
    and validation.
    """
    # Core data
    embedding: list[float]
    format: str
    
    # Metadata
    name: str = ""
    description: str = ""
    source_file: str = ""
    source_hash: str = ""
    duration_seconds: float = 0.0
    sample_rate: int = 0
    
    # Version info
    version: str = "1.0"
    created_at: str = ""
    voice_soundboard_version: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmbeddingFile":
        """Create from dictionary."""
        return cls(
            embedding=data["embedding"],
            format=data["format"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            source_file=data.get("source_file", ""),
            source_hash=data.get("source_hash", ""),
            duration_seconds=data.get("duration_seconds", 0.0),
            sample_rate=data.get("sample_rate", 0),
            version=data.get("version", "1.0"),
            created_at=data.get("created_at", ""),
            voice_soundboard_version=data.get("voice_soundboard_version", ""),
        )
    
    @classmethod
    def from_result(
        cls,
        result: EmbeddingResult,
        name: str = "",
        description: str = "",
    ) -> "EmbeddingFile":
        """Create from EmbeddingResult."""
        from voice_soundboard import __version__
        
        return cls(
            embedding=result.embedding,
            format=result.format.value,
            name=name or result.source_file,
            description=description,
            source_file=result.source_file,
            source_hash=result.source_hash,
            duration_seconds=result.duration_seconds,
            sample_rate=result.sample_rate,
            version="1.0",
            created_at=datetime.now().isoformat(),
            voice_soundboard_version=__version__,
        )


def save_embedding(
    embedding: list[float] | EmbeddingResult | EmbeddingFile,
    path: Path | str,
    *,
    name: str = "",
    description: str = "",
    format: str = "resemblyzer",
) -> Path:
    """Save speaker embedding to file.
    
    Args:
        embedding: Embedding data (list, EmbeddingResult, or EmbeddingFile)
        path: Output path (will add .vsemb extension if needed)
        name: Optional speaker name
        description: Optional description
        format: Embedding format if embedding is a list
    
    Returns:
        Path to saved file
    
    Example:
        embedding = extract_embedding("alice.wav")
        save_embedding(embedding, "speakers/alice")
        # Creates: speakers/alice.vsemb
    """
    path = Path(path)
    
    # Add extension if needed
    if path.suffix != EMBEDDING_EXTENSION:
        path = path.with_suffix(EMBEDDING_EXTENSION)
    
    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to EmbeddingFile
    if isinstance(embedding, EmbeddingFile):
        emb_file = embedding
    elif isinstance(embedding, EmbeddingResult):
        emb_file = EmbeddingFile.from_result(embedding, name=name, description=description)
    else:
        # Raw list
        from voice_soundboard import __version__
        emb_file = EmbeddingFile(
            embedding=embedding,
            format=format,
            name=name or path.stem,
            description=description,
            version="1.0",
            created_at=datetime.now().isoformat(),
            voice_soundboard_version=__version__,
        )
    
    # Save as JSON
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(emb_file.to_dict(), f, indent=2)
    
    logger.info(f"Saved embedding to {path}")
    return path


def load_embedding(path: Path | str) -> list[float]:
    """Load speaker embedding from file.
    
    Args:
        path: Path to embedding file
    
    Returns:
        Embedding as list of floats
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid
    
    Example:
        embedding = load_embedding("speakers/alice.vsemb")
        speaker = SpeakerRef.from_embedding(embedding)
    """
    path = Path(path)
    
    # Add extension if needed
    if path.suffix != EMBEDDING_EXTENSION and not path.exists():
        path = path.with_suffix(EMBEDDING_EXTENSION)
    
    if not path.exists():
        raise FileNotFoundError(f"Embedding file not found: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if "embedding" not in data:
        raise ValueError(f"Invalid embedding file: missing 'embedding' field")
    
    return data["embedding"]


def load_embedding_file(path: Path | str) -> EmbeddingFile:
    """Load full embedding file with metadata.
    
    Args:
        path: Path to embedding file
    
    Returns:
        EmbeddingFile with full metadata
    """
    path = Path(path)
    
    if path.suffix != EMBEDDING_EXTENSION and not path.exists():
        path = path.with_suffix(EMBEDDING_EXTENSION)
    
    if not path.exists():
        raise FileNotFoundError(f"Embedding file not found: {path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return EmbeddingFile.from_dict(data)


def list_embeddings(directory: Path | str) -> list[EmbeddingFile]:
    """List all embedding files in a directory.
    
    Args:
        directory: Directory to search
    
    Returns:
        List of EmbeddingFile objects
    """
    directory = Path(directory)
    
    if not directory.exists():
        return []
    
    embeddings = []
    for path in directory.glob(f"*{EMBEDDING_EXTENSION}"):
        try:
            emb = load_embedding_file(path)
            embeddings.append(emb)
        except Exception as e:
            logger.warning(f"Failed to load {path}: {e}")
    
    return embeddings
