"""
Tests for v2.1 caching features.

Tests GraphCache and LRUCache for performance optimization.
"""

import pytest
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor

from voice_soundboard.runtime.cache import GraphCache, LRUCache, CacheStats
from voice_soundboard.graph import ControlGraph, TokenEvent, SpeakerRef


class TestLRUCache:
    """Tests for generic LRUCache."""
    
    def test_basic_set_get(self):
        """Basic set and get operations."""
        cache = LRUCache(max_size=10)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
    
    def test_get_missing(self):
        """Getting missing key returns None."""
        cache = LRUCache(max_size=10)
        
        assert cache.get("nonexistent") is None
    
    def test_eviction_on_full(self):
        """LRU item is evicted when cache is full."""
        cache = LRUCache(max_size=3)
        
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        
        # Access 'a' to make it recently used
        cache.get("a")
        
        # Add new item, should evict 'b' (least recently used)
        cache.set("d", 4)
        
        assert cache.get("a") == 1  # Still there (recently accessed)
        assert cache.get("b") is None  # Evicted
        assert cache.get("c") == 3
        assert cache.get("d") == 4
    
    def test_clear(self):
        """Clear removes all items."""
        cache = LRUCache(max_size=10)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert len(cache) == 0
    
    def test_size(self):
        """Cache reports correct size."""
        cache = LRUCache(max_size=10)
        
        assert len(cache) == 0
        
        cache.set("a", 1)
        assert len(cache) == 1
        
        cache.set("b", 2)
        assert len(cache) == 2
    
    def test_thread_safety(self):
        """Cache is thread-safe."""
        cache = LRUCache(max_size=100)
        
        def writer(n):
            for i in range(100):
                cache.set(f"key-{n}-{i}", i)
        
        def reader(n):
            for i in range(100):
                cache.get(f"key-{n}-{i}")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(5):
                futures.append(executor.submit(writer, i))
                futures.append(executor.submit(reader, i))
            
            for f in futures:
                f.result()
        
        # Should complete without errors


class TestCacheStats:
    """Tests for CacheStats."""
    
    def test_hit_rate(self):
        """Calculate hit rate."""
        stats = CacheStats()
        
        stats.record_hit()
        stats.record_hit()
        stats.record_miss()
        
        assert stats.hit_rate() == pytest.approx(2/3, abs=0.01)
    
    def test_empty_stats(self):
        """Empty stats have 0 hit rate."""
        stats = CacheStats()
        
        assert stats.hit_rate() == 0.0
    
    def test_reset(self):
        """Reset clears stats."""
        stats = CacheStats()
        
        stats.record_hit()
        stats.record_miss()
        
        stats.reset()
        
        assert stats.hits == 0
        assert stats.misses == 0


class TestGraphCache:
    """Tests for GraphCache."""
    
    @pytest.fixture
    def sample_graph(self):
        """Create a sample graph."""
        return ControlGraph(
            tokens=[
                TokenEvent(text="Hello", start_ms=0, duration_ms=100),
                TokenEvent(text="world", start_ms=100, duration_ms=100),
            ],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
    
    @pytest.fixture
    def sample_audio(self):
        """Create sample audio data."""
        return np.zeros(4800, dtype=np.float32)
    
    def test_cache_graph(self, sample_graph, sample_audio):
        """Cache and retrieve a graph's audio."""
        cache = GraphCache(max_size=10)
        
        cache.put(sample_graph, sample_audio)
        
        cached = cache.get(sample_graph)
        assert cached is not None
        np.testing.assert_array_equal(cached, sample_audio)
    
    def test_cache_miss(self, sample_graph):
        """Missing graph returns None."""
        cache = GraphCache(max_size=10)
        
        result = cache.get(sample_graph)
        assert result is None
    
    def test_content_based_hashing(self, sample_audio):
        """Same content produces same cache key."""
        cache = GraphCache(max_size=10)
        
        # Two identical graphs
        g1 = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        g2 = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        
        cache.put(g1, sample_audio)
        
        # Should find using g2 since content is identical
        cached = cache.get(g2)
        assert cached is not None
    
    def test_different_graphs_different_keys(self, sample_audio):
        """Different graphs have different cache keys."""
        cache = GraphCache(max_size=10)
        
        g1 = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        g2 = ControlGraph(
            tokens=[TokenEvent(text="Goodbye")],
            speaker=SpeakerRef.from_voice("af_bella"),
        )
        
        cache.put(g1, sample_audio)
        
        # g2 should not be found
        cached = cache.get(g2)
        assert cached is None
    
    def test_stats_tracking(self, sample_graph, sample_audio):
        """Cache tracks hit/miss stats."""
        cache = GraphCache(max_size=10)
        
        # Miss
        cache.get(sample_graph)
        
        # Store and hit
        cache.put(sample_graph, sample_audio)
        cache.get(sample_graph)
        cache.get(sample_graph)
        
        stats = cache.get_stats()
        
        assert stats.misses == 1
        assert stats.hits == 2
    
    def test_invalidate(self, sample_graph, sample_audio):
        """Invalidate specific graph."""
        cache = GraphCache(max_size=10)
        
        cache.put(sample_graph, sample_audio)
        assert cache.get(sample_graph) is not None
        
        cache.invalidate(sample_graph)
        assert cache.get(sample_graph) is None
