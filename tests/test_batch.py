"""
Tests for v2.1 batch synthesis features.

Tests BatchSynthesizer for processing multiple items efficiently.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile

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
    
    def test_create_from_text(self):
        """Create batch item from text."""
        item = BatchItem(
            id="item1",
            text="Hello world",
            voice="af_bella",
        )
        
        assert item.id == "item1"
        assert item.text == "Hello world"
        assert item.voice == "af_bella"
    
    def test_create_from_graph(self):
        """Create batch item from graph."""
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        
        item = BatchItem(
            id="item2",
            graph=graph,
        )
        
        assert item.graph is not None


class TestBatchResult:
    """Tests for BatchResult."""
    
    def test_result_with_audio(self):
        """Result contains audio."""
        audio = np.zeros(4800, dtype=np.float32)
        
        result = BatchResult(
            id="item1",
            audio=audio,
            sample_rate=24000,
            success=True,
        )
        
        assert result.success
        assert len(result.audio) == 4800
    
    def test_result_with_error(self):
        """Result can contain error."""
        result = BatchResult(
            id="item1",
            audio=None,
            success=False,
            error="Synthesis failed",
        )
        
        assert not result.success
        assert result.error == "Synthesis failed"


class TestBatchSynthesizer:
    """Tests for BatchSynthesizer."""
    
    @pytest.fixture
    def batch_synth(self):
        """Create a batch synthesizer with mock backend."""
        backend = MockBackend()
        return BatchSynthesizer(backend)
    
    def test_synthesize_single(self, batch_synth):
        """Synthesize single item."""
        items = [
            BatchItem(id="1", text="Hello world", voice="af_bella"),
        ]
        
        results = batch_synth.synthesize(items)
        
        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].success
    
    def test_synthesize_multiple(self, batch_synth):
        """Synthesize multiple items."""
        items = [
            BatchItem(id="1", text="Hello", voice="af_bella"),
            BatchItem(id="2", text="World", voice="af_bella"),
            BatchItem(id="3", text="Goodbye", voice="af_bella"),
        ]
        
        results = batch_synth.synthesize(items)
        
        assert len(results) == 3
        assert all(r.success for r in results)
    
    def test_preserves_order(self, batch_synth):
        """Results are in same order as inputs."""
        items = [
            BatchItem(id="a", text="First", voice="af_bella"),
            BatchItem(id="b", text="Second", voice="af_bella"),
            BatchItem(id="c", text="Third", voice="af_bella"),
        ]
        
        results = batch_synth.synthesize(items)
        
        assert [r.id for r in results] == ["a", "b", "c"]
    
    def test_with_graphs(self, batch_synth):
        """Synthesize pre-built graphs."""
        items = [
            BatchItem(
                id="graph1",
                graph=ControlGraph(
                    tokens=[TokenEvent(text="Hello")],
                    speaker=SpeakerRef.from_voice("af_bella"),
                ),
            ),
            BatchItem(
                id="graph2",
                graph=ControlGraph(
                    tokens=[TokenEvent(text="World")],
                    speaker=SpeakerRef.from_voice("af_bella"),
                ),
            ),
        ]
        
        results = batch_synth.synthesize(items)
        
        assert len(results) == 2
        assert all(r.success for r in results)
    
    def test_save_to_directory(self, batch_synth):
        """Save results to directory."""
        items = [
            BatchItem(id="output1", text="Hello", voice="af_bella"),
            BatchItem(id="output2", text="World", voice="af_bella"),
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            
            results = batch_synth.synthesize(items, output_dir=output_dir)
            
            # Check files were created
            files = list(output_dir.glob("*.wav"))
            assert len(files) == 2
    
    def test_with_progress_callback(self, batch_synth):
        """Progress callback is called."""
        items = [
            BatchItem(id="1", text="Hello", voice="af_bella"),
            BatchItem(id="2", text="World", voice="af_bella"),
        ]
        
        progress_calls = []
        
        def on_progress(completed, total):
            progress_calls.append((completed, total))
        
        batch_synth.synthesize(items, progress_callback=on_progress)
        
        assert len(progress_calls) >= 2
        assert progress_calls[-1][0] == progress_calls[-1][1]  # Final call shows all complete
    
    def test_parallel_compile(self, batch_synth):
        """Parallel compilation with workers."""
        items = [
            BatchItem(id=str(i), text=f"Text {i}", voice="af_bella")
            for i in range(10)
        ]
        
        results = batch_synth.synthesize(items, compile_workers=4)
        
        assert len(results) == 10
        assert all(r.success for r in results)


class TestConvenienceFunction:
    """Tests for batch_synthesize convenience function."""
    
    def test_basic_usage(self):
        """Basic convenience function usage."""
        texts = ["Hello", "World", "Goodbye"]
        
        backend = MockBackend()
        results = batch_synthesize(texts, voice="af_bella", backend=backend)
        
        assert len(results) == 3
        assert all(r.success for r in results)
    
    def test_with_output_dir(self):
        """Save to output directory."""
        texts = ["Hello", "World"]
        backend = MockBackend()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            results = batch_synthesize(
                texts, 
                voice="af_bella", 
                backend=backend,
                output_dir=tmpdir,
            )
            
            files = list(Path(tmpdir).glob("*.wav"))
            assert len(files) == 2
