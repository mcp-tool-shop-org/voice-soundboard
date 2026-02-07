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
        assert config.buffer_size_ms == 20
        assert config.sample_rate == 22050
        assert config.crossfade_ms == 5
        assert config.backpressure == BackpressurePolicy.BLOCK
        
    def test_buffer_samples_calculation(self):
        config = RealtimeConfig(buffer_size_ms=20, sample_rate=22050)
        # 20ms at 22050 Hz = 441 samples
        assert config.buffer_samples == 441
        
    def test_custom_config(self):
        config = RealtimeConfig(
            buffer_size_ms=50,
            sample_rate=48000,
            backpressure=BackpressurePolicy.DROP_OLDEST,
        )
        assert config.buffer_size_ms == 50
        assert config.sample_rate == 48000
        assert config.backpressure == BackpressurePolicy.DROP_OLDEST


class TestRealtimeBuffer:
    """Tests for RealtimeBuffer."""
    
    def test_buffer_creation(self):
        config = RealtimeConfig(buffer_size_ms=20, sample_rate=22050)
        buffer = RealtimeBuffer(config)
        assert buffer.available == 0
        assert buffer.is_empty
        
    def test_write_and_read(self):
        config = RealtimeConfig(buffer_size_ms=100, sample_rate=1000)
        buffer = RealtimeBuffer(config)
        
        data = np.array([1, 2, 3, 4, 5], dtype=np.int16)
        written = buffer.write(data)
        
        assert written == 5
        assert buffer.available == 5
        
        read_data = buffer.read(3)
        assert len(read_data) == 3
        assert list(read_data) == [1, 2, 3]
        assert buffer.available == 2
        
    def test_circular_behavior(self):
        config = RealtimeConfig(buffer_size_ms=10, sample_rate=1000)  # 10 sample buffer
        buffer = RealtimeBuffer(config)
        
        # Write some data
        buffer.write(np.array([1, 2, 3, 4, 5], dtype=np.int16))
        buffer.read(3)  # Remove 3
        
        # Write more - should wrap
        buffer.write(np.array([6, 7, 8, 9, 10], dtype=np.int16))
        
        # Read all
        data = buffer.read(7)
        assert list(data) == [4, 5, 6, 7, 8, 9, 10]
        
    def test_checkpoint_and_rollback(self):
        config = RealtimeConfig(buffer_size_ms=100, sample_rate=1000)
        buffer = RealtimeBuffer(config)
        
        buffer.write(np.array([1, 2, 3, 4, 5], dtype=np.int16))
        
        # Create checkpoint
        checkpoint = buffer.checkpoint()
        
        # Read some data
        buffer.read(3)
        assert buffer.available == 2
        
        # Rollback
        buffer.rollback(checkpoint)
        assert buffer.available == 5
        
        # Verify data is preserved
        data = buffer.read(5)
        assert list(data) == [1, 2, 3, 4, 5]


class TestRealtimeEngine:
    """Tests for RealtimeEngine."""
    
    def test_engine_creation(self):
        mock_backend = Mock()
        engine = RealtimeEngine(mock_backend)
        assert engine.backend == mock_backend
        
    def test_create_session(self):
        mock_backend = Mock()
        engine = RealtimeEngine(mock_backend)
        
        session = engine.create_session()
        assert isinstance(session, RealtimeSession)
        assert session.state.value == "idle"
        
    def test_session_lifecycle(self):
        mock_backend = Mock()
        mock_backend.synthesize.return_value = np.zeros(1000, dtype=np.int16)
        
        engine = RealtimeEngine(mock_backend)
        session = engine.create_session()
        
        # Start
        session.start()
        assert session.state.value == "running"
        
        # Pause
        session.pause()
        assert session.state.value == "paused"
        
        # Resume
        session.resume()
        assert session.state.value == "running"
        
        # Stop
        session.stop()
        assert session.state.value == "stopped"


class TestBackpressurePolicies:
    """Tests for backpressure handling."""
    
    def test_drop_newest_policy(self):
        config = RealtimeConfig(
            buffer_size_ms=10,
            sample_rate=1000,
            backpressure=BackpressurePolicy.DROP_NEWEST,
        )
        buffer = RealtimeBuffer(config, drop_policy=DropPolicy.NEWEST)
        
        # Fill buffer
        buffer.write(np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=np.int16))
        
        # Try to write more - should drop new data
        written = buffer.write(np.array([11, 12, 13], dtype=np.int16))
        
        # Buffer should still contain original data
        data = buffer.read(10)
        assert list(data) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
    def test_drop_oldest_policy(self):
        config = RealtimeConfig(
            buffer_size_ms=10,
            sample_rate=1000,
            backpressure=BackpressurePolicy.DROP_OLDEST,
        )
        buffer = RealtimeBuffer(config, drop_policy=DropPolicy.OLDEST)
        
        # Fill buffer
        buffer.write(np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=np.int16))
        
        # Write more - should drop oldest
        buffer.write(np.array([11, 12, 13], dtype=np.int16))
        
        # Buffer should have newer data
        data = buffer.read(10)
        # Oldest 3 dropped, newest 3 added
        assert 11 in data
        assert 12 in data
        assert 13 in data
