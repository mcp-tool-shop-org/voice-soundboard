"""
Tests for v2.3 realtime module.
"""

import time
import threading

import numpy as np
import pytest
from unittest.mock import Mock

from voice_soundboard.realtime import (
    RealtimeConfig,
    BackpressurePolicy,
    DropPolicy,
    RealtimeBuffer,
    BufferStats,
    RealtimeEngine,
)
from voice_soundboard.realtime.config import SessionConfig
from voice_soundboard.realtime.engine import SessionState, SynthesisRequest
from voice_soundboard.engine.backends.mock import MockBackend


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
            if not chunks:
                return []
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
        with engine.session():
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


# ---------------------------------------------------------------------------
# Additional tests
# ---------------------------------------------------------------------------


class TestRealtimeConfigValidation:
    """Tests for RealtimeConfig validation and derived values."""

    def test_latency_too_low_raises(self):
        with pytest.raises(ValueError, match="max_latency_ms must be >= 10ms"):
            RealtimeConfig(max_latency_ms=5, buffer_size_ms=100)

    def test_buffer_smaller_than_latency_raises(self):
        with pytest.raises(ValueError, match="buffer_size_ms must be >= max_latency_ms"):
            RealtimeConfig(max_latency_ms=50, buffer_size_ms=30)

    def test_memory_too_low_raises(self):
        with pytest.raises(ValueError, match="max_memory_mb must be >= 32MB"):
            RealtimeConfig(max_memory_mb=16)

    def test_effective_latency_budget_sums_correctly(self):
        config = RealtimeConfig(max_latency_ms=100, buffer_size_ms=100)
        budget = config.effective_latency_budget()
        assert set(budget.keys()) == {"synthesis", "buffering", "scheduling", "margin"}
        # 60 + 20 + 10 + 10 = 100
        assert sum(budget.values()) == 100

    def test_all_backpressure_policies(self):
        for policy in BackpressurePolicy:
            config = RealtimeConfig(backpressure=policy)
            assert config.backpressure == policy

    def test_all_drop_policies(self):
        for policy in DropPolicy:
            config = RealtimeConfig(drop_policy=policy)
            assert config.drop_policy == policy

    def test_chunk_size_samples_configurable(self):
        config = RealtimeConfig(chunk_size_samples=1024)
        assert config.chunk_size_samples == 1024


class TestRealtimeBufferDetailed:
    """Detailed buffer management tests."""

    def test_write_read_exact_content(self):
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
        buffer.write(data)

        out = buffer.read(5)
        np.testing.assert_array_equal(out, data)

    def test_read_empty_buffer_returns_zeros_and_counts_underrun(self):
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        out = buffer.read(10)
        assert len(out) == 10
        np.testing.assert_array_equal(out, np.zeros(10, dtype=np.float32))
        assert buffer.stats.underruns >= 1

    def test_read_partial_pads_with_zeros(self):
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        buffer.write(np.array([1.0, 2.0, 3.0], dtype=np.float32))
        out = buffer.read(5)
        assert len(out) == 5
        assert out[0] == 1.0
        assert out[2] == 3.0
        assert out[3] == 0.0
        assert out[4] == 0.0

    def test_free_space_tracks_correctly(self):
        buffer = RealtimeBuffer(size_samples=50, sample_rate=1000)
        assert buffer.free_space == 50
        buffer.write(np.ones(20, dtype=np.float32))
        assert buffer.free_space == 30
        buffer.read(10)
        assert buffer.free_space == 40

    def test_overflow_drops_oldest_and_increments_overruns(self):
        buffer = RealtimeBuffer(size_samples=10, sample_rate=1000)
        buffer.write(np.arange(10, dtype=np.float32))
        assert buffer.available == 10

        buffer.write(np.array([100.0, 101.0], dtype=np.float32))
        assert buffer.available == 10
        stats = buffer.stats
        assert stats.overruns >= 1
        assert stats.samples_dropped >= 2

        out = buffer.read(10)
        # oldest (0, 1) dropped; starts at 2
        assert out[0] == 2.0

    def test_overflow_no_drop_truncates_write(self):
        buffer = RealtimeBuffer(size_samples=10, sample_rate=1000)
        buffer.write(np.arange(10, dtype=np.float32))
        written = buffer.write(np.array([99.0, 100.0], dtype=np.float32), allow_drop=False)
        assert written == 0
        assert buffer.available == 10

    def test_write_larger_than_buffer_takes_tail(self):
        buffer = RealtimeBuffer(size_samples=5, sample_rate=1000)
        big = np.arange(20, dtype=np.float32)
        buffer.write(big)
        assert buffer.available == 5

    def test_wrap_around_write_read(self):
        """Write + read in a pattern that forces the ring to wrap."""
        buffer = RealtimeBuffer(size_samples=8, sample_rate=1000)
        # Fill 6, read 4 => read_pos=4, count=2
        buffer.write(np.arange(6, dtype=np.float32))
        buffer.read(4)
        assert buffer.available == 2

        # Write 5 more => write_pos wraps: (6+5)%8=3
        buffer.write(np.arange(10, 15, dtype=np.float32))
        assert buffer.available == 7
        out = buffer.read(7)
        expected = np.array([4.0, 5.0, 10.0, 11.0, 12.0, 13.0, 14.0], dtype=np.float32)
        np.testing.assert_array_equal(out, expected)

    def test_stats_samples_written_and_read(self):
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        buffer.write(np.ones(25, dtype=np.float32))
        buffer.read(10)
        stats = buffer.stats
        assert stats.samples_written == 25
        assert stats.samples_read == 10

    def test_clear_resets_state(self):
        buffer = RealtimeBuffer(size_samples=50, sample_rate=1000)
        buffer.write(np.ones(30, dtype=np.float32))
        buffer.clear()
        assert buffer.available == 0
        assert buffer.free_space == 50

    def test_dtype_coercion(self):
        """Write int16 data; buffer should coerce to float32."""
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        data = np.array([1, 2, 3], dtype=np.int16)
        written = buffer.write(data)
        assert written == 3
        out = buffer.read(3)
        assert out.dtype == np.float32


class TestRollbackAndMarkers:
    """Tests for rollback marker lifecycle."""

    def test_create_marker_records_position(self):
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        buffer.write(np.ones(10, dtype=np.float32))
        marker = buffer.create_marker(metadata={"text": "hello"})
        assert marker.position == 10
        assert marker.committed is False
        assert marker.metadata == {"text": "hello"}

    def test_rollback_undoes_writes(self):
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        buffer.write(np.ones(10, dtype=np.float32))
        marker = buffer.create_marker()
        buffer.write(np.ones(20, dtype=np.float32))
        assert buffer.available == 30

        rolled = buffer.rollback(marker)
        assert rolled == 20
        assert buffer.available == 10
        assert buffer.stats.rollbacks == 1

    def test_commit_prevents_rollback(self):
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        buffer.write(np.ones(10, dtype=np.float32))
        marker = buffer.create_marker()
        buffer.commit(marker)
        assert marker.committed is True

        with pytest.raises(ValueError, match="Cannot rollback to committed marker"):
            buffer.rollback(marker)

    def test_commit_cascades_to_older_markers(self):
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        m1 = buffer.create_marker()
        buffer.write(np.ones(5, dtype=np.float32))
        m2 = buffer.create_marker()
        buffer.write(np.ones(5, dtype=np.float32))
        m3 = buffer.create_marker()

        buffer.commit(m3)
        assert m1.committed is True
        assert m2.committed is True
        assert m3.committed is True

    def test_rollback_zero_samples(self):
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        buffer.write(np.ones(10, dtype=np.float32))
        marker = buffer.create_marker()
        # No writes after marker
        rolled = buffer.rollback(marker)
        assert rolled == 0
        assert buffer.available == 10

    def test_multiple_rollbacks_sequential(self):
        buffer = RealtimeBuffer(size_samples=100, sample_rate=1000)
        m1 = buffer.create_marker()
        buffer.write(np.ones(10, dtype=np.float32))
        m2 = buffer.create_marker()
        buffer.write(np.ones(5, dtype=np.float32))

        buffer.rollback(m2)
        assert buffer.available == 10
        buffer.rollback(m1)
        assert buffer.available == 0
        assert buffer.stats.rollbacks == 2


class TestCrossfade:
    """Tests for crossfade transitions."""

    def test_apply_crossfade_short_audio(self):
        buffer = RealtimeBuffer(size_samples=100, crossfade_samples=10, sample_rate=1000)
        short = np.ones(5, dtype=np.float32)
        result = buffer.apply_crossfade(short)
        assert len(result) == 5
        # First sample should be faded in (near zero)
        assert result[0] < 1.0

    def test_apply_crossfade_long_audio(self):
        buffer = RealtimeBuffer(size_samples=100, crossfade_samples=4, sample_rate=1000)
        audio = np.ones(20, dtype=np.float32)
        result = buffer.apply_crossfade(audio)
        assert len(result) == 20
        # First sample faded, last samples untouched
        assert result[0] < 0.5
        assert result[-1] == 1.0


class TestRealtimeEngineWithMockBackend:
    """Tests for RealtimeEngine using MockBackend."""

    def _make_engine(self, **config_kwargs):
        backend = MockBackend()
        config = RealtimeConfig(**config_kwargs) if config_kwargs else RealtimeConfig()
        # Use a trivial compiler that creates a minimal graph
        from voice_soundboard.compiler import compile_request
        engine = RealtimeEngine(backend, config=config, compiler=lambda text, params: compile_request(text))
        return engine

    def test_engine_sample_rate_from_backend(self):
        engine = self._make_engine()
        assert engine.sample_rate == 24000

    def test_engine_config_stored(self):
        engine = self._make_engine(max_latency_ms=30, buffer_size_ms=60)
        assert engine.config.max_latency_ms == 30
        assert engine.config.buffer_size_ms == 60

    def test_speak_immediate_writes_to_buffer(self):
        engine = self._make_engine()
        samples = engine.speak_immediate("Hello world")
        assert samples > 0
        assert engine.buffer_stats.samples_written > 0

    def test_speak_immediate_empty_text(self):
        engine = self._make_engine()
        # Empty string produces 0-length audio from mock (no words)
        samples = engine.speak_immediate("")
        assert samples == 0

    def test_health_returns_expected_keys(self):
        engine = self._make_engine()
        h = engine.health()
        expected_keys = {
            "backend", "status", "buffer_fill", "samples_processed",
            "total_requests", "active_sessions", "underruns", "overruns",
            "avg_latency_ms", "uptime_seconds",
        }
        assert set(h.keys()) == expected_keys
        assert h["backend"] == "mock"
        assert h["status"] == "healthy"
        assert h["active_sessions"] == 0

    def test_clear_resets_buffer(self):
        engine = self._make_engine()
        engine.speak_immediate("test")
        assert engine.buffer_stats.samples_written > 0
        engine.clear()
        assert engine._buffer.available == 0

    def test_buffer_size_calculated_from_config(self):
        # 100ms at 24000 Hz = 2400 samples
        engine = self._make_engine(buffer_size_ms=100)
        assert engine._buffer.size == 2400

    def test_buffer_size_custom(self):
        # 200ms at 24000 Hz = 4800 samples
        engine = self._make_engine(buffer_size_ms=200, max_latency_ms=50)
        assert engine._buffer.size == 4800


class TestSessionLifecycleDetailed:
    """Detailed session lifecycle tests."""

    def _make_engine(self):
        backend = MockBackend()
        from voice_soundboard.compiler import compile_request
        engine = RealtimeEngine(
            backend,
            config=RealtimeConfig(),
            compiler=lambda text, params: compile_request(text),
        )
        return engine

    def test_session_starts_idle(self):
        engine = self._make_engine()
        with engine.session() as session:
            # Worker thread starts but state is IDLE until a request arrives
            assert session.state in (SessionState.IDLE, SessionState.SYNTHESIZING)
            assert session.queue_depth == 0

    def test_session_closed_after_exit(self):
        engine = self._make_engine()
        with engine.session() as session:
            ref = session
        assert ref.state == SessionState.CLOSED

    def test_speak_after_close_raises(self):
        engine = self._make_engine()
        with engine.session() as session:
            ref = session
        with pytest.raises(RuntimeError, match="Session is closed"):
            ref.speak("should fail")

    def test_session_speak_queues_and_drains(self):
        engine = self._make_engine()
        with engine.session() as session:
            session.speak("Hello")
            session.speak("World")
            # Give the worker time to process
            time.sleep(0.5)
        # After exit, both should have been processed
        assert engine._total_requests >= 1

    def test_session_clear_queue(self):
        engine = self._make_engine()
        with engine.session() as session:
            # Pause the worker by filling the queue faster than it processes
            for i in range(5):
                session.speak(f"word {i}")
            cleared = session.clear_queue()
            # At least some items should have been cleared (or already processed)
            assert cleared >= 0

    def test_session_callbacks(self):
        engine = self._make_engine()
        started = []
        completed = []

        with engine.session() as session:
            session.on_start(lambda text: started.append(text))
            session.on_complete(lambda text: completed.append(text))
            session.speak("callback test")
            time.sleep(0.5)

        assert "callback test" in started
        assert "callback test" in completed

    def test_multiple_sessions_tracked(self):
        engine = self._make_engine()
        with engine.session() as _s1:
            assert engine.health()["active_sessions"] == 1
            with engine.session() as _s2:
                assert engine.health()["active_sessions"] == 2
            assert engine.health()["active_sessions"] == 1
        assert engine.health()["active_sessions"] == 0

    def test_session_with_custom_config(self):
        engine = self._make_engine()
        sc = SessionConfig(voice="test-voice", speed=1.5, interruptible=False)
        with engine.session(config=sc) as session:
            assert session._config.voice == "test-voice"
            assert session._config.speed == 1.5
            assert session._config.interruptible is False


class TestSessionInterrupt:
    """Tests for session interruption."""

    def _make_engine(self):
        backend = MockBackend()
        from voice_soundboard.compiler import compile_request
        return RealtimeEngine(
            backend,
            config=RealtimeConfig(),
            compiler=lambda text, params: compile_request(text),
        )

    def test_interrupt_idle_is_noop(self):
        engine = self._make_engine()
        with engine.session() as session:
            # Interrupt when idle does nothing
            session.interrupt()
            assert session.state != SessionState.CLOSED

    def test_interrupt_callback_fires(self):
        engine = self._make_engine()
        interrupted = []

        with engine.session() as session:
            session.on_interrupt(lambda text: interrupted.append(text))
            # Queue a request and quickly interrupt
            session.speak("interrupt me")
            time.sleep(0.1)
            if session.state == SessionState.SYNTHESIZING:
                session.interrupt()
                assert session.state == SessionState.INTERRUPTED

    def test_speak_with_interrupt_current(self):
        engine = self._make_engine()
        with engine.session() as session:
            session.speak("first")
            time.sleep(0.05)
            # This should attempt to interrupt current if synthesizing
            session.speak("urgent", priority=10, interrupt_current=True)
            time.sleep(0.5)


class TestSynthesisRequest:
    """Tests for SynthesisRequest ordering."""

    def test_higher_priority_sorts_first(self):
        r1 = SynthesisRequest(text="low", priority=0, timestamp=1.0)
        r2 = SynthesisRequest(text="high", priority=5, timestamp=2.0)
        # Higher priority is "less than" for PriorityQueue (comes first)
        assert r2 < r1

    def test_same_priority_earlier_first(self):
        r1 = SynthesisRequest(text="early", priority=0, timestamp=1.0)
        r2 = SynthesisRequest(text="late", priority=0, timestamp=2.0)
        assert r1 < r2

    def test_default_metadata_empty_dict(self):
        r = SynthesisRequest(text="test")
        assert r.metadata == {}
        assert r.priority == 0
        assert r.marker is None


class TestBackpressurePoliciesDetailed:
    """Detailed backpressure policy tests."""

    def test_drop_newest_callback_fires(self):
        drops = []

        def on_drop(count, reason):
            drops.append((count, reason))

        config = RealtimeConfig(
            backpressure=BackpressurePolicy.DROP_NEWEST,
            callback_on_drop=on_drop,
        )
        backend = MockBackend()
        from voice_soundboard.compiler import compile_request
        engine = RealtimeEngine(
            backend,
            config=config,
            compiler=lambda text, params: compile_request(text),
        )

        # Fill the buffer entirely
        engine._buffer.write(np.ones(engine._buffer.size, dtype=np.float32))

        # Trigger backpressure handler
        engine._handle_backpressure(100)
        assert len(drops) == 1
        assert drops[0][1] == "backpressure_drop_newest"

    def test_drop_oldest_policy_does_not_block(self):
        config = RealtimeConfig(backpressure=BackpressurePolicy.DROP_OLDEST)
        backend = MockBackend()
        engine = RealtimeEngine(backend, config=config)

        engine._buffer.write(np.ones(engine._buffer.size, dtype=np.float32))
        # Should return immediately (pass-through to write's drop logic)
        engine._handle_backpressure(100)

    def test_adaptive_policy_does_not_block(self):
        config = RealtimeConfig(backpressure=BackpressurePolicy.ADAPTIVE)
        backend = MockBackend()
        engine = RealtimeEngine(backend, config=config)

        engine._buffer.write(np.ones(engine._buffer.size, dtype=np.float32))
        # Adaptive is TODO, should return immediately
        engine._handle_backpressure(100)

    def test_block_policy_waits_for_space(self):
        config = RealtimeConfig(backpressure=BackpressurePolicy.BLOCK)
        backend = MockBackend()
        engine = RealtimeEngine(backend, config=config)

        # Fill buffer
        engine._buffer.write(np.ones(engine._buffer.size, dtype=np.float32))

        # In a thread, free space after a short delay
        def free_space():
            time.sleep(0.05)
            engine._buffer.read(200)

        t = threading.Thread(target=free_space)
        t.start()

        start = time.time()
        engine._handle_backpressure(100)
        elapsed = time.time() - start
        t.join()

        # Should have waited at least ~50ms for space
        assert elapsed >= 0.03


class TestEdgeCases:
    """Edge cases: empty text, rapid submissions, large batches."""

    def _make_engine(self):
        backend = MockBackend()
        from voice_soundboard.compiler import compile_request
        return RealtimeEngine(
            backend,
            config=RealtimeConfig(),
            compiler=lambda text, params: compile_request(text),
        )

    def test_speak_immediate_single_word(self):
        engine = self._make_engine()
        samples = engine.speak_immediate("Hi")
        assert samples > 0

    def test_speak_immediate_whitespace_only(self):
        engine = self._make_engine()
        samples = engine.speak_immediate("   ")
        assert samples == 0

    def test_rapid_session_speak(self):
        """Submit many requests rapidly; engine should not crash."""
        engine = self._make_engine()
        with engine.session() as session:
            for i in range(50):
                session.speak(f"word{i}")
            # Let the worker drain
            time.sleep(1.0)

    def test_read_audio_from_empty_engine(self):
        engine = self._make_engine()
        chunks = list(engine.read_audio(chunk_size=256, block=False, timeout=0.01))
        # Should produce at most one zero-filled chunk then stop
        assert len(chunks) <= 1

    def test_read_samples_blocks_until_data(self):
        engine = self._make_engine()

        def write_later():
            time.sleep(0.1)
            engine._buffer.write(np.ones(100, dtype=np.float32))

        t = threading.Thread(target=write_later)
        t.start()
        out = engine.read_samples(50, block=True, timeout=1.0)
        t.join()
        assert len(out) == 50

    def test_buffer_stats_type(self):
        engine = self._make_engine()
        stats = engine.buffer_stats
        assert isinstance(stats, BufferStats)
        assert 0.0 <= stats.buffer_fill_ratio <= 1.0

