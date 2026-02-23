"""
Tests for v2.1 voice cloning features.

Tests EmbeddingExtractor and embedding storage.
"""

import pytest
import numpy as np
import tempfile
from pathlib import Path

from voice_soundboard.cloning import (
    extract_embedding,
    save_embedding,
    load_embedding,
)
from voice_soundboard.cloning.extractor import EmbeddingExtractor, EmbeddingFormat
from voice_soundboard.cloning.storage import EmbeddingFile


class TestEmbeddingExtractor:
    """Tests for EmbeddingExtractor."""
    
    def test_extract_from_file(self):
        """Extract embedding from audio file."""
        import soundfile as sf
        
        # Create dummy audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            audio = np.random.randn(48000).astype(np.float32) * 0.1
            sf.write(f.name, audio, 16000)
            f.close()
            
            try:
                try:
                    extractor = EmbeddingExtractor()
                    embedding = extractor.extract(f.name)
                    
                    assert isinstance(embedding.embedding, list)
                    assert len(embedding.embedding) > 0
                    assert embedding.format == EmbeddingFormat.RESEMBLYZER
                except ImportError:
                    pytest.skip("resemblyzer not installed")
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    def test_extract_with_backend(self):
        """Extract embedding with specified backend."""
        import soundfile as sf
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            audio = np.random.randn(48000).astype(np.float32) * 0.1
            sf.write(f.name, audio, 16000)
            f.close()
            
            try:
                try:
                    extractor = EmbeddingExtractor(backend="resemblyzer")
                    embedding = extractor.extract(f.name)
                    
                    assert embedding is not None
                except ImportError:
                    pytest.skip("resemblyzer not installed")
            finally:
                Path(f.name).unlink(missing_ok=True)
    
    def test_convenience_function(self):
        """Test extract_embedding convenience function."""
        import soundfile as sf
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            audio = np.random.randn(48000).astype(np.float32) * 0.1
            sf.write(f.name, audio, 16000)
            f.close()
            
            try:
                try:
                    embedding = extract_embedding(f.name)
                    assert embedding is not None
                except ImportError:
                    pytest.skip("resemblyzer not installed")
            finally:
                Path(f.name).unlink(missing_ok=True)


class TestEmbeddingStorage:
    """Tests for embedding storage functions."""
    
    @pytest.fixture
    def sample_embedding(self):
        """Create a sample embedding."""
        return np.random.randn(256).astype(np.float32).tolist()
    
    def test_save_and_load(self, sample_embedding):
        """Save and load embedding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.vsemb"
            
            save_embedding(sample_embedding, path, name="test_speaker")
            loaded = load_embedding(path)
            
            # load_embedding returns list
            np.testing.assert_array_almost_equal(
                sample_embedding, 
                loaded, 
                decimal=5
            )
    
    def test_save_with_metadata(self, sample_embedding):
        """Save embedding with metadata."""
        from voice_soundboard.cloning.storage import load_embedding_file, EmbeddingFile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.vsemb"
            
            # Create EmbeddingFile explicitly to include source_file
            emb_obj = EmbeddingFile(
                embedding=sample_embedding,
                format="resemblyzer",
                name="test_speaker",
                description="Test description",
                source_file="original.wav"
            )
            
            save_embedding(
                emb_obj, 
                path
            )
            
            # Load the file and check metadata
            emb_file = load_embedding_file(path)
            
            assert emb_file.name == "test_speaker"
            assert emb_file.description == "Test description"
            assert emb_file.source_file == "original.wav"
    
    def test_embedding_file_class(self, sample_embedding):
        """Test EmbeddingFile class directly."""
        emb_file = EmbeddingFile(
            embedding=sample_embedding,
            name="speaker1",
            format=EmbeddingFormat.RESEMBLYZER,
        )
        
        assert emb_file.name == "speaker1"
        assert emb_file.format == EmbeddingFormat.RESEMBLYZER
        assert emb_file.embedding == sample_embedding
    
    def test_load_nonexistent(self):
        """Loading nonexistent file raises error."""
        with pytest.raises((FileNotFoundError, ValueError)):
            load_embedding(Path("/nonexistent/path.vsemb"))
