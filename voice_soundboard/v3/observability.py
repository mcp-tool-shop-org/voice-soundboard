"""
v3.1 Observability - Audio Quality Metrics.

Makes audio invariants visible and measurable for production use:
- Loudness (LUFS)
- Clipping detection
- Effect chain timing
- Memory usage
- Prometheus/Grafana integration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol
import time
import json


class MetricType(str, Enum):
    """Type of metric."""
    GAUGE = "gauge"       # Point-in-time value
    COUNTER = "counter"   # Cumulative count
    HISTOGRAM = "histogram"  # Distribution of values


@dataclass
class MetricDefinition:
    """Definition of a metric to collect."""
    name: str
    type: MetricType
    description: str
    unit: str = ""
    labels: list[str] = field(default_factory=list)


# Standard audio metrics
LOUDNESS_LUFS = MetricDefinition(
    name="loudness_lufs",
    type=MetricType.GAUGE,
    description="Integrated loudness in LUFS (ITU-R BS.1770)",
    unit="LUFS",
)

PEAK_DBFS = MetricDefinition(
    name="peak_dbfs",
    type=MetricType.GAUGE,
    description="Peak level in dBFS",
    unit="dBFS",
)

CLIPPING_EVENTS = MetricDefinition(
    name="clipping_events",
    type=MetricType.COUNTER,
    description="Number of clipping events detected",
    unit="count",
)

EFFECT_LATENCY_MS = MetricDefinition(
    name="effect_latency_ms",
    type=MetricType.HISTOGRAM,
    description="Time spent in effect processing",
    unit="ms",
    labels=["effect_name"],
)

RENDER_TIME_MS = MetricDefinition(
    name="render_time_ms",
    type=MetricType.HISTOGRAM,
    description="Total render time",
    unit="ms",
)

MEMORY_BYTES = MetricDefinition(
    name="memory_bytes",
    type=MetricType.GAUGE,
    description="Memory usage of audio graph",
    unit="bytes",
)

TRACK_COUNT = MetricDefinition(
    name="track_count",
    type=MetricType.GAUGE,
    description="Number of active tracks",
    unit="count",
)


@dataclass
class MetricSample:
    """A single metric sample."""
    metric: str
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "metric": self.metric,
            "value": self.value,
            "timestamp": self.timestamp,
            "labels": self.labels,
        }


@dataclass
class MetricsReport:
    """Report of collected metrics."""
    samples: list[MetricSample] = field(default_factory=list)
    
    # Aggregated values
    loudness_lufs: float | None = None
    peak_dbfs: float | None = None
    clipping_events: int = 0
    render_time_ms: float | None = None
    
    # Per-effect timing
    effect_latencies: dict[str, float] = field(default_factory=dict)
    
    def add(self, sample: MetricSample) -> None:
        """Add a metric sample."""
        self.samples.append(sample)
        
        # Update aggregates
        if sample.metric == "loudness_lufs":
            self.loudness_lufs = sample.value
        elif sample.metric == "peak_dbfs":
            self.peak_dbfs = sample.value
        elif sample.metric == "clipping_events":
            self.clipping_events += int(sample.value)
        elif sample.metric == "render_time_ms":
            self.render_time_ms = sample.value
        elif sample.metric == "effect_latency_ms":
            effect_name = sample.labels.get("effect_name", "unknown")
            self.effect_latencies[effect_name] = sample.value
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "loudness_lufs": self.loudness_lufs,
            "peak_dbfs": self.peak_dbfs,
            "clipping_events": self.clipping_events,
            "render_time_ms": self.render_time_ms,
            "effect_latencies": self.effect_latencies,
            "samples": [s.to_dict() for s in self.samples],
        }
    
    def __str__(self) -> str:
        lines = ["Audio Metrics Report:"]
        if self.loudness_lufs is not None:
            lines.append(f"  Loudness: {self.loudness_lufs:.1f} LUFS")
        if self.peak_dbfs is not None:
            lines.append(f"  Peak: {self.peak_dbfs:.1f} dBFS")
        if self.clipping_events > 0:
            lines.append(f"  Clipping: {self.clipping_events} events")
        if self.render_time_ms is not None:
            lines.append(f"  Render time: {self.render_time_ms:.1f} ms")
        if self.effect_latencies:
            lines.append("  Effect latencies:")
            for name, latency in self.effect_latencies.items():
                lines.append(f"    {name}: {latency:.2f} ms")
        return "\n".join(lines)


class AudioMetrics:
    """Metrics collector for AudioGraph.
    
    Samples a percentage of renders and collects audio quality metrics.
    
    Example:
        metrics = AudioMetrics(sample_rate=0.1)  # Sample 10%
        graph.enable_metrics(metrics)
        
        output = graph.render()
        report = metrics.report()
        print(f"Loudness: {report.loudness_lufs} LUFS")
    """
    
    def __init__(
        self,
        sample_rate: float = 1.0,  # 1.0 = 100% sampling
        metrics: list[str] | None = None,
    ):
        self.sample_rate = sample_rate
        self.enabled_metrics = set(metrics or [
            "loudness_lufs",
            "peak_dbfs",
            "clipping_events",
            "render_time_ms",
            "effect_latency_ms",
        ])
        
        self._samples: list[MetricSample] = []
        self._render_count = 0
        self._alerts: list[AlertRule] = []
    
    def should_sample(self) -> bool:
        """Determine if this render should be sampled."""
        import random
        return random.random() < self.sample_rate
    
    def record(self, metric: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a metric value."""
        if metric not in self.enabled_metrics:
            return
        
        sample = MetricSample(
            metric=metric,
            value=value,
            labels=labels or {},
        )
        self._samples.append(sample)
        
        # Check alerts
        for alert in self._alerts:
            alert.check(sample)
    
    def record_render_start(self) -> float:
        """Record the start of a render. Returns start time."""
        return time.perf_counter()
    
    def record_render_end(self, start_time: float) -> None:
        """Record the end of a render."""
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self.record("render_time_ms", elapsed_ms)
        self._render_count += 1
    
    def report(self) -> MetricsReport:
        """Generate a metrics report."""
        report = MetricsReport()
        for sample in self._samples:
            report.add(sample)
        return report
    
    def clear(self) -> None:
        """Clear collected samples."""
        self._samples.clear()
        self._render_count = 0
    
    def set_alert(
        self,
        metric: str,
        threshold: float,
        comparison: str = "gt",  # "gt", "lt", "eq", "gte", "lte"
        action: str | Callable | None = None,
    ) -> None:
        """Set an alert rule for a metric.
        
        Args:
            metric: Metric name to monitor
            threshold: Threshold value
            comparison: Comparison operator
            action: Action to take (URL or callable)
        """
        rule = AlertRule(
            metric=metric,
            threshold=threshold,
            comparison=comparison,
            action=action,
        )
        self._alerts.append(rule)
    
    @property
    def render_count(self) -> int:
        """Number of renders recorded."""
        return self._render_count


@dataclass
class AlertRule:
    """A rule for alerting on metric values."""
    metric: str
    threshold: float
    comparison: str = "gt"
    action: str | Callable | None = None
    
    # State
    triggered: bool = False
    trigger_count: int = 0
    
    def check(self, sample: MetricSample) -> bool:
        """Check if alert should trigger."""
        if sample.metric != self.metric:
            return False
        
        triggered = False
        if self.comparison == "gt" and sample.value > self.threshold:
            triggered = True
        elif self.comparison == "lt" and sample.value < self.threshold:
            triggered = True
        elif self.comparison == "eq" and sample.value == self.threshold:
            triggered = True
        elif self.comparison == "gte" and sample.value >= self.threshold:
            triggered = True
        elif self.comparison == "lte" and sample.value <= self.threshold:
            triggered = True
        
        if triggered:
            self.triggered = True
            self.trigger_count += 1
            self._execute_action(sample)
        
        return triggered
    
    def _execute_action(self, sample: MetricSample) -> None:
        """Execute the alert action."""
        if self.action is None:
            return
        
        if callable(self.action):
            self.action(self, sample)
        elif isinstance(self.action, str):
            # URL-based action (would integrate with notification systems)
            # e.g., "slack://audio-alerts" or "webhook://my-service"
            pass


# ============================================================================
# Exporters
# ============================================================================

class MetricsExporter:
    """Export metrics to monitoring systems.
    
    Supports:
    - Prometheus
    - JSON
    - Console (for debugging)
    """
    
    def __init__(self, backend: str = "console"):
        self.backend = backend
    
    def export(self, report: MetricsReport) -> str | None:
        """Export metrics report."""
        if self.backend == "console":
            return self._export_console(report)
        elif self.backend == "prometheus":
            return self._export_prometheus(report)
        elif self.backend == "json":
            return self._export_json(report)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")
    
    def _export_console(self, report: MetricsReport) -> str:
        """Export to console-friendly format."""
        return str(report)
    
    def _export_prometheus(self, report: MetricsReport) -> str:
        """Export to Prometheus text format."""
        lines = []
        
        for sample in report.samples:
            label_str = ""
            if sample.labels:
                label_pairs = [f'{k}="{v}"' for k, v in sample.labels.items()]
                label_str = "{" + ",".join(label_pairs) + "}"
            
            lines.append(f"voice_soundboard_{sample.metric}{label_str} {sample.value}")
        
        return "\n".join(lines)
    
    def _export_json(self, report: MetricsReport) -> str:
        """Export to JSON format."""
        return json.dumps(report.to_dict(), indent=2)


# ============================================================================
# Grafana Dashboard Templates
# ============================================================================

GRAFANA_DASHBOARD_TEMPLATE = {
    "title": "Voice Soundboard Audio Quality",
    "panels": [
        {
            "title": "Loudness (LUFS)",
            "type": "stat",
            "targets": [{"expr": "voice_soundboard_loudness_lufs"}],
        },
        {
            "title": "Peak Level (dBFS)",
            "type": "gauge",
            "targets": [{"expr": "voice_soundboard_peak_dbfs"}],
        },
        {
            "title": "Clipping Events",
            "type": "stat",
            "targets": [{"expr": "rate(voice_soundboard_clipping_events[5m])"}],
        },
        {
            "title": "Render Time",
            "type": "graph",
            "targets": [
                {"expr": "histogram_quantile(0.99, voice_soundboard_render_time_ms)"}
            ],
        },
        {
            "title": "Effect Latency",
            "type": "heatmap",
            "targets": [{"expr": "voice_soundboard_effect_latency_ms"}],
        },
    ],
}


def get_grafana_dashboard() -> dict:
    """Get the Grafana dashboard template."""
    return GRAFANA_DASHBOARD_TEMPLATE.copy()


# ============================================================================
# Prometheus Alert Rules
# ============================================================================

PROMETHEUS_ALERT_RULES = """
groups:
- name: voice_soundboard_audio_quality
  rules:
  - alert: HighClippingRate
    expr: rate(voice_soundboard_clipping_events[5m]) > 0.1
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: High clipping rate detected
      description: More than 0.1 clipping events per second

  - alert: LoudnessOutOfRange
    expr: abs(voice_soundboard_loudness_lufs + 16) > 3
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: Loudness out of target range
      description: Loudness is more than 3 LUFS from target (-16 LUFS)

  - alert: HighRenderLatency
    expr: histogram_quantile(0.99, voice_soundboard_render_time_ms) > 100
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: High render latency
      description: 99th percentile render time exceeds 100ms
"""


def get_prometheus_alert_rules() -> str:
    """Get Prometheus alert rules."""
    return PROMETHEUS_ALERT_RULES
