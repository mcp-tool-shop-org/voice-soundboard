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
    
    def test_extract_from_audio_array(self):
        """Extract embedding from audio array."""
        # Simulate audio data (3 seconds at 16kHz)
        audio = np.random.randn(48000).astype(np.float32) * 0.1
        
        try:
            extractor = EmbeddingExtractor()
            embedding = extractor.extract(audio, sample_rate=16000)
            
            assert isinstance(embedding, np.ndarray)
            assert embedding.ndim == 1
            assert len(embedding) == 256  # resemblyzer default
        except ImportError:
            pytest.skip("resemblyzer not installed")
    
    def test_extract_with_format(self):
        """Extract embedding with specified format."""
        audio = np.random.randn(48000).astype(np.float32) * 0.1
        
        try:
            extractor = EmbeddingExtractor(format=EmbeddingFormat.RESEMBLYZER)
            embedding = extractor.extract(audio, sample_rate=16000)
            
            assert embedding is not None
        except ImportError:
            pytest.skip("resemblyzer not installed")
    
    def test_convenience_function(self):
        """Test extract_embedding convenience function."""
        audio = np.random.randn(48000).astype(np.float32) * 0.1
        
        try:
            embedding = extract_embedding(audio, sample_rate=16000)
            assert embedding is not None
        except ImportError:
            pytest.skip("resemblyzer not installed")


class TestEmbeddingStorage:
    """Tests for embedding storage functions."""
    
    @pytest.fixture
    def sample_embedding(self):
        """Create a sample embedding."""
        return np.random.randn(256).astype(np.float32)
    
    def test_save_and_load(self, sample_embedding):
        """Save and load embedding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.vsemb"
            
            save_embedding(sample_embedding, path, speaker_id="test_speaker")
            loaded = load_embedding(path)
            
            np.testing.assert_array_almost_equal(
                sample_embedding, 
                loaded, 
                decimal=5
            )
    
    def test_save_with_metadata(self, sample_embedding):
        """Save embedding with metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.vsemb"
            
            save_embedding(
                sample_embedding, 
                path,
                speaker_id="test_speaker",
                source_file="original.wav",
                format=EmbeddingFormat.RESEMBLYZER,
            )
            
            # Load the file and check metadata
            emb_file = EmbeddingFile.load(path)
            
            assert emb_file.speaker_id == "test_speaker"
            assert emb_file.source_file == "original.wav"
    
    def test_load_nonexistent(self):
        """Loading nonexistent file raises error."""
        with pytest.raises((FileNotFoundError, ValueError)):
            load_embedding(Path("/nonexistent/path.vsemb"))
    
    def test_embedding_file_class(self, sample_embedding):
        """Test EmbeddingFile class directly."""
        emb_file = EmbeddingFile(
            embedding=sample_embedding,
            speaker_id="speaker1",
            format=EmbeddingFormat.RESEMBLYZER,
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "emb.vsemb"
            emb_file.save(path)
            
            loaded = EmbeddingFile.load(path)
            
            assert loaded.speaker_id == "speaker1"
            np.testing.assert_array_almost_equal(
                emb_file.embedding,
                loaded.embedding,
                decimal=5
            )
