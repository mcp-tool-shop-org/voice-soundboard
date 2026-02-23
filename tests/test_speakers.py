"""
Tests for v2.5 speaker database features.

Tests SpeakerDB for managing speaker identities.
"""

import pytest
import tempfile
from pathlib import Path
import numpy as np
from unittest.mock import Mock, patch

from voice_soundboard.speakers.database import SpeakerDB, SpeakerEntry


class TestSpeakerEntry:
    """Tests for SpeakerEntry dataclass."""
    
    def test_create_entry(self):
        """Create a speaker entry."""
        entry = SpeakerEntry(
            name="john_doe",
            embedding_file="john_doe.vsemb",
        )
        
        assert entry.name == "john_doe"
        assert entry.embedding_file == "john_doe.vsemb"
    
    def test_entry_with_metadata(self):
        """Create entry with additional metadata."""
        entry = SpeakerEntry(
            name="jane_doe",
            embedding_file="jane_doe.vsemb",
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
        return np.random.randn(256).astype(np.float32).tolist()
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = SpeakerDB(Path(tmpdir))
            yield db
    
    def test_add_speaker(self, temp_db, sample_embedding):
        """Add a speaker to database."""
        import soundfile as sf
        
        with patch('voice_soundboard.speakers.database.extract_embedding') as mock_extract:
            mock_extract.return_value = sample_embedding
            
            dummy_path = Path("tests/dummy.wav")
            # Create valid wav file
            audio = np.zeros(16000, dtype=np.float32)
            sf.write(str(dummy_path), audio, 16000)
            
            try:
                # New API: add(name, audio_path, description=...)
                temp_db.add(
                    name="speaker1", 
                    audio_path=dummy_path,
                    description="Speaker One"
                )
            finally:
                if dummy_path.exists():
                    try: dummy_path.unlink()
                    except: pass
        
        entry = temp_db.get_entry("speaker1")
        
        assert entry is not None
        assert entry.name == "speaker1"
        assert entry.description == "Speaker One"
    
    def test_get_nonexistent(self, temp_db):
        """Getting nonexistent speaker raises KeyError."""
        with pytest.raises(KeyError):
            temp_db.get("nonexistent")
            
    def test_remove_speaker(self, temp_db, sample_embedding):
        """Remove a speaker from database."""
        import soundfile as sf
        
        with patch('voice_soundboard.speakers.database.extract_embedding') as mock_extract:
            mock_extract.return_value = sample_embedding
            dummy_path = Path("tests/dummy.wav")
            audio = np.zeros(16000, dtype=np.float32)
            sf.write(str(dummy_path), audio, 16000)
            
            try:
                temp_db.add(name="to_remove", audio_path=dummy_path, description="Remove Me")
                
                # Check removal
                success = temp_db.remove("to_remove")
                assert success
                
                # Verify removal
                with pytest.raises(KeyError):
                    temp_db.get("to_remove")
                    
            finally:
                if dummy_path.exists():
                    try: dummy_path.unlink()
                    except: pass
    
    def test_remove_nonexistent(self, temp_db):
        """Removing nonexistent speaker returns False."""
        removed = temp_db.remove("nonexistent")
        assert removed is False
    
    def test_list_speakers(self, temp_db, sample_embedding):
        """List all speakers in database."""
        with patch('voice_soundboard.speakers.database.extract_embedding') as mock_extract:
            mock_extract.return_value = sample_embedding
            dummy_path = Path("tests/dummy.wav")
            if not dummy_path.exists(): dummy_path.touch()
            
            temp_db.add("speaker1", dummy_path, description="One")
            temp_db.add("speaker2", dummy_path, description="Two")
            temp_db.add("speaker3", dummy_path, description="Three")
            
            try: dummy_path.unlink()
            except: pass
        
        speakers = temp_db.list()
        
        # New API: list() returns list of strings (names)
        assert len(speakers) == 3
        assert "speaker1" in speakers
        assert "speaker2" in speakers
        assert "speaker3" in speakers
    
    def test_search_by_name(self, temp_db, sample_embedding):
        """Search speakers by name."""
        with patch('voice_soundboard.speakers.database.extract_embedding') as mock_extract:
            mock_extract.return_value = sample_embedding
            dummy_path = Path("tests/dummy.wav")
            if not dummy_path.exists(): dummy_path.touch()
            
            # Using name field as the text field to match 'Smith'
            # Although 'name' argument in add is ID.
            # But search checks name (ID) and description.
            # So I can put "John Smith" in description.
            
            temp_db.add("john", dummy_path, description="John Smith")
            temp_db.add("jane", dummy_path, description="Jane Doe")
            temp_db.add("bob", dummy_path, description="Bob Smith")
            
            try: dummy_path.unlink()
            except: pass
        
        results = temp_db.search(query="Smith")
        
        assert len(results) == 2
        names = [r.name for r in results]
        assert "john" in names
        assert "bob" in names
    
    def test_search_by_tag(self, temp_db, sample_embedding):
        """Search speakers by tag."""
        with patch('voice_soundboard.speakers.database.extract_embedding') as mock_extract:
            mock_extract.return_value = sample_embedding
            dummy_path = Path("tests/dummy.wav")
            if not dummy_path.exists(): dummy_path.touch()
            
            # tags list argument
            temp_db.add("narrator1", dummy_path, tags=["professional", "english"])
            temp_db.add("narrator2", dummy_path, tags=["casual", "english"])
            temp_db.add("narrator3", dummy_path, tags=["professional", "german"])
            
            try: dummy_path.unlink()
            except: pass
        
        # argument name 'tags' (list)
        results = temp_db.search(tags=["professional"])
        
        assert len(results) == 2
    
    def test_persistence(self, sample_embedding):
        """Database persists across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir)
            dummy_path = Path("tests/dummy.wav")
            if not dummy_path.exists(): dummy_path.touch()
            
            try:
                # Create and populate
                db1 = SpeakerDB(db_path)
                with patch('voice_soundboard.speakers.database.extract_embedding') as m:
                    m.return_value = sample_embedding
                    db1.add("persistent", dummy_path, description="Persistent Speaker")
                
                # Create new instance pointing to same path
                db2 = SpeakerDB(db_path)
                
                # db.get returns SpeakerRef which has name
                # db.get_entry returns SpeakerEntry which has description
                entry = db2.get_entry("persistent")
                assert entry is not None
                assert entry.description == "Persistent Speaker"

            finally:
                if dummy_path.exists():
                    try: dummy_path.unlink()
                    except: pass
    
    def test_update_speaker(self, temp_db, sample_embedding):
        """Update existing speaker."""
        import soundfile as sf
        
        with patch('voice_soundboard.speakers.database.extract_embedding') as mock_extract:
            mock_extract.return_value = sample_embedding
            dummy_path = Path("tests/dummy.wav")
            # Create valid wav just in case mock leaks or logic changes
            audio = np.zeros(16000, dtype=np.float32)
            sf.write(str(dummy_path), audio, 16000)
            
            try:
                temp_db.add("updatable", dummy_path, description="Original Name")
                
                # Update with new description (and new embedding technically)
                new_embedding = np.random.randn(256).astype(np.float32).tolist()
                mock_extract.return_value = new_embedding
                
                # Must use overwrite=True
                temp_db.add("updatable", dummy_path, description="Updated Name", overwrite=True)
                
            finally:
                if dummy_path.exists():
                    try: dummy_path.unlink()
                    except: pass
        
        entry = temp_db.get_entry("updatable")
        assert entry.description == "Updated Name"
    
    def test_count(self, temp_db, sample_embedding):
        """Count speakers in database."""
        with patch('voice_soundboard.speakers.database.extract_embedding') as m:
            m.return_value = sample_embedding
            dummy_path = Path("tests/dummy.wav")
            if not dummy_path.exists(): dummy_path.touch()
            
            assert len(temp_db) == 0
            
            temp_db.add("s1", dummy_path, description="One")
            assert len(temp_db) == 1
            
            temp_db.add("s2", dummy_path, description="Two")
            assert len(temp_db) == 2
            
            try: dummy_path.unlink()
            except: pass
