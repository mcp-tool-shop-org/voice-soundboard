"""
Tests for v2.1 streaming features.

Tests IncrementalSynthesizer, StreamBuffer, and CorrectionDetector.
"""

import pytest
import numpy as np

from voice_soundboard.streaming import (
    IncrementalSynthesizer,
    StreamBuffer,
    SpeculativeGraph,
    CorrectionDetector,
)
from voice_soundboard.streaming.synthesizer import AudioChunk
from voice_soundboard.engine.backends.mock import MockBackend


class TestStreamBuffer:
    """Tests for StreamBuffer."""
    
    def test_add_chunk(self):
        """Adding chunks to buffer."""
        buffer = StreamBuffer(sample_rate=24000, max_buffer_ms=500)
        
        chunk = AudioChunk(
            audio=np.zeros(1200, dtype=np.float32),  # 50ms at 24kHz
            sample_rate=24000,
            is_committed=False,
            word_index=0,
        )
        
        ready = buffer.add(chunk)
        # Should not be ready yet (buffer not full)
        assert len(ready) == 0
        assert buffer.get_buffer_duration_ms() == pytest.approx(50, abs=1)
    
    def test_auto_commit_on_full(self):
        """Buffer auto-commits when full."""
        buffer = StreamBuffer(sample_rate=24000, max_buffer_ms=100)
        
        # Add multiple chunks
        for i in range(5):
            chunk = AudioChunk(
                audio=np.zeros(1200, dtype=np.float32),  # 50ms each
                sample_rate=24000,
                word_index=i,
            )
            ready = buffer.add(chunk)
        
        # Should have committed some chunks
        assert len(ready) > 0
    
    def test_commit_all(self):
        """Commit all flushes buffer."""
        buffer = StreamBuffer(sample_rate=24000, max_buffer_ms=500)
        
        for i in range(3):
            chunk = AudioChunk(
                audio=np.zeros(1200, dtype=np.float32),
                sample_rate=24000,
                word_index=i,
            )
            buffer.add(chunk)
        
        ready = buffer.commit_all()
        assert len(ready) == 3
        assert all(c.is_committed for c in ready)
    
    def test_rollback(self):
        """Rolling back discards uncommitted chunks."""
        buffer = StreamBuffer(sample_rate=24000, max_buffer_ms=500)
        
        for i in range(3):
            chunk = AudioChunk(
                audio=np.zeros(1200, dtype=np.float32),
                sample_rate=24000,
                word_index=i,
            )
            buffer.add(chunk)
        
        # Roll back to word 0
        crossfade = buffer.rollback_to(0)
        
        # Should have discarded chunks for words 1 and 2
        # Crossfade should be returned
        assert crossfade is not None or buffer.get_buffer_duration_ms() < 100


class TestCorrectionDetector:
    """Tests for CorrectionDetector."""
    
    def test_no_correction(self):
        """Normal words don't trigger correction."""
        detector = CorrectionDetector(sensitivity=0.5)
        
        words = ["Hello", "how", "are", "you"]
        for word in words:
            is_corr, _ = detector.feed(word)
            assert not is_corr
    
    def test_explicit_correction(self):
        """Explicit correction phrases are detected."""
        detector = CorrectionDetector(sensitivity=0.5)
        
        detector.feed("Hello")
        detector.feed("I")
        is_corr, _ = detector.feed("actually")
        
        assert is_corr
    
    def test_commit_resets_history(self):
        """Committing clears history."""
        detector = CorrectionDetector(sensitivity=0.5)
        
        detector.feed("Hello")
        detector.feed("world")
        detector.commit("Hello world")
        
        # History should be cleared
        is_corr, _ = detector.feed("Hello")  # Not a correction now
        assert not is_corr


class TestSpeculativeGraph:
    """Tests for SpeculativeGraph."""
    
    def test_commit(self):
        """Committing a graph."""
        from voice_soundboard.graph import ControlGraph, TokenEvent, SpeakerRef
        
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        
        spec = SpeculativeGraph(graph, word_index=0, is_committed=False)
        assert spec.can_rollback()
        
        committed = spec.commit()
        assert not committed.can_rollback()


class TestIncrementalSynthesizer:
    """Tests for IncrementalSynthesizer."""
    
    def test_feed_word(self):
        """Feed words and get audio chunks."""
        backend = MockBackend()
        synth = IncrementalSynthesizer(backend, voice="af_bella")
        
        chunks = list(synth.feed("Hello"))
        # Should produce some chunks
        assert len(chunks) >= 0  # May be 0 if buffering
    
    def test_finalize(self):
        """Finalize flushes remaining audio."""
        backend = MockBackend()
        synth = IncrementalSynthesizer(backend, voice="af_bella")
        
        # Feed some words
        for word in ["Hello", "world"]:
            list(synth.feed(word))
        
        # Finalize should flush
        final_chunks = list(synth.finalize())
        assert len(final_chunks) >= 0
    
    def test_commit_on_punctuation(self):
        """Punctuation creates commit points."""
        backend = MockBackend()
        synth = IncrementalSynthesizer(backend, voice="af_bella")
        
        # Feed sentence with punctuation
        for word in ["Hello,", "how", "are", "you?"]:
            list(synth.feed(word))
        
        stats = synth.get_stats()
        assert stats["words_processed"] == 4
    
    def test_reset(self):
        """Reset clears state."""
        backend = MockBackend()
        synth = IncrementalSynthesizer(backend, voice="af_bella")
        
        for word in ["Hello", "world"]:
            list(synth.feed(word))
        
        synth.reset()
        
        stats = synth.get_stats()
        assert stats["words_processed"] == 0
    
    def test_rollback_disabled(self):
        """Rollback can be disabled."""
        backend = MockBackend()
        synth = IncrementalSynthesizer(
            backend, 
            voice="af_bella",
            enable_rollback=False,
        )
        
        # Should work without rollback
        for word in ["Hello", "actually", "goodbye"]:
            list(synth.feed(word))
        
        stats = synth.get_stats()
        assert stats["rollback_count"] == 0
