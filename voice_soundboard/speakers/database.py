"""
Speaker Database - Store and retrieve speaker embeddings.

Provides a file-based database for managing speaker identities
for voice cloning workflows.

Usage:
    db = SpeakerDB("./speakers")
    
    # Add speaker from audio reference
    db.add("alice", "alice_reference.wav")
    
    # Get speaker reference
    speaker = db.get("alice")
    engine.speak("Hello!", speaker=speaker)
    
    # List speakers
    for name in db.list():
        print(name)
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

from voice_soundboard.graph import SpeakerRef
from voice_soundboard.cloning import extract_embedding, save_embedding, load_embedding

logger = logging.getLogger(__name__)


@dataclass
class SpeakerEntry:
    """A speaker entry in the database."""
    name: str
    embedding_file: str
    source_audio: str = ""
    description: str = ""
    created_at: str = ""
    tags: list[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "SpeakerEntry":
        return cls(
            name=data["name"],
            embedding_file=data["embedding_file"],
            source_audio=data.get("source_audio", ""),
            description=data.get("description", ""),
            created_at=data.get("created_at", ""),
            tags=data.get("tags", []),
        )


class SpeakerDB:
    """File-based speaker database.
    
    Stores speaker embeddings and metadata for voice cloning.
    
    Directory structure:
        ./speakers/
            index.json          # Speaker index
            alice.vsemb         # Embedding file
            bob.vsemb           # Embedding file
            ...
    
    Example:
        db = SpeakerDB("./speakers")
        
        # Add from audio
        db.add("alice", "recordings/alice.wav", description="Customer Alice")
        
        # Add from existing embedding
        db.add_embedding("bob", embedding_list, description="Bob from sales")
        
        # Get as SpeakerRef
        speaker = db.get("alice")
        engine.speak("Hello!", speaker=speaker)
        
        # Search
        for entry in db.search(tags=["customer"]):
            print(entry.name)
    """
    
    INDEX_FILE = "index.json"
    
    def __init__(self, directory: Path | str):
        """Initialize speaker database.
        
        Args:
            directory: Directory to store speaker data
        """
        self.directory = Path(directory)
        self._index: dict[str, SpeakerEntry] = {}
        
        # Create directory if needed
        self.directory.mkdir(parents=True, exist_ok=True)
        
        # Load existing index
        self._load_index()
    
    def add(
        self,
        name: str,
        audio_path: Path | str,
        *,
        description: str = "",
        tags: list[str] | None = None,
        overwrite: bool = False,
    ) -> SpeakerEntry:
        """Add speaker from audio reference.
        
        Extracts embedding from audio and stores it.
        
        Args:
            name: Unique speaker name (alphanumeric, underscores)
            audio_path: Path to reference audio file
            description: Optional description
            tags: Optional tags for searching
            overwrite: Replace existing speaker with same name
        
        Returns:
            SpeakerEntry for the added speaker
        
        Raises:
            ValueError: If name exists and overwrite=False
        """
        name = self._validate_name(name)
        
        if name in self._index and not overwrite:
            raise ValueError(f"Speaker '{name}' already exists. Use overwrite=True to replace.")
        
        # Extract embedding
        logger.info(f"Extracting embedding for '{name}' from {audio_path}")
        embedding = extract_embedding(audio_path)
        
        # Save embedding
        emb_file = f"{name}.vsemb"
        emb_path = self.directory / emb_file
        save_embedding(embedding, emb_path, name=name, description=description)
        
        # Create entry
        entry = SpeakerEntry(
            name=name,
            embedding_file=emb_file,
            source_audio=str(Path(audio_path).name),
            description=description,
            created_at=datetime.now().isoformat(),
            tags=tags or [],
        )
        
        # Update index
        self._index[name] = entry
        self._save_index()
        
        logger.info(f"Added speaker '{name}' to database")
        return entry
    
    def add_embedding(
        self,
        name: str,
        embedding: list[float],
        *,
        description: str = "",
        tags: list[str] | None = None,
        overwrite: bool = False,
    ) -> SpeakerEntry:
        """Add speaker from existing embedding.
        
        Args:
            name: Unique speaker name
            embedding: Pre-extracted embedding
            description: Optional description
            tags: Optional tags
            overwrite: Replace existing speaker
        
        Returns:
            SpeakerEntry for the added speaker
        """
        name = self._validate_name(name)
        
        if name in self._index and not overwrite:
            raise ValueError(f"Speaker '{name}' already exists. Use overwrite=True to replace.")
        
        # Save embedding
        emb_file = f"{name}.vsemb"
        emb_path = self.directory / emb_file
        save_embedding(embedding, emb_path, name=name, description=description)
        
        # Create entry
        entry = SpeakerEntry(
            name=name,
            embedding_file=emb_file,
            source_audio="",
            description=description,
            created_at=datetime.now().isoformat(),
            tags=tags or [],
        )
        
        # Update index
        self._index[name] = entry
        self._save_index()
        
        logger.info(f"Added speaker '{name}' from embedding")
        return entry
    
    def get(self, name: str) -> SpeakerRef:
        """Get speaker reference by name.
        
        Args:
            name: Speaker name
        
        Returns:
            SpeakerRef that can be used with the engine
        
        Raises:
            KeyError: If speaker not found
        """
        if name not in self._index:
            raise KeyError(f"Speaker '{name}' not found in database")
        
        entry = self._index[name]
        emb_path = self.directory / entry.embedding_file
        embedding = load_embedding(emb_path)
        
        return SpeakerRef.from_embedding(embedding, name=name)
    
    def get_entry(self, name: str) -> SpeakerEntry:
        """Get speaker entry with metadata.
        
        Args:
            name: Speaker name
        
        Returns:
            SpeakerEntry with full metadata
        """
        if name not in self._index:
            raise KeyError(f"Speaker '{name}' not found")
        return self._index[name]
    
    def remove(self, name: str) -> bool:
        """Remove speaker from database.
        
        Args:
            name: Speaker name
        
        Returns:
            True if removed, False if not found
        """
        if name not in self._index:
            return False
        
        entry = self._index[name]
        
        # Remove embedding file
        emb_path = self.directory / entry.embedding_file
        if emb_path.exists():
            emb_path.unlink()
        
        # Remove from index
        del self._index[name]
        self._save_index()
        
        logger.info(f"Removed speaker '{name}'")
        return True
    
    def list(self) -> list[str]:
        """List all speaker names.
        
        Returns:
            List of speaker names
        """
        return list(self._index.keys())
    
    def __iter__(self) -> Iterator[SpeakerEntry]:
        """Iterate over all speaker entries."""
        return iter(self._index.values())
    
    def __len__(self) -> int:
        """Number of speakers in database."""
        return len(self._index)
    
    def __contains__(self, name: str) -> bool:
        """Check if speaker exists."""
        return name in self._index
    
    def search(
        self,
        *,
        tags: list[str] | None = None,
        query: str | None = None,
    ) -> list[SpeakerEntry]:
        """Search for speakers.
        
        Args:
            tags: Filter by tags (any match)
            query: Search in name and description
        
        Returns:
            Matching speaker entries
        """
        results = []
        
        for entry in self._index.values():
            # Tag filter
            if tags:
                if not any(t in entry.tags for t in tags):
                    continue
            
            # Query filter
            if query:
                query_lower = query.lower()
                if query_lower not in entry.name.lower() and query_lower not in entry.description.lower():
                    continue
            
            results.append(entry)
        
        return results
    
    def export(self, output_path: Path | str) -> Path:
        """Export database to a zip archive.
        
        Args:
            output_path: Path for output archive
        
        Returns:
            Path to created archive
        """
        output_path = Path(output_path)
        if output_path.suffix != '.zip':
            output_path = output_path.with_suffix('.zip')
        
        shutil.make_archive(
            str(output_path.with_suffix('')),
            'zip',
            self.directory,
        )
        
        return output_path
    
    def _validate_name(self, name: str) -> str:
        """Validate and normalize speaker name."""
        import re
        name = name.strip().lower()
        
        if not name:
            raise ValueError("Speaker name cannot be empty")
        
        if not re.match(r'^[a-z0-9_]+$', name):
            raise ValueError(
                f"Invalid speaker name '{name}'. "
                "Use only lowercase letters, numbers, and underscores."
            )
        
        return name
    
    def _load_index(self):
        """Load index from disk."""
        index_path = self.directory / self.INDEX_FILE
        
        if not index_path.exists():
            self._index = {}
            return
        
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._index = {
                name: SpeakerEntry.from_dict(entry)
                for name, entry in data.get("speakers", {}).items()
            }
            
        except Exception as e:
            logger.warning(f"Failed to load speaker index: {e}")
            self._index = {}
    
    def _save_index(self):
        """Save index to disk."""
        index_path = self.directory / self.INDEX_FILE
        
        data = {
            "version": "1.0",
            "speakers": {
                name: entry.to_dict()
                for name, entry in self._index.items()
            },
        }
        
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
