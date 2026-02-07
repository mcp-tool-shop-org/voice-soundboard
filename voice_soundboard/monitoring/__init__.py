"""
Production Monitoring for Voice Soundboard v2.3.

Provides health checks, structured logging, and observability
for production deployments.

Components:
    HealthCheck     - Health and readiness checks
    MetricsCollector - Prometheus-style metrics
    StructuredLogger - JSON structured logging

Example:
    from voice_soundboard.monitoring import HealthCheck, MetricsCollector
    
    health = HealthCheck(engine)
    status = health.check()
    
    metrics = MetricsCollector()
    metrics.record_latency(150.2)
"""

from voice_soundboard.monitoring.health import (
    HealthCheck,
    HealthStatus,
    ComponentHealth,
)
from voice_soundboard.monitoring.metrics import (
    MetricsCollector,
    Counter,
    Gauge,
    Histogram,
)
from voice_soundboard.monitoring.logging import (
    StructuredLogger,
    LogLevel,
    configure_logging,
)

__all__ = [
    # Health
    "HealthCheck",
    "HealthStatus",
    "ComponentHealth",
    # Metrics
    "MetricsCollector",
    "Counter",
    "Gauge",
    "Histogram",
    # Logging
    "StructuredLogger",
    "LogLevel",
    "configure_logging",
]
