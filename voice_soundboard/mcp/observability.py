"""
MCP Observability - Structured metadata for agent reasoning.

Provides structured output metadata for agents to understand synthesis
results, not debug logs. This enables agents to make informed decisions
about audio usage, cost, and quality.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from voice_soundboard.adapters import VoiceEngine

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of observability metrics."""
    
    LATENCY = "latency"
    DURATION = "duration"
    COST = "cost"
    QUALITY = "quality"
    CACHE = "cache"


@dataclass
class MetadataConfig:
    """Configuration for metadata collection.
    
    Attributes:
        include_latency: Include synthesis latency
        include_duration: Include audio duration
        include_voice: Include voice information
        include_backend: Include backend information
        include_emotion: Include emotion applied
        include_cost: Include cost estimate
        include_cache: Include cache information
        include_quality: Include quality metrics
    """
    
    include_latency: bool = True
    include_duration: bool = True
    include_voice: bool = True
    include_backend: bool = True
    include_emotion: bool = True
    include_cost: bool = True
    include_cache: bool = True
    include_quality: bool = False  # Expensive, off by default


@dataclass
class SynthesisMetadata:
    """
    Structured metadata returned from synthesis operations.
    
    This is structured output for agents, not debug logs.
    Agents can use this data to:
    - Track costs
    - Optimize caching
    - Monitor latency
    - Adjust voice selection
    
    Attributes:
        latency_ms: Time to complete synthesis in milliseconds
        duration_ms: Audio duration in milliseconds
        voice: Voice identifier used
        backend: Backend used for synthesis
        emotion: Emotion applied (if any)
        cost_estimate: Estimated cost in USD (0.0 for local)
        cache_hit: Whether result was served from cache
        character_count: Number of characters synthesized
        word_count: Number of words synthesized
        sample_rate: Output sample rate
        channels: Output channels (1=mono, 2=stereo)
        quality_score: Quality score (0.0 to 1.0) if evaluated
    """
    
    latency_ms: float = 0.0
    duration_ms: float = 0.0
    voice: Optional[str] = None
    backend: Optional[str] = None
    emotion: Optional[str] = None
    cost_estimate: float = 0.0
    cache_hit: bool = False
    character_count: int = 0
    word_count: int = 0
    sample_rate: int = 24000
    channels: int = 1
    quality_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {}
        
        if self.latency_ms > 0:
            result["latency_ms"] = round(self.latency_ms, 2)
        if self.duration_ms > 0:
            result["duration_ms"] = round(self.duration_ms, 2)
        if self.voice:
            result["voice"] = self.voice
        if self.backend:
            result["backend"] = self.backend
        if self.emotion:
            result["emotion"] = self.emotion
        
        result["cost_estimate"] = round(self.cost_estimate, 6)
        result["cache_hit"] = self.cache_hit
        
        if self.character_count > 0:
            result["character_count"] = self.character_count
        if self.word_count > 0:
            result["word_count"] = self.word_count
        
        result["sample_rate"] = self.sample_rate
        result["channels"] = self.channels
        
        if self.quality_score is not None:
            result["quality_score"] = round(self.quality_score, 3)
        
        return result
    
    @property
    def real_time_factor(self) -> float:
        """Calculate real-time factor (synthesis time / audio duration)."""
        if self.duration_ms <= 0:
            return 0.0
        return self.latency_ms / self.duration_ms
    
    @property
    def characters_per_second(self) -> float:
        """Calculate synthesis speed in characters per second."""
        if self.latency_ms <= 0:
            return 0.0
        return self.character_count / (self.latency_ms / 1000)


@dataclass
class BackendPricing:
    """Pricing information for a TTS backend.
    
    Attributes:
        backend: Backend identifier
        cost_per_character: Cost per character in USD
        cost_per_request: Fixed cost per request in USD
        free_tier_characters: Free characters per month
    """
    
    backend: str
    cost_per_character: float = 0.0
    cost_per_request: float = 0.0
    free_tier_characters: int = 0


# Default pricing for known backends
DEFAULT_PRICING: Dict[str, BackendPricing] = {
    "kokoro": BackendPricing("kokoro", 0.0, 0.0, float("inf")),  # Free (local)
    "piper": BackendPricing("piper", 0.0, 0.0, float("inf")),  # Free (local)
    "openai": BackendPricing("openai", 0.000015, 0.0, 0),  # $15 per 1M chars
    "elevenlabs": BackendPricing("elevenlabs", 0.00018, 0.0, 10000),  # ~$180 per 1M
    "azure": BackendPricing("azure", 0.000016, 0.0, 500000),  # $16 per 1M, 500k free
    "google": BackendPricing("google", 0.000016, 0.0, 4000000),  # $16 per 1M, 4M free
    "amazon": BackendPricing("amazon", 0.000016, 0.0, 5000000),  # $16 per 1M, 5M free
}


class MetadataCollector:
    """
    Collector for synthesis metadata.
    
    Tracks synthesis operations and builds structured metadata
    for agent consumption.
    
    Example:
        collector = MetadataCollector()
        
        with collector.track("synthesis-123") as tracker:
            result = engine.speak(text)
            tracker.set_duration(result.duration)
            tracker.set_voice(result.voice)
        
        metadata = collector.get_metadata("synthesis-123")
    """
    
    def __init__(
        self,
        config: Optional[MetadataConfig] = None,
        pricing: Optional[Dict[str, BackendPricing]] = None,
    ):
        """
        Initialize metadata collector.
        
        Args:
            config: Metadata configuration
            pricing: Backend pricing information
        """
        self.config = config or MetadataConfig()
        self.pricing = pricing or DEFAULT_PRICING.copy()
        
        self._active_trackers: Dict[str, "SynthesisTracker"] = {}
        self._collected: List[SynthesisMetadata] = []
        self._cache_stats = {"hits": 0, "misses": 0}
    
    def track(
        self,
        operation_id: str,
    ) -> "SynthesisTracker":
        """
        Create a tracker for a synthesis operation.
        
        Args:
            operation_id: Unique operation identifier
            
        Returns:
            SynthesisTracker context manager
        """
        tracker = SynthesisTracker(
            operation_id=operation_id,
            collector=self,
        )
        self._active_trackers[operation_id] = tracker
        return tracker
    
    def estimate_cost(
        self,
        backend: str,
        character_count: int,
    ) -> float:
        """
        Estimate cost for synthesis.
        
        Args:
            backend: Backend identifier
            character_count: Number of characters
            
        Returns:
            Estimated cost in USD
        """
        pricing = self.pricing.get(backend)
        if not pricing:
            return 0.0
        
        return (
            character_count * pricing.cost_per_character +
            pricing.cost_per_request
        )
    
    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self._cache_stats["hits"] += 1
    
    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self._cache_stats["misses"] += 1
    
    def get_cache_hit_rate(self) -> float:
        """
        Get cache hit rate.
        
        Returns:
            Hit rate as fraction (0.0 to 1.0)
        """
        total = self._cache_stats["hits"] + self._cache_stats["misses"]
        if total == 0:
            return 0.0
        return self._cache_stats["hits"] / total
    
    def finalize(
        self,
        operation_id: str,
        metadata: SynthesisMetadata,
    ) -> SynthesisMetadata:
        """
        Finalize and store metadata.
        
        Args:
            operation_id: Operation identifier
            metadata: Collected metadata
            
        Returns:
            Finalized metadata
        """
        self._active_trackers.pop(operation_id, None)
        self._collected.append(metadata)
        
        # Update cache stats
        if metadata.cache_hit:
            self.record_cache_hit()
        else:
            self.record_cache_miss()
        
        return metadata
    
    def get_metadata(
        self,
        operation_id: str,
    ) -> Optional[SynthesisMetadata]:
        """
        Get metadata for an operation.
        
        Args:
            operation_id: Operation identifier
            
        Returns:
            SynthesisMetadata or None
        """
        tracker = self._active_trackers.get(operation_id)
        if tracker:
            return tracker.metadata
        return None
    
    def get_aggregate_stats(self) -> Dict[str, Any]:
        """
        Get aggregate statistics.
        
        Returns:
            Aggregate statistics dictionary
        """
        if not self._collected:
            return {}
        
        total_latency = sum(m.latency_ms for m in self._collected)
        total_duration = sum(m.duration_ms for m in self._collected)
        total_cost = sum(m.cost_estimate for m in self._collected)
        total_chars = sum(m.character_count for m in self._collected)
        
        return {
            "total_operations": len(self._collected),
            "total_latency_ms": round(total_latency, 2),
            "avg_latency_ms": round(total_latency / len(self._collected), 2),
            "total_duration_ms": round(total_duration, 2),
            "total_cost_usd": round(total_cost, 6),
            "total_characters": total_chars,
            "cache_hit_rate": round(self.get_cache_hit_rate(), 3),
        }
    
    def set_pricing(
        self,
        backend: str,
        pricing: BackendPricing,
    ) -> None:
        """
        Set pricing for a backend.
        
        Args:
            backend: Backend identifier
            pricing: Pricing information
        """
        self.pricing[backend] = pricing


class SynthesisTracker:
    """
    Tracker for individual synthesis operations.
    
    Used as a context manager to track timing and collect metadata.
    
    Example:
        with collector.track("op-123") as tracker:
            result = engine.speak(text)
            tracker.set_duration(result.duration * 1000)
            tracker.set_voice(result.voice)
    """
    
    def __init__(
        self,
        operation_id: str,
        collector: MetadataCollector,
    ):
        """
        Initialize tracker.
        
        Args:
            operation_id: Operation identifier
            collector: Parent collector
        """
        self.operation_id = operation_id
        self._collector = collector
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._metadata = SynthesisMetadata()
    
    @property
    def metadata(self) -> SynthesisMetadata:
        """Get current metadata."""
        return self._metadata
    
    def __enter__(self) -> "SynthesisTracker":
        """Start tracking."""
        self._start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End tracking and finalize."""
        self._end_time = time.time()
        
        if self._start_time:
            self._metadata.latency_ms = (self._end_time - self._start_time) * 1000
        
        # Calculate cost estimate
        if self._metadata.backend and self._metadata.character_count > 0:
            self._metadata.cost_estimate = self._collector.estimate_cost(
                self._metadata.backend,
                self._metadata.character_count,
            )
        
        self._collector.finalize(self.operation_id, self._metadata)
    
    def set_duration(self, duration_ms: float) -> "SynthesisTracker":
        """Set audio duration."""
        self._metadata.duration_ms = duration_ms
        return self
    
    def set_voice(self, voice: str) -> "SynthesisTracker":
        """Set voice used."""
        self._metadata.voice = voice
        return self
    
    def set_backend(self, backend: str) -> "SynthesisTracker":
        """Set backend used."""
        self._metadata.backend = backend
        return self
    
    def set_emotion(self, emotion: str) -> "SynthesisTracker":
        """Set emotion applied."""
        self._metadata.emotion = emotion
        return self
    
    def set_text_stats(
        self,
        text: str,
    ) -> "SynthesisTracker":
        """Set text statistics from input text."""
        self._metadata.character_count = len(text)
        self._metadata.word_count = len(text.split())
        return self
    
    def set_cache_hit(self, hit: bool = True) -> "SynthesisTracker":
        """Set cache hit status."""
        self._metadata.cache_hit = hit
        return self
    
    def set_audio_format(
        self,
        sample_rate: int,
        channels: int = 1,
    ) -> "SynthesisTracker":
        """Set audio format."""
        self._metadata.sample_rate = sample_rate
        self._metadata.channels = channels
        return self
    
    def set_quality_score(self, score: float) -> "SynthesisTracker":
        """Set quality score."""
        self._metadata.quality_score = max(0.0, min(1.0, score))
        return self


def collect_synthesis_metadata(
    engine: "VoiceEngine",
    text: str,
    result: Any,
    latency_ms: float,
) -> SynthesisMetadata:
    """
    Convenience function to collect metadata from synthesis result.
    
    Args:
        engine: Voice engine used
        text: Input text
        result: Synthesis result
        latency_ms: Measured latency
        
    Returns:
        SynthesisMetadata
    """
    metadata = SynthesisMetadata(
        latency_ms=latency_ms,
        character_count=len(text),
        word_count=len(text.split()),
    )
    
    # Extract from engine
    if hasattr(engine, "_backend_name"):
        metadata.backend = engine._backend_name
    if hasattr(engine, "config") and hasattr(engine.config, "default_voice"):
        metadata.voice = engine.config.default_voice
    
    # Extract from result
    if hasattr(result, "duration"):
        metadata.duration_ms = result.duration * 1000
    if hasattr(result, "voice"):
        metadata.voice = result.voice
    if hasattr(result, "sample_rate"):
        metadata.sample_rate = result.sample_rate
    
    # Estimate cost
    if metadata.backend:
        pricing = DEFAULT_PRICING.get(metadata.backend)
        if pricing:
            metadata.cost_estimate = (
                metadata.character_count * pricing.cost_per_character
            )
    
    return metadata
