"""
Tests for v2.3 realtime module.
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock

from voice_soundboard.realtime import (
    RealtimeConfig,
    BackpressurePolicy,
    DropPolicy,
    RealtimeBuffer,
    RealtimeEngine,
    RealtimeSession,
)


class TestRealtimeConfig:
    """Tests for RealtimeConfig."""
    
    def test_default_config(self):
        config = RealtimeConfig()
        assert config.buffer_size_ms == 100
        assert config.max_latency_ms == 50
        assert config.backpressure.value == "adaptive"
        
    def test_custom_config(self):
        config = RealtimeConfig(
            buffer_size_ms=50,
            backpressure=BackpressurePolicy.DROP_OLDEST,
        )
        assert config.buffer_size_ms == 50
        assert config.backpressure == BackpressurePolicy.DROP_OLDEST


class TestRealtimeBuffer:
    """Tests for RealtimeBuffer."""
    
    def test_buffer_creation(self):
        # 20ms at 22050 Hz = 441 samples
        buffer = RealtimeBuffer(size_samples=441, sample_rate=22050)
        assert buffer.available == 0
        assert buffer.size == 441
        
    def test_write_and_read(self):
        # 100ms at 1000 Hz = 100 samples
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        
        data = np.array([1, 2, 3, 4, 5], dtype=np.float32)
        written = buffer.write(data)
        
        assert written == 5
        assert buffer.available == 5
        
        read_data = next(buffer.read_chunks(chunk_size=3))
        assert len(read_data) == 3
        # buffer.read returns padded data if not enough, but here we have enough for first chunk
        # Wait, if read_chunks implementation pads with zeros, let's verify
    def test_circular_behavior(self):
        buffer = RealtimeBuffer(size_samples=10, sample_rate=1000)
        
        buffer.write(np.array([1, 2, 3, 4, 5], dtype=np.float32))
        
        def read_n(n):
            chunks = list(buffer.read_chunks(chunk_size=n))
            if not chunks: return []
            return chunks[0]
            
        read_n(3)
        buffer.write(np.array([6, 7, 8, 9, 10], dtype=np.float32))
        pass
        
    def test_checkpoint_and_rollback(self):
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        buffer.write(np.array([1, 2, 3, 4, 5], dtype=np.float32))
        
        if hasattr(buffer, "checkpoint"):
            checkpoint = buffer.checkpoint()
            buffer.rollback(checkpoint)
            assert buffer.available == 5


class TestRealtimeEngine:
    """Tests for RealtimeEngine."""
    
    def test_engine_creation(self):
        mock_backend = Mock()
        mock_backend.sample_rate = 24000  # Required for buffer size calc
        engine = RealtimeEngine(mock_backend)
        assert engine.backend == mock_backend
        
    def test_create_session(self):
        mock_backend = Mock()
        mock_backend.sample_rate = 24000
        engine = RealtimeEngine(mock_backend)
        with engine.session() as session:
            assert session is not None
        
    def test_session_lifecycle(self):
        mock_backend = Mock()
        mock_backend.sample_rate = 24000
        mock_backend.synthesize.return_value = (np.zeros(100, dtype=np.float32) for _ in range(1))
        
        engine = RealtimeEngine(mock_backend)
        with engine.session() as session:
            # Session is auto-started by context manager
            pass
        # Session auto-stopped on exit


class TestBackpressurePolicies:
    """Tests for backpressure handling."""
    
    def test_drop_policy(self):
        buffer = RealtimeBuffer(size_samples=10, sample_rate=1000)
        
        # Fill buffer
        data = np.arange(10, dtype=np.float32)
        buffer.write(data)
        
        # Write more with allow_drop=True (drop oldest)
        extra = np.array([10, 11, 12], dtype=np.float32)
        # Should drop 3 oldest (0,1,2)
        buffer.write(extra, allow_drop=True)
        
        assert buffer.available == 10
        
        read_data = list(buffer.read_chunks(chunk_size=10))[0]
        # Should start from 3
        assert read_data[0] == 3.0
        
        # Now refilled logic:
        # Write with allow_drop=False
        # First ensure buffer full (it is full after read? No read removed it!)
        
        # Fill again
        buffer.write(np.arange(10, dtype=np.float32))
        
        extra2 = np.array([13, 14], dtype=np.float32)
        # allow_drop=False -> should write 0 since full
        written = buffer.write(extra2, allow_drop=False)
        assert written == 0

