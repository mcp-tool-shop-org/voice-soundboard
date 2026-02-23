"""
Tests for v2.1 batch synthesis features.

Tests BatchSynthesizer for processing multiple items efficiently.
"""

import pytest
import numpy as np
import time
from pathlib import Path
import tempfile
from unittest.mock import MagicMock

from voice_soundboard.runtime.batch import (
    BatchSynthesizer,
    batch_synthesize,
    BatchItem,
    BatchResult,
)
from voice_soundboard.graph import ControlGraph, TokenEvent, SpeakerRef
from voice_soundboard.engine.backends.mock import MockBackend


class TestBatchItem:
    """Tests for BatchItem dataclass."""
    
    def test_create_basic(self):
        """Create batch item with basic properties."""
        
        # BatchItem is created internally by synthesizer usually, 
        # but we can test it directly.
        # Based on definition:
        # index: int, text: str, voice: str | None = None, ...
        
        item = BatchItem(
            index=1,
            text="Hello world",
            voice="af_bella",
        )
        
        assert item.index == 1
        assert item.text == "Hello world"
        assert item.voice == "af_bella"
        assert not item.success  # Initially False (no audio)
    
    def test_success_property(self):
        """Test success property logic."""
        item = BatchItem(index=1, text="test")
        assert not item.success
        
        item.audio = np.zeros(100)
        assert item.success
        
        item.error = "Failed"
        # If error is set, success should be false even if audio exists (usually audio is None)
        assert not item.success


class TestBatchResult:
    """Tests for BatchResult aggregation."""
    
    def test_result_stats(self):
        """Test result statistics."""
        items = [
            BatchItem(index=0, text="success1", audio=np.zeros(100), duration_seconds=1.0),
            BatchItem(index=1, text="success2", audio=np.zeros(200), duration_seconds=2.0),
            BatchItem(index=2, text="fail", error="error"),
        ]
        
        result = BatchResult(
            items=items,
            total_time=10.0,
            compile_time=1.0,
            synth_time=9.0
        )
        
        assert result.success_count == 2
        assert result.failure_count == 1
        assert result.total_duration == 3.0
        assert len(list(result)) == 3  # iterator works


class TestBatchSynthesizer:
    """Tests for BatchSynthesizer."""
    
    @pytest.fixture
    def mock_backend(self):
        return MockBackend()
        
    @pytest.fixture
    def batch_synth(self, mock_backend):
        """Create a batch synthesizer with mock backend."""
        # We assume MockBackend works for synthesis.
        # But we might need to mock compile_request if BatchSynthesizer calls it.
        # In runtime/batch.py, default compile_fn is compile_request.
        # We can probably use the real one if it doesn't depend on external services,
        # or mock it to be safe/fast.
        
        return BatchSynthesizer(mock_backend)

    def test_synthesize_single(self, batch_synth):
        """Synthesize single item."""
        texts = ["Hello world"]
        
        # We need to make sure the backend returns something valid
        # MockBackend typically returns valid audio
        
        # However, compilation might fail if we don't mock it or provide real compiler context (e.g. assets)
        # But test_compiler.py passed, so compiler should work.
        
        # Mock the compile function on the instance to avoid complex dependencies
        # if needed. But let's try with default first, or override if simple.
        
        # Override _compile_fn for simplicity
        mock_graph = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("af_bella")
        )
        batch_synth._compile_fn = MagicMock(return_value=mock_graph)
        
        result = batch_synth.synthesize(texts, voice="af_bella")
        
        assert isinstance(result, BatchResult)
        assert len(result.items) == 1
        assert result.items[0].text == "Hello world"
        assert result.items[0].success
        assert result.items[0].audio is not None
        
    def test_synthesize_multiple(self, batch_synth):
        """Synthesize multiple items."""
        texts = ["One", "Two", "Three"]
        
        # Mock compiler
        mock_graph = ControlGraph(
            tokens=[TokenEvent(text="test")],
            speaker=SpeakerRef.from_voice("af_bella")
        )
        batch_synth._compile_fn = MagicMock(return_value=mock_graph)
        
        result = batch_synth.synthesize(texts, voice="af_bella")
        
        assert len(result.items) == 3
        assert result.success_count == 3
        
    def test_save_to_directory(self, batch_synth):
        """Save results to directory."""
        texts = ["Hello", "World"]
        
        # Mock compiler
        mock_graph = ControlGraph(
            tokens=[TokenEvent(text="test")],
            speaker=SpeakerRef.from_voice("af_bella")
        )
        batch_synth._compile_fn = MagicMock(return_value=mock_graph)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            
            result = batch_synth.synthesize(texts, voice="af_bella", output_dir=output_dir)
            
            # Check files were created (mock backend might not write files? 
            # Wait, synthesize function writes files if audio is present)
            # BatchSynthesizer.synthesize writes files if output_dir is set
            
            files = list(output_dir.glob("*.wav"))
            assert len(files) == 2


class TestConvenienceFunction:
    """Tests for batch_synthesize convenience function."""
    
    def test_basic_usage(self):
        """Basic convenience function usage."""
        texts = ["Hello", "World"]
        
        # Should succeed
        # Use "mock" string, not instance, as batch_synthesize expects backend name
        results = batch_synthesize(texts, voice="af_bella", backend="mock")
        
        assert isinstance(results, BatchResult)
        assert len(results.items) == 2
        assert results.success_count == 2
