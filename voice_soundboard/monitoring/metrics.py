"""
Metrics collection for Voice Soundboard.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator
from collections import deque
import statistics


@dataclass
class MetricValue:
    """A single metric value."""
    
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)


class Counter:
    """Counter metric (monotonically increasing).
    
    Example:
        requests = Counter("requests_total", "Total requests processed")
        requests.inc()
        requests.inc(5)
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ):
        self.name = name
        self.description = description
        self._labels = labels or []
        self._values: dict[tuple, float] = {}
        self._lock = threading.Lock()
    
    def inc(self, value: float = 1, **labels: str) -> None:
        """Increment the counter.
        
        Args:
            value: Amount to increment by.
            **labels: Label values.
        """
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0) + value
    
    def get(self, **labels: str) -> float:
        """Get current counter value.
        
        Args:
            **labels: Label values.
        
        Returns:
            Current counter value.
        """
        key = tuple(sorted(labels.items()))
        return self._values.get(key, 0)
    
    def values(self) -> Iterator[tuple[dict[str, str], float]]:
        """Iterate over all values with labels."""
        with self._lock:
            for key, value in self._values.items():
                yield dict(key), value


class Gauge:
    """Gauge metric (can go up or down).
    
    Example:
        queue_depth = Gauge("queue_depth", "Current queue depth")
        queue_depth.set(5)
        queue_depth.inc()
        queue_depth.dec()
    """
    
    def __init__(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ):
        self.name = name
        self.description = description
        self._labels = labels or []
        self._values: dict[tuple, float] = {}
        self._lock = threading.Lock()
    
    def set(self, value: float, **labels: str) -> None:
        """Set the gauge value."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = value
    
    def inc(self, value: float = 1, **labels: str) -> None:
        """Increment the gauge."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0) + value
    
    def dec(self, value: float = 1, **labels: str) -> None:
        """Decrement the gauge."""
        key = tuple(sorted(labels.items()))
        with self._lock:
            self._values[key] = self._values.get(key, 0) - value
    
    def get(self, **labels: str) -> float:
        """Get current gauge value."""
        key = tuple(sorted(labels.items()))
        return self._values.get(key, 0)
    
    def values(self) -> Iterator[tuple[dict[str, str], float]]:
        """Iterate over all values with labels."""
        with self._lock:
            for key, value in self._values.items():
                yield dict(key), value


class Histogram:
    """Histogram metric for measuring distributions.
    
    Example:
        latency = Histogram(
            "synthesis_latency_ms",
            "Synthesis latency in milliseconds",
            buckets=[10, 50, 100, 200, 500, 1000]
        )
        latency.observe(145.2)
    """
    
    DEFAULT_BUCKETS = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
    
    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: list[float] | None = None,
        labels: list[str] | None = None,
    ):
        self.name = name
        self.description = description
        self._buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self._labels = labels or []
        
        # Per-label data
        self._counts: dict[tuple, list[int]] = {}
        self._sums: dict[tuple, float] = {}
        self._totals: dict[tuple, int] = {}
        self._samples: dict[tuple, deque] = {}
        
        self._lock = threading.Lock()
    
    def observe(self, value: float, **labels: str) -> None:
        """Record an observation.
        
        Args:
            value: Value to observe.
            **labels: Label values.
        """
        key = tuple(sorted(labels.items()))
        
        with self._lock:
            # Initialize if needed
            if key not in self._counts:
                self._counts[key] = [0] * len(self._buckets)
                self._sums[key] = 0
                self._totals[key] = 0
                self._samples[key] = deque(maxlen=1000)
            
            # Update buckets
            for i, bucket in enumerate(self._buckets):
                if value <= bucket:
                    self._counts[key][i] += 1
            
            self._sums[key] += value
            self._totals[key] += 1
            self._samples[key].append(value)
    
    def get_stats(self, **labels: str) -> dict[str, float]:
        """Get histogram statistics.
        
        Returns:
            Dictionary with count, sum, mean, p50, p95, p99.
        """
        key = tuple(sorted(labels.items()))
        
        with self._lock:
            if key not in self._totals or self._totals[key] == 0:
                return {
                    "count": 0,
                    "sum": 0,
                    "mean": 0,
                    "p50": 0,
                    "p95": 0,
                    "p99": 0,
                }
            
            samples = list(self._samples[key])
            sorted_samples = sorted(samples)
            n = len(sorted_samples)
            
            return {
                "count": self._totals[key],
                "sum": self._sums[key],
                "mean": self._sums[key] / self._totals[key],
                "p50": sorted_samples[int(n * 0.5)] if n else 0,
                "p95": sorted_samples[int(n * 0.95)] if n else 0,
                "p99": sorted_samples[int(n * 0.99)] if n else 0,
            }
    
    def get_buckets(self, **labels: str) -> list[tuple[float, int]]:
        """Get bucket counts.
        
        Returns:
            List of (bucket_boundary, count) tuples.
        """
        key = tuple(sorted(labels.items()))
        
        with self._lock:
            counts = self._counts.get(key, [0] * len(self._buckets))
            return list(zip(self._buckets, counts))


class MetricsCollector:
    """Central metrics collection for Voice Soundboard.
    
    Provides Prometheus-style metrics for monitoring:
    - Counters (requests, errors, etc.)
    - Gauges (queue depth, memory, etc.)
    - Histograms (latency distributions)
    
    Example:
        metrics = MetricsCollector()
        
        # Record metrics
        metrics.record_synthesis(latency_ms=145.2, backend="kokoro")
        metrics.record_error("timeout")
        
        # Get all metrics
        report = metrics.get_report()
        
        # Prometheus export
        prometheus_text = metrics.export_prometheus()
    """
    
    def __init__(self):
        # Built-in metrics
        self.synthesis_count = Counter(
            "voice_soundboard_synthesis_total",
            "Total synthesis requests",
            labels=["backend", "voice"],
        )
        
        self.synthesis_latency = Histogram(
            "voice_soundboard_synthesis_duration_ms",
            "Synthesis duration in milliseconds",
            buckets=[10, 25, 50, 100, 150, 200, 300, 500, 1000, 2000],
            labels=["backend"],
        )
        
        self.errors = Counter(
            "voice_soundboard_errors_total",
            "Total errors",
            labels=["type"],
        )
        
        self.queue_depth = Gauge(
            "voice_soundboard_queue_depth",
            "Current queue depth",
        )
        
        self.buffer_fill = Gauge(
            "voice_soundboard_buffer_fill_ratio",
            "Buffer fill ratio (0-1)",
        )
        
        self.memory_usage = Gauge(
            "voice_soundboard_memory_mb",
            "Memory usage in MB",
        )
        
        # Custom metrics
        self._custom_metrics: dict[str, Counter | Gauge | Histogram] = {}
        self._lock = threading.Lock()
    
    def record_synthesis(
        self,
        latency_ms: float,
        backend: str = "unknown",
        voice: str = "unknown",
    ) -> None:
        """Record a synthesis operation.
        
        Args:
            latency_ms: Synthesis duration in milliseconds.
            backend: Backend name.
            voice: Voice identifier.
        """
        self.synthesis_count.inc(backend=backend, voice=voice)
        self.synthesis_latency.observe(latency_ms, backend=backend)
    
    def record_error(self, error_type: str) -> None:
        """Record an error.
        
        Args:
            error_type: Type/category of error.
        """
        self.errors.inc(type=error_type)
    
    def record_latency(self, latency_ms: float, backend: str = "default") -> None:
        """Record synthesis latency.
        
        Args:
            latency_ms: Latency in milliseconds.
            backend: Backend name.
        """
        self.synthesis_latency.observe(latency_ms, backend=backend)
    
    def set_queue_depth(self, depth: int) -> None:
        """Set current queue depth.
        
        Args:
            depth: Queue depth.
        """
        self.queue_depth.set(depth)
    
    def set_buffer_fill(self, fill_ratio: float) -> None:
        """Set buffer fill ratio.
        
        Args:
            fill_ratio: Fill ratio (0-1).
        """
        self.buffer_fill.set(fill_ratio)
    
    def update_memory(self) -> None:
        """Update memory usage metric."""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            self.memory_usage.set(memory_mb)
        except ImportError:
            pass
    
    def register_counter(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Counter:
        """Register a custom counter metric."""
        counter = Counter(name, description, labels)
        with self._lock:
            self._custom_metrics[name] = counter
        return counter
    
    def register_gauge(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Gauge:
        """Register a custom gauge metric."""
        gauge = Gauge(name, description, labels)
        with self._lock:
            self._custom_metrics[name] = gauge
        return gauge
    
    def register_histogram(
        self,
        name: str,
        description: str = "",
        buckets: list[float] | None = None,
        labels: list[str] | None = None,
    ) -> Histogram:
        """Register a custom histogram metric."""
        histogram = Histogram(name, description, buckets, labels)
        with self._lock:
            self._custom_metrics[name] = histogram
        return histogram
    
    def get_report(self) -> dict[str, Any]:
        """Get a complete metrics report.
        
        Returns:
            Dictionary with all metrics data.
        """
        self.update_memory()
        
        return {
            "synthesis": {
                "total": sum(v for _, v in self.synthesis_count.values()),
                "latency": self.synthesis_latency.get_stats(),
            },
            "errors": {
                "total": sum(v for _, v in self.errors.values()),
                "by_type": dict(self.errors.values()),
            },
            "queue_depth": self.queue_depth.get(),
            "buffer_fill": self.buffer_fill.get(),
            "memory_mb": self.memory_usage.get(),
            "custom": {
                name: self._get_metric_value(metric)
                for name, metric in self._custom_metrics.items()
            },
        }
    
    def _get_metric_value(self, metric: Counter | Gauge | Histogram) -> Any:
        """Get value from a metric."""
        if isinstance(metric, Histogram):
            return metric.get_stats()
        return dict(metric.values())
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format.
        
        Returns:
            Prometheus-formatted metrics string.
        """
        lines = []
        
        def format_metric(name, description, metric_type, values):
            lines.append(f"# HELP {name} {description}")
            lines.append(f"# TYPE {name} {metric_type}")
            for labels, value in values:
                if labels:
                    label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                    lines.append(f"{name}{{{label_str}}} {value}")
                else:
                    lines.append(f"{name} {value}")
        
        # Export built-in metrics
        format_metric(
            self.synthesis_count.name,
            self.synthesis_count.description,
            "counter",
            self.synthesis_count.values(),
        )
        
        format_metric(
            self.errors.name,
            self.errors.description,
            "counter",
            self.errors.values(),
        )
        
        format_metric(
            self.queue_depth.name,
            self.queue_depth.description,
            "gauge",
            [({}, self.queue_depth.get())],
        )
        
        # Histogram export
        name = self.synthesis_latency.name
        lines.append(f"# HELP {name} {self.synthesis_latency.description}")
        lines.append(f"# TYPE {name} histogram")
        
        for labels, bucket, count in self._iter_histogram_buckets(self.synthesis_latency):
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            le_label = f'le="{bucket}"'
            if label_str:
                lines.append(f'{name}_bucket{{{label_str},{le_label}}} {count}')
            else:
                lines.append(f'{name}_bucket{{{le_label}}} {count}')
        
        return "\n".join(lines)
    
    def _iter_histogram_buckets(self, histogram: Histogram):
        """Iterate over histogram buckets for export."""
        # Get all label combinations
        for key in histogram._counts:
            labels = dict(key)
            for bucket, count in histogram.get_buckets(**labels):
                yield labels, bucket, count
