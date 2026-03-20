"""
Tests for v2.5 speaker database features.

Tests SpeakerDB for managing speaker identities.
"""

import json
import pytest
import tempfile
from pathlib import Path
import numpy as np
from unittest.mock import patch

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
                    try:
                        dummy_path.unlink()
                    except Exception:
                        pass
        
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
                    try:
                        dummy_path.unlink()
                    except Exception:
                        pass
    
    def test_remove_nonexistent(self, temp_db):
        """Removing nonexistent speaker returns False."""
        removed = temp_db.remove("nonexistent")
        assert removed is False
    
    def test_list_speakers(self, temp_db, sample_embedding):
        """List all speakers in database."""
        with patch('voice_soundboard.speakers.database.extract_embedding') as mock_extract:
            mock_extract.return_value = sample_embedding
            dummy_path = Path("tests/dummy.wav")
            if not dummy_path.exists():
                dummy_path.touch()
            
            temp_db.add("speaker1", dummy_path, description="One")
            temp_db.add("speaker2", dummy_path, description="Two")
            temp_db.add("speaker3", dummy_path, description="Three")
            
            try:
                dummy_path.unlink()
            except Exception:
                pass
        
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
            if not dummy_path.exists():
                dummy_path.touch()
            
            # Using name field as the text field to match 'Smith'
            # Although 'name' argument in add is ID.
            # But search checks name (ID) and description.
            # So I can put "John Smith" in description.
            
            temp_db.add("john", dummy_path, description="John Smith")
            temp_db.add("jane", dummy_path, description="Jane Doe")
            temp_db.add("bob", dummy_path, description="Bob Smith")
            
            try:
                dummy_path.unlink()
            except Exception:
                pass
        
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
            if not dummy_path.exists():
                dummy_path.touch()
            
            # tags list argument
            temp_db.add("narrator1", dummy_path, tags=["professional", "english"])
            temp_db.add("narrator2", dummy_path, tags=["casual", "english"])
            temp_db.add("narrator3", dummy_path, tags=["professional", "german"])
            
            try:
                dummy_path.unlink()
            except Exception:
                pass
        
        # argument name 'tags' (list)
        results = temp_db.search(tags=["professional"])
        
        assert len(results) == 2
    
    def test_persistence(self, sample_embedding):
        """Database persists across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir)
            dummy_path = Path("tests/dummy.wav")
            if not dummy_path.exists():
                dummy_path.touch()
            
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
                    try:
                        dummy_path.unlink()
                    except Exception:
                        pass
    
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
                    try:
                        dummy_path.unlink()
                    except Exception:
                        pass
        
        entry = temp_db.get_entry("updatable")
        assert entry.description == "Updated Name"
    
    def test_count(self, temp_db, sample_embedding):
        """Count speakers in database."""
        with patch('voice_soundboard.speakers.database.extract_embedding') as m:
            m.return_value = sample_embedding
            dummy_path = Path("tests/dummy.wav")
            if not dummy_path.exists():
                dummy_path.touch()
            
            assert len(temp_db) == 0
            
            temp_db.add("s1", dummy_path, description="One")
            assert len(temp_db) == 1
            
            temp_db.add("s2", dummy_path, description="Two")
            assert len(temp_db) == 2

            try:
                dummy_path.unlink()
            except Exception:
                pass


class TestSpeakerEntryExtended:
    """Extended tests for SpeakerEntry dataclass."""

    def test_entry_defaults(self):
        """Entry has correct defaults when no optionals given."""
        entry = SpeakerEntry(name="test", embedding_file="test.vsemb")
        assert entry.source_audio == ""
        assert entry.description == ""
        assert entry.created_at == ""
        assert entry.tags == []

    def test_entry_tags_none_becomes_empty_list(self):
        """Tags=None is normalized to empty list in __post_init__."""
        entry = SpeakerEntry(name="a", embedding_file="a.vsemb", tags=None)
        assert entry.tags == []
        assert isinstance(entry.tags, list)

    def test_entry_to_dict(self):
        """to_dict produces a serializable dict with all fields."""
        entry = SpeakerEntry(
            name="speaker",
            embedding_file="speaker.vsemb",
            source_audio="ref.wav",
            description="A speaker",
            created_at="2026-01-01T00:00:00",
            tags=["english", "male"],
        )
        d = entry.to_dict()
        assert d["name"] == "speaker"
        assert d["embedding_file"] == "speaker.vsemb"
        assert d["source_audio"] == "ref.wav"
        assert d["description"] == "A speaker"
        assert d["created_at"] == "2026-01-01T00:00:00"
        assert d["tags"] == ["english", "male"]

    def test_entry_from_dict_full(self):
        """from_dict round-trips all fields."""
        original = SpeakerEntry(
            name="roundtrip",
            embedding_file="roundtrip.vsemb",
            source_audio="audio.wav",
            description="Round trip test",
            created_at="2026-03-19T12:00:00",
            tags=["test"],
        )
        rebuilt = SpeakerEntry.from_dict(original.to_dict())
        assert rebuilt.name == original.name
        assert rebuilt.embedding_file == original.embedding_file
        assert rebuilt.source_audio == original.source_audio
        assert rebuilt.description == original.description
        assert rebuilt.created_at == original.created_at
        assert rebuilt.tags == original.tags

    def test_entry_from_dict_missing_optionals(self):
        """from_dict handles missing optional fields gracefully."""
        minimal = {"name": "minimal", "embedding_file": "minimal.vsemb"}
        entry = SpeakerEntry.from_dict(minimal)
        assert entry.name == "minimal"
        assert entry.source_audio == ""
        assert entry.description == ""
        assert entry.created_at == ""
        assert entry.tags == []

    def test_entry_tags_not_shared_across_instances(self):
        """Each entry gets its own tags list (no mutable default sharing)."""
        a = SpeakerEntry(name="a", embedding_file="a.vsemb")
        b = SpeakerEntry(name="b", embedding_file="b.vsemb")
        a.tags.append("modified")
        assert "modified" not in b.tags


class TestSpeakerDBExtended:
    """Extended tests for SpeakerDB CRUD, persistence, search, and edge cases."""

    @pytest.fixture
    def sample_embedding(self):
        """Create a sample embedding."""
        return np.random.randn(256).astype(np.float32).tolist()

    @pytest.fixture
    def db(self, tmp_path):
        """Create a SpeakerDB in tmp_path."""
        return SpeakerDB(tmp_path / "speakers")

    def _add_speaker(self, db, name, embedding, **kwargs):
        """Helper: add a speaker via add_embedding (no audio file needed)."""
        with patch('voice_soundboard.speakers.database.save_embedding'):
            return db.add_embedding(name, embedding, **kwargs)

    # --- Empty database ---

    def test_empty_db_list(self, db):
        """Empty database returns empty list."""
        assert db.list() == []

    def test_empty_db_len(self, db):
        """Empty database has length 0."""
        assert len(db) == 0

    def test_empty_db_iter(self, db):
        """Iterating empty database yields nothing."""
        assert list(db) == []

    def test_empty_db_contains(self, db):
        """Containment check returns False on empty database."""
        assert "anyone" not in db

    def test_empty_db_search_returns_empty(self, db):
        """Search on empty database returns empty list."""
        assert db.search(query="anything") == []
        assert db.search(tags=["any"]) == []

    # --- Name validation ---

    def test_validate_name_strips_and_lowercases(self, db, sample_embedding):
        """Names are stripped and lowercased."""
        entry = self._add_speaker(db, "  My_Speaker  ", sample_embedding)
        assert entry.name == "my_speaker"

    def test_validate_name_empty_raises(self, db, sample_embedding):
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            self._add_speaker(db, "", sample_embedding)

    def test_validate_name_whitespace_only_raises(self, db, sample_embedding):
        """Whitespace-only name raises ValueError after strip."""
        with pytest.raises(ValueError, match="cannot be empty"):
            self._add_speaker(db, "   ", sample_embedding)

    def test_validate_name_special_chars_raises(self, db, sample_embedding):
        """Names with special characters are rejected."""
        for bad_name in ["hello world", "hello-world", "hello.world", "Hello!", "@user"]:
            with pytest.raises(ValueError, match="Invalid speaker name"):
                self._add_speaker(db, bad_name, sample_embedding)

    def test_validate_name_allows_underscores_and_digits(self, db, sample_embedding):
        """Names with underscores and digits are valid."""
        entry = self._add_speaker(db, "speaker_01", sample_embedding)
        assert entry.name == "speaker_01"

    # --- Duplicate handling ---

    def test_add_duplicate_without_overwrite_raises(self, db, sample_embedding):
        """Adding a duplicate name without overwrite raises ValueError."""
        self._add_speaker(db, "duplicate", sample_embedding)
        with pytest.raises(ValueError, match="already exists"):
            self._add_speaker(db, "duplicate", sample_embedding)

    def test_add_duplicate_with_overwrite_succeeds(self, db, sample_embedding):
        """Adding a duplicate name with overwrite=True replaces the entry."""
        self._add_speaker(db, "replaceme", sample_embedding, description="Original")
        self._add_speaker(db, "replaceme", sample_embedding, description="Replaced", overwrite=True)
        entry = db.get_entry("replaceme")
        assert entry.description == "Replaced"

    def test_add_duplicate_overwrite_preserves_count(self, db, sample_embedding):
        """Overwriting a speaker does not increase the count."""
        self._add_speaker(db, "one", sample_embedding)
        assert len(db) == 1
        self._add_speaker(db, "one", sample_embedding, overwrite=True)
        assert len(db) == 1

    # --- add_embedding ---

    def test_add_embedding_creates_entry(self, db, sample_embedding):
        """add_embedding creates a proper SpeakerEntry."""
        entry = self._add_speaker(db, "emb_speaker", sample_embedding, description="From embedding")
        assert entry.name == "emb_speaker"
        assert entry.description == "From embedding"
        assert entry.embedding_file == "emb_speaker.vsemb"

    def test_add_embedding_with_tags(self, db, sample_embedding):
        """add_embedding stores tags correctly."""
        entry = self._add_speaker(db, "tagged", sample_embedding, tags=["english", "deep"])
        assert entry.tags == ["english", "deep"]

    def test_add_embedding_source_audio_empty(self, db, sample_embedding):
        """add_embedding sets source_audio to empty string."""
        entry = self._add_speaker(db, "no_source", sample_embedding)
        assert entry.source_audio == ""

    def test_add_embedding_sets_created_at(self, db, sample_embedding):
        """add_embedding sets a non-empty created_at timestamp."""
        entry = self._add_speaker(db, "timestamped", sample_embedding)
        assert entry.created_at != ""

    # --- get_entry ---

    def test_get_entry_nonexistent_raises(self, db):
        """get_entry raises KeyError for missing speaker."""
        with pytest.raises(KeyError, match="not found"):
            db.get_entry("ghost")

    def test_get_entry_returns_correct_metadata(self, db, sample_embedding):
        """get_entry returns all metadata fields correctly."""
        self._add_speaker(db, "meta", sample_embedding, description="Metadata test", tags=["a", "b"])
        entry = db.get_entry("meta")
        assert entry.name == "meta"
        assert entry.description == "Metadata test"
        assert entry.tags == ["a", "b"]

    # --- __contains__ ---

    def test_contains_true(self, db, sample_embedding):
        """'in' operator returns True for existing speaker."""
        self._add_speaker(db, "exists", sample_embedding)
        assert "exists" in db

    def test_contains_false(self, db):
        """'in' operator returns False for missing speaker."""
        assert "missing" not in db

    # --- __iter__ ---

    def test_iter_yields_all_entries(self, db, sample_embedding):
        """Iterating yields all SpeakerEntry objects."""
        self._add_speaker(db, "alpha", sample_embedding)
        self._add_speaker(db, "beta", sample_embedding)
        entries = list(db)
        names = {e.name for e in entries}
        assert names == {"alpha", "beta"}
        assert all(isinstance(e, SpeakerEntry) for e in entries)

    # --- remove ---

    def test_remove_decreases_count(self, db, sample_embedding):
        """Removing a speaker decreases len."""
        self._add_speaker(db, "will_go", sample_embedding)
        assert len(db) == 1
        db.remove("will_go")
        assert len(db) == 0

    def test_remove_makes_contains_false(self, db, sample_embedding):
        """Removed speaker is no longer 'in' the database."""
        self._add_speaker(db, "temp", sample_embedding)
        assert "temp" in db
        db.remove("temp")
        assert "temp" not in db

    def test_remove_cleans_up_embedding_file(self, db, sample_embedding):
        """Remove deletes the .vsemb file from disk."""
        with patch('voice_soundboard.speakers.database.save_embedding'):
            db.add_embedding("cleanup", sample_embedding, description="Cleanup test")
        emb_path = db.directory / "cleanup.vsemb"
        # Create a fake file so remove can delete it
        emb_path.touch()
        assert emb_path.exists()
        db.remove("cleanup")
        assert not emb_path.exists()

    def test_remove_missing_embedding_file_still_succeeds(self, db, sample_embedding):
        """Remove succeeds even if the embedding file is already gone."""
        self._add_speaker(db, "no_file", sample_embedding)
        # Ensure the embedding file does NOT exist (mock prevented creation)
        emb_path = db.directory / "no_file.vsemb"
        if emb_path.exists():
            emb_path.unlink()
        result = db.remove("no_file")
        assert result is True
        assert "no_file" not in db

    # --- Search ---

    def test_search_no_filters_returns_all(self, db, sample_embedding):
        """Search with no filters returns all entries."""
        self._add_speaker(db, "one", sample_embedding)
        self._add_speaker(db, "two", sample_embedding)
        results = db.search()
        assert len(results) == 2

    def test_search_query_case_insensitive(self, db, sample_embedding):
        """Query search is case-insensitive."""
        self._add_speaker(db, "alice", sample_embedding, description="Alice Wonderland")
        results = db.search(query="alice")
        assert len(results) == 1
        results_upper = db.search(query="ALICE")
        assert len(results_upper) == 1

    def test_search_query_matches_name(self, db, sample_embedding):
        """Query matches against the speaker name."""
        self._add_speaker(db, "john_smith", sample_embedding, description="")
        results = db.search(query="john")
        assert len(results) == 1
        assert results[0].name == "john_smith"

    def test_search_query_matches_description(self, db, sample_embedding):
        """Query matches against the description."""
        self._add_speaker(db, "speaker_x", sample_embedding, description="Deep bass narrator")
        results = db.search(query="narrator")
        assert len(results) == 1

    def test_search_query_no_match(self, db, sample_embedding):
        """Query with no match returns empty list."""
        self._add_speaker(db, "alice", sample_embedding, description="Wonderland")
        results = db.search(query="zzzzzzz")
        assert results == []

    def test_search_tags_any_match(self, db, sample_embedding):
        """Tag search uses any-match (OR) semantics."""
        self._add_speaker(db, "a", sample_embedding, tags=["english"])
        self._add_speaker(db, "b", sample_embedding, tags=["german"])
        self._add_speaker(db, "c", sample_embedding, tags=["english", "german"])
        results = db.search(tags=["english"])
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"a", "c"}

    def test_search_multiple_tags(self, db, sample_embedding):
        """Searching with multiple tags matches speakers having any of them."""
        self._add_speaker(db, "a", sample_embedding, tags=["english"])
        self._add_speaker(db, "b", sample_embedding, tags=["german"])
        self._add_speaker(db, "c", sample_embedding, tags=["french"])
        results = db.search(tags=["english", "german"])
        assert len(results) == 2

    def test_search_combined_query_and_tags(self, db, sample_embedding):
        """Combining query and tags applies both filters (AND)."""
        self._add_speaker(db, "pro_english", sample_embedding, description="Professional", tags=["english"])
        self._add_speaker(db, "casual_english", sample_embedding, description="Casual", tags=["english"])
        self._add_speaker(db, "pro_german", sample_embedding, description="Professional", tags=["german"])
        results = db.search(query="professional", tags=["english"])
        assert len(results) == 1
        assert results[0].name == "pro_english"

    # --- Persistence ---

    def test_persistence_across_instances(self, tmp_path, sample_embedding):
        """Data persists when a new SpeakerDB instance is created on the same directory."""
        db_dir = tmp_path / "persist_db"
        db1 = SpeakerDB(db_dir)
        with patch('voice_soundboard.speakers.database.save_embedding'):
            db1.add_embedding("alice", sample_embedding, description="Alice", tags=["english"])
            db1.add_embedding("bob", sample_embedding, description="Bob")

        db2 = SpeakerDB(db_dir)
        assert len(db2) == 2
        assert "alice" in db2
        assert "bob" in db2
        entry = db2.get_entry("alice")
        assert entry.description == "Alice"
        assert entry.tags == ["english"]

    def test_persistence_after_remove(self, tmp_path, sample_embedding):
        """Removals persist across instances."""
        db_dir = tmp_path / "persist_remove"
        db1 = SpeakerDB(db_dir)
        with patch('voice_soundboard.speakers.database.save_embedding'):
            db1.add_embedding("temp", sample_embedding)
        db1.remove("temp")

        db2 = SpeakerDB(db_dir)
        assert len(db2) == 0
        assert "temp" not in db2

    def test_index_file_is_valid_json(self, tmp_path, sample_embedding):
        """The index.json file is valid JSON with expected structure."""
        db_dir = tmp_path / "json_check"
        db = SpeakerDB(db_dir)
        with patch('voice_soundboard.speakers.database.save_embedding'):
            db.add_embedding("test", sample_embedding, description="Test speaker")

        index_path = db_dir / "index.json"
        assert index_path.exists()
        with open(index_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert "version" in data
        assert data["version"] == "1.0"
        assert "speakers" in data
        assert "test" in data["speakers"]
        assert data["speakers"]["test"]["description"] == "Test speaker"

    def test_corrupted_index_loads_empty(self, tmp_path):
        """A corrupted index.json results in an empty database (no crash)."""
        db_dir = tmp_path / "corrupt"
        db_dir.mkdir()
        index_path = db_dir / "index.json"
        index_path.write_text("THIS IS NOT JSON!!!", encoding="utf-8")

        db = SpeakerDB(db_dir)
        assert len(db) == 0
        assert db.list() == []

    def test_creates_directory_if_missing(self, tmp_path):
        """SpeakerDB creates the directory if it does not exist."""
        db_dir = tmp_path / "deep" / "nested" / "speakers"
        assert not db_dir.exists()
        SpeakerDB(db_dir)
        assert db_dir.exists()

    # --- Export ---

    def test_export_creates_zip(self, tmp_path, sample_embedding):
        """Export creates a .zip archive."""
        db_dir = tmp_path / "export_db"
        db = SpeakerDB(db_dir)
        with patch('voice_soundboard.speakers.database.save_embedding'):
            db.add_embedding("exportable", sample_embedding, description="Export me")

        output = tmp_path / "backup.zip"
        result = db.export(output)
        assert result == output
        assert result.exists()
        assert result.suffix == ".zip"

    def test_export_adds_zip_suffix(self, tmp_path, sample_embedding):
        """Export appends .zip if not provided."""
        db_dir = tmp_path / "export_db2"
        db = SpeakerDB(db_dir)
        with patch('voice_soundboard.speakers.database.save_embedding'):
            db.add_embedding("speaker", sample_embedding)

        output = tmp_path / "backup"
        result = db.export(output)
        assert result.suffix == ".zip"
        assert result.exists()

    def test_export_contains_index(self, tmp_path, sample_embedding):
        """Exported zip contains the index.json file."""
        import zipfile
        db_dir = tmp_path / "export_db3"
        db = SpeakerDB(db_dir)
        with patch('voice_soundboard.speakers.database.save_embedding'):
            db.add_embedding("zipped", sample_embedding)

        output = tmp_path / "with_index.zip"
        db.export(output)
        with zipfile.ZipFile(output, 'r') as zf:
            assert "index.json" in zf.namelist()

    # --- add() with audio_path ---

    def test_add_from_audio_stores_source_filename(self, db, sample_embedding):
        """add() records the source audio filename (not full path)."""
        with patch('voice_soundboard.speakers.database.extract_embedding', return_value=sample_embedding):
            with patch('voice_soundboard.speakers.database.save_embedding'):
                entry = db.add("from_audio", Path("/some/path/reference.wav"), description="Audio")
        assert entry.source_audio == "reference.wav"

    def test_add_from_audio_duplicate_raises(self, db, sample_embedding):
        """add() from audio raises on duplicate without overwrite."""
        with patch('voice_soundboard.speakers.database.extract_embedding', return_value=sample_embedding):
            with patch('voice_soundboard.speakers.database.save_embedding'):
                db.add("dup_audio", Path("ref.wav"))
                with pytest.raises(ValueError, match="already exists"):
                    db.add("dup_audio", Path("ref2.wav"))

    # --- list() ordering ---

    def test_list_returns_all_names(self, db, sample_embedding):
        """list() returns exactly the names of added speakers."""
        for name in ["charlie", "alice", "bob"]:
            self._add_speaker(db, name, sample_embedding)
        names = set(db.list())
        assert names == {"alice", "bob", "charlie"}
