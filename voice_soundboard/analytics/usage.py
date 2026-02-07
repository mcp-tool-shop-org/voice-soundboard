"""
Usage Tracker - Request and usage analytics.

Features:
    - Request counting by voice, language, client
    - Character/word tracking
    - Error rate monitoring
    - Prometheus/OpenTelemetry export
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable
from collections import defaultdict
from datetime import datetime, timezone, timedelta


@dataclass
class UsageMetrics:
    """Usage metrics for a time period."""
    
    requests: int = 0
    characters: int = 0
    words: int = 0
    audio_seconds: float = 0.0
    errors: int = 0
    
    # Latency percentiles
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    def __add__(self, other: "UsageMetrics") -> "UsageMetrics":
        """Add two metrics together."""
        return UsageMetrics(
            requests=self.requests + other.requests,
            characters=self.characters + other.characters,
            words=self.words + other.words,
            audio_seconds=self.audio_seconds + other.audio_seconds,
            errors=self.errors + other.errors,
        )


@dataclass
class UsageConfig:
    """Configuration for usage tracking."""
    
    # Backend
    backend: str = "memory"  # memory, prometheus, opentelemetry
    
    # Labels to track
    labels: list[str] = field(default_factory=lambda: [
        "voice", "language", "client_id", "backend"
    ])
    
    # Aggregation
    aggregation_interval_seconds: int = 60
    retention_hours: int = 168  # 1 week
    
    # Export
    prometheus_port: int | None = None
    otlp_endpoint: str | None = None
    
    # Sampling
    sample_rate: float = 1.0  # 1.0 = track all


@dataclass
class UsageQuery:
    """Query for usage data."""
    
    timeframe: str = "24h"  # 1h, 24h, 7d, 30d
    group_by: str | list[str] | None = None
    filter_voice: str | None = None
    filter_client: str | None = None
    filter_language: str | None = None


class UsageTracker:
    """
    Track usage metrics for voice synthesis.
    
    Example:
        tracker = UsageTracker(
            backend="prometheus",
            labels=["voice", "language", "client_id"],
        )
        
        # Automatic tracking with engine
        engine = VoiceEngine(Config(analytics=tracker))
        
        # Query insights
        insights = tracker.query(
            timeframe="7d",
            group_by="voice",
        )
    """
    
    def __init__(
        self,
        backend: str = "memory",
        labels: list[str] | None = None,
        config: UsageConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = UsageConfig(
                backend=backend,
                labels=labels or UsageConfig().labels,
            )
        
        # Metrics storage
        self._metrics: dict[str, list[tuple[float, UsageMetrics]]] = defaultdict(list)
        self._latencies: list[float] = []
        self._lock = threading.Lock()
        
        # Prometheus metrics
        self._prometheus_metrics = None
        if self.config.backend == "prometheus" and self.config.prometheus_port:
            self._setup_prometheus()
    
    def _setup_prometheus(self) -> None:
        """Set up Prometheus metrics."""
        try:
            from prometheus_client import Counter, Histogram, start_http_server, REGISTRY
            
            # Create metrics
            self._prometheus_metrics = {
                "requests": Counter(
                    "voice_soundboard_requests_total",
                    "Total synthesis requests",
                    self.config.labels,
                ),
                "characters": Counter(
                    "voice_soundboard_characters_total",
                    "Total characters synthesized",
                    self.config.labels,
                ),
                "errors": Counter(
                    "voice_soundboard_errors_total",
                    "Total synthesis errors",
                    self.config.labels,
                ),
                "latency": Histogram(
                    "voice_soundboard_latency_seconds",
                    "Synthesis latency",
                    self.config.labels,
                    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
                ),
                "audio_duration": Histogram(
                    "voice_soundboard_audio_duration_seconds",
                    "Generated audio duration",
                    self.config.labels,
                    buckets=[1, 5, 10, 30, 60, 120, 300],
                ),
            }
            
            # Start HTTP server
            start_http_server(self.config.prometheus_port)
            
        except ImportError:
            pass
    
    def record(
        self,
        text: str,
        voice: str,
        audio_duration: float,
        latency_ms: float,
        success: bool = True,
        client_id: str | None = None,
        language: str | None = None,
        backend: str | None = None,
    ) -> None:
        """
        Record a synthesis request.
        
        Args:
            text: Synthesized text
            voice: Voice used
            audio_duration: Duration of generated audio
            latency_ms: Request latency in milliseconds
            success: Whether request succeeded
            client_id: Client identifier
            language: Language code
            backend: Backend used
        """
        # Apply sampling
        if self.config.sample_rate < 1.0:
            import random
            if random.random() > self.config.sample_rate:
                return
        
        # Build label key
        labels = {
            "voice": voice,
            "language": language or "unknown",
            "client_id": client_id or "anonymous",
            "backend": backend or "unknown",
        }
        label_key = self._make_key(labels)
        
        # Create metrics
        metrics = UsageMetrics(
            requests=1,
            characters=len(text),
            words=len(text.split()),
            audio_seconds=audio_duration,
            errors=0 if success else 1,
        )
        
        # Store
        with self._lock:
            timestamp = time.time()
            self._metrics[label_key].append((timestamp, metrics))
            self._latencies.append(latency_ms)
            
            # Cleanup old data
            self._cleanup_old_data()
        
        # Export to Prometheus
        if self._prometheus_metrics:
            label_values = [labels.get(l, "unknown") for l in self.config.labels]
            
            self._prometheus_metrics["requests"].labels(*label_values).inc()
            self._prometheus_metrics["characters"].labels(*label_values).inc(len(text))
            self._prometheus_metrics["latency"].labels(*label_values).observe(latency_ms / 1000)
            self._prometheus_metrics["audio_duration"].labels(*label_values).observe(audio_duration)
            
            if not success:
                self._prometheus_metrics["errors"].labels(*label_values).inc()
    
    def _make_key(self, labels: dict[str, str]) -> str:
        """Create a key from labels."""
        return "|".join(f"{k}={labels.get(k, '')}" for k in sorted(self.config.labels))
    
    def _cleanup_old_data(self) -> None:
        """Remove data older than retention period."""
        cutoff = time.time() - (self.config.retention_hours * 3600)
        
        for key in list(self._metrics.keys()):
            self._metrics[key] = [
                (ts, m) for ts, m in self._metrics[key]
                if ts > cutoff
            ]
            if not self._metrics[key]:
                del self._metrics[key]
        
        # Keep only recent latencies
        max_latencies = 10000
        if len(self._latencies) > max_latencies:
            self._latencies = self._latencies[-max_latencies:]
    
    def query(
        self,
        timeframe: str = "24h",
        group_by: str | list[str] | None = None,
        **filters: Any,
    ) -> dict[str, UsageMetrics]:
        """
        Query usage metrics.
        
        Args:
            timeframe: Time range (1h, 24h, 7d, 30d)
            group_by: Field(s) to group by
            **filters: Label filters
            
        Returns:
            Dictionary of grouped metrics
        """
        # Parse timeframe
        hours = self._parse_timeframe(timeframe)
        cutoff = time.time() - (hours * 3600)
        
        # Aggregate metrics
        results: dict[str, UsageMetrics] = defaultdict(UsageMetrics)
        
        with self._lock:
            for key, data in self._metrics.items():
                # Parse labels from key
                labels = dict(kv.split("=") for kv in key.split("|") if "=" in kv)
                
                # Apply filters
                skip = False
                for filter_key, filter_value in filters.items():
                    if labels.get(filter_key) != filter_value:
                        skip = True
                        break
                if skip:
                    continue
                
                # Calculate group key
                if group_by:
                    if isinstance(group_by, str):
                        group_by = [group_by]
                    group_key = "|".join(labels.get(g, "unknown") for g in group_by)
                else:
                    group_key = "total"
                
                # Sum metrics in timeframe
                for timestamp, metrics in data:
                    if timestamp > cutoff:
                        results[group_key] = results[group_key] + metrics
        
        # Calculate latency percentiles
        if self._latencies:
            sorted_latencies = sorted(self._latencies)
            n = len(sorted_latencies)
            for metrics in results.values():
                metrics.p50_latency_ms = sorted_latencies[int(n * 0.5)]
                metrics.p95_latency_ms = sorted_latencies[int(n * 0.95)]
                metrics.p99_latency_ms = sorted_latencies[int(n * 0.99)]
        
        return dict(results)
    
    def _parse_timeframe(self, timeframe: str) -> int:
        """Parse timeframe string to hours."""
        if timeframe.endswith("h"):
            return int(timeframe[:-1])
        elif timeframe.endswith("d"):
            return int(timeframe[:-1]) * 24
        elif timeframe.endswith("w"):
            return int(timeframe[:-1]) * 168
        else:
            return 24  # Default to 24 hours
    
    def get_summary(self) -> dict[str, Any]:
        """Get summary of current metrics."""
        metrics = self.query(timeframe="24h")
        total = sum(metrics.values(), UsageMetrics())
        
        return {
            "total_requests": total.requests,
            "total_characters": total.characters,
            "total_audio_seconds": total.audio_seconds,
            "error_rate": total.errors / max(total.requests, 1),
            "p50_latency_ms": total.p50_latency_ms,
            "p95_latency_ms": total.p95_latency_ms,
            "unique_voices": len(set(
                k.split("|")[0].split("=")[1]
                for k in self._metrics.keys()
                if k.startswith("voice=")
            )),
        }
