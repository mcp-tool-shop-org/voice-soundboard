"""
Caching Module - Graph and audio caching for performance.

v2.1 Feature (P2): Graph caching for faster repeated synthesis.

Provides:
- Graph caching by content hash
- LRU eviction
- Thread-safe access
- Statistics tracking

Usage:
    engine = VoiceEngine(Config(cache_graphs=True))
    
    # First call: compiles and caches
    engine.speak("Welcome to the show!")
    
    # Second call: cache hit, skips compilation
    engine.speak("Welcome to the show!")
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, TypeVar, Generic, Callable

from voice_soundboard.graph import ControlGraph

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def reset(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0


@dataclass
class CacheEntry(Generic[T]):
    """A cached item with metadata."""
    value: T
    key: str
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    size_bytes: int = 0


class LRUCache(Generic[T]):
    """Thread-safe LRU cache with size limit.
    
    Provides O(1) access with automatic eviction of
    least recently used items.
    
    Example:
        cache = LRUCache[ControlGraph](max_size=100)
        cache.put("key", graph)
        graph = cache.get("key")
    """
    
    def __init__(self, max_size: int = 100):
        """Initialize cache.
        
        Args:
            max_size: Maximum number of items to cache
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = CacheStats(max_size=max_size)
    
    def get(self, key: str) -> T | None:
        """Get item from cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found
        """
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None
            
            # Move to end (most recent)
            self._cache.move_to_end(key)
            
            entry = self._cache[key]
            entry.last_accessed = time.time()
            entry.access_count += 1
            
            self._stats.hits += 1
            return entry.value
    
    def put(self, key: str, value: T, size_bytes: int = 0):
        """Put item in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            size_bytes: Optional size for metrics
        """
        with self._lock:
            # Remove if exists (will re-add at end)
            if key in self._cache:
                del self._cache[key]
            
            # Evict oldest if at capacity
            while len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats.evictions += 1
            
            # Add new entry
            self._cache[key] = CacheEntry(
                value=value,
                key=key,
                size_bytes=size_bytes,
            )
            self._stats.size = len(self._cache)
    
    def remove(self, key: str) -> bool:
        """Remove item from cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.size = len(self._cache)
                return True
            return False
    
    def clear(self):
        """Clear all cached items."""
        with self._lock:
            self._cache.clear()
            self._stats.size = 0
    
    def contains(self, key: str) -> bool:
        """Check if key exists in cache."""
        with self._lock:
            return key in self._cache
    
    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats
    
    def __len__(self) -> int:
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        return self.contains(key)


class GraphCache:
    """Specialized cache for ControlGraphs.
    
    Caches compiled graphs to skip compilation on repeated requests.
    
    Usage:
        cache = GraphCache()
        
        key = cache.make_key(text="Hello", voice="bella")
        if cached := cache.get(key):
            graph = cached
        else:
            graph = compile_request(text, voice=voice)
            cache.put(key, graph)
    """
    
    def __init__(self, max_size: int = 100, enabled: bool = True):
        """Initialize graph cache.
        
        Args:
            max_size: Maximum graphs to cache
            enabled: Whether caching is enabled
        """
        self.enabled = enabled
        self._cache = LRUCache[ControlGraph](max_size=max_size)
    
    @staticmethod
    def make_key(
        text: str,
        voice: str | None = None,
        preset: str | None = None,
        emotion: str | None = None,
        style: str | None = None,
        speed: float | None = None,
    ) -> str:
        """Create cache key from synthesis parameters.
        
        Args:
            text: Source text
            voice, preset, emotion, style, speed: Synthesis parameters
        
        Returns:
            Hash key for caching
        """
        # Combine all parameters into a string
        parts = [
            text,
            f"v:{voice or 'default'}",
            f"p:{preset or 'none'}",
            f"e:{emotion or 'none'}",
            f"s:{style or 'none'}",
            f"sp:{speed or 1.0}",
        ]
        combined = "|".join(parts)
        
        # Hash for shorter key
        return hashlib.sha256(combined.encode()).hexdigest()[:32]
    
    def get(self, key: str) -> ControlGraph | None:
        """Get cached graph."""
        if not self.enabled:
            return None
        return self._cache.get(key)
    
    def put(self, key: str, graph: ControlGraph):
        """Cache a graph."""
        if not self.enabled:
            return
        self._cache.put(key, graph)
    
    def invalidate(self, key: str) -> bool:
        """Invalidate a cached graph."""
        return self._cache.remove(key)
    
    def clear(self):
        """Clear all cached graphs."""
        self._cache.clear()
    
    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._cache.stats
    
    @property
    def hit_rate(self) -> float:
        """Get cache hit rate."""
        return self._cache.stats.hit_rate


def cached_compile(
    cache: GraphCache,
    compile_fn: Callable[..., ControlGraph],
) -> Callable[..., ControlGraph]:
    """Decorator to add caching to compile function.
    
    Args:
        cache: GraphCache instance
        compile_fn: Original compile function
    
    Returns:
        Wrapped function with caching
    
    Example:
        cache = GraphCache()
        compile = cached_compile(cache, compile_request)
        graph = compile(text, voice=voice)  # Uses cache
    """
    def wrapper(
        text: str,
        *,
        voice: str | None = None,
        preset: str | None = None,
        emotion: str | None = None,
        style: str | None = None,
        speed: float | None = None,
        **kwargs,
    ) -> ControlGraph:
        # Generate key
        key = cache.make_key(
            text=text,
            voice=voice,
            preset=preset,
            emotion=emotion,
            style=style,
            speed=speed,
        )
        
        # Check cache
        if cached := cache.get(key):
            return cached
        
        # Compile
        graph = compile_fn(
            text,
            voice=voice,
            preset=preset,
            emotion=emotion,
            style=style,
            speed=speed,
            **kwargs,
        )
        
        # Cache result
        cache.put(key, graph)
        
        return graph
    
    return wrapper
