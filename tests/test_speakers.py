"""
Tests for v2.1 speaker database features.

Tests SpeakerDB for managing speaker identities.
"""

import pytest
import tempfile
from pathlib import Path
import numpy as np

from voice_soundboard.speakers import SpeakerDB, SpeakerEntry


class TestSpeakerEntry:
    """Tests for SpeakerEntry dataclass."""
    
    def test_create_entry(self):
        """Create a speaker entry."""
        embedding = np.random.randn(256).astype(np.float32)
        
        entry = SpeakerEntry(
            speaker_id="john_doe",
            name="John Doe",
            embedding=embedding,
        )
        
        assert entry.speaker_id == "john_doe"
        assert entry.name == "John Doe"
        assert len(entry.embedding) == 256
    
    def test_entry_with_metadata(self):
        """Create entry with additional metadata."""
        embedding = np.random.randn(256).astype(np.float32)
        
        entry = SpeakerEntry(
            speaker_id="jane_doe",
            name="Jane Doe",
            embedding=embedding,
            tags=["female", "english", "professional"],
            description="Professional narrator voice",
        )
        
        assert "female" in entry.tags
        assert entry.description == "Professional narrator voice"


class TestSpeakerDB:
    """Tests for SpeakerDB."""
    
    @pytest.fixture
    def sample_embedding(self):
        """Create a sample embedding."""
        return np.random.randn(256).astype(np.float32)
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = SpeakerDB(Path(tmpdir))
            yield db
    
    def test_add_speaker(self, temp_db, sample_embedding):
        """Add a speaker to database."""
        temp_db.add(
            speaker_id="speaker1",
            name="Speaker One",
            embedding=sample_embedding,
        )
        
        entry = temp_db.get("speaker1")
        
        assert entry is not None
        assert entry.name == "Speaker One"
    
    def test_get_nonexistent(self, temp_db):
        """Getting nonexistent speaker returns None."""
        entry = temp_db.get("nonexistent")
        assert entry is None
    
    def test_remove_speaker(self, temp_db, sample_embedding):
        """Remove a speaker from database."""
        temp_db.add("to_remove", "Remove Me", sample_embedding)
        
        # Verify it exists
        assert temp_db.get("to_remove") is not None
        
        # Remove it
        removed = temp_db.remove("to_remove")
        
        assert removed is True
        assert temp_db.get("to_remove") is None
    
    def test_remove_nonexistent(self, temp_db):
        """Removing nonexistent speaker returns False."""
        removed = temp_db.remove("nonexistent")
        assert removed is False
    
    def test_list_speakers(self, temp_db, sample_embedding):
        """List all speakers in database."""
        temp_db.add("speaker1", "One", sample_embedding)
        temp_db.add("speaker2", "Two", sample_embedding)
        temp_db.add("speaker3", "Three", sample_embedding)
        
        speakers = temp_db.list()
        
        assert len(speakers) == 3
        ids = [s.speaker_id for s in speakers]
        assert "speaker1" in ids
        assert "speaker2" in ids
        assert "speaker3" in ids
    
    def test_search_by_name(self, temp_db, sample_embedding):
        """Search speakers by name."""
        temp_db.add("john", "John Smith", sample_embedding)
        temp_db.add("jane", "Jane Doe", sample_embedding)
        temp_db.add("bob", "Bob Smith", sample_embedding)
        
        results = temp_db.search("Smith")
        
        assert len(results) == 2
        names = [r.name for r in results]
        assert "John Smith" in names
        assert "Bob Smith" in names
    
    def test_search_by_tag(self, temp_db, sample_embedding):
        """Search speakers by tag."""
        temp_db.add("narrator1", "Pro Narrator", sample_embedding, tags=["professional", "english"])
        temp_db.add("narrator2", "Casual Voice", sample_embedding, tags=["casual", "english"])
        temp_db.add("narrator3", "German Pro", sample_embedding, tags=["professional", "german"])
        
        results = temp_db.search(tag="professional")
        
        assert len(results) == 2
    
    def test_persistence(self, sample_embedding):
        """Database persists across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir)
            
            # Create and populate
            db1 = SpeakerDB(db_path)
            db1.add("persistent", "Persistent Speaker", sample_embedding)
            
            # Create new instance pointing to same path
            db2 = SpeakerDB(db_path)
            
            entry = db2.get("persistent")
            assert entry is not None
            assert entry.name == "Persistent Speaker"
    
    def test_update_speaker(self, temp_db, sample_embedding):
        """Update existing speaker."""
        temp_db.add("updatable", "Original Name", sample_embedding)
        
        # Update with new name
        new_embedding = np.random.randn(256).astype(np.float32)
        temp_db.add("updatable", "Updated Name", new_embedding)
        
        entry = temp_db.get("updatable")
        assert entry.name == "Updated Name"
    
    def test_count(self, temp_db, sample_embedding):
        """Count speakers in database."""
        assert temp_db.count() == 0
        
        temp_db.add("s1", "One", sample_embedding)
        assert temp_db.count() == 1
        
        temp_db.add("s2", "Two", sample_embedding)
        assert temp_db.count() == 2
