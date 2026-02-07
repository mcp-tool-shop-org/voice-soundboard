"""
Tests for v2.3 monitoring module.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch

from voice_soundboard.monitoring import (
    HealthCheck,
    HealthStatus,
    ComponentHealth,
    Counter,
    Gauge,
    Histogram,
    MetricsCollector,
    StructuredLogger,
    LogLevel,
)


class TestHealthCheck:
    """Tests for HealthCheck."""
    
    def test_health_check_creation(self):
        health = HealthCheck()
        assert health is not None
        
    def test_register_component(self):
        health = HealthCheck()
        
        def backend_check():
            return ComponentHealth(
                name="backend",
                status=HealthStatus.HEALTHY,
                message="Backend operational",
            )
        
        health.register("backend", backend_check)
        
        # Check that component is registered
        result = health.check()
        assert "backend" in result.components
        assert result.components["backend"].status == HealthStatus.HEALTHY
        
    def test_overall_health_degraded(self):
        health = HealthCheck()
        
        health.register("healthy", lambda: ComponentHealth(
            name="healthy",
            status=HealthStatus.HEALTHY,
        ))
        health.register("degraded", lambda: ComponentHealth(
            name="degraded",
            status=HealthStatus.DEGRADED,
            message="High latency",
        ))
        
        result = health.check()
        # Overall should be degraded if any component is degraded
        assert result.status == HealthStatus.DEGRADED
        
    def test_overall_health_unhealthy(self):
        health = HealthCheck()
        
        health.register("healthy", lambda: ComponentHealth(
            name="healthy",
            status=HealthStatus.HEALTHY,
        ))
        health.register("unhealthy", lambda: ComponentHealth(
            name="unhealthy",
            status=HealthStatus.UNHEALTHY,
            message="Connection failed",
        ))
        
        result = health.check()
        assert result.status == HealthStatus.UNHEALTHY


class TestCounter:
    """Tests for Counter metric."""
    
    def test_counter_increment(self):
        counter = Counter("requests", "Total requests")
        
        assert counter.value == 0
        
        counter.inc()
        assert counter.value == 1
        
        counter.inc(5)
        assert counter.value == 6
        
    def test_counter_with_labels(self):
        counter = Counter("requests", "Total requests", labels=["method", "status"])
        
        counter.inc(labels={"method": "GET", "status": "200"})
        counter.inc(labels={"method": "POST", "status": "201"})
        counter.inc(labels={"method": "GET", "status": "200"})
        
        # Get value for specific labels
        assert counter.value_for({"method": "GET", "status": "200"}) == 2
        assert counter.value_for({"method": "POST", "status": "201"}) == 1


class TestGauge:
    """Tests for Gauge metric."""
    
    def test_gauge_set(self):
        gauge = Gauge("temperature", "Current temperature")
        
        gauge.set(25.5)
        assert gauge.value == 25.5
        
        gauge.set(30.0)
        assert gauge.value == 30.0
        
    def test_gauge_inc_dec(self):
        gauge = Gauge("connections", "Active connections")
        
        gauge.set(10)
        gauge.inc()
        assert gauge.value == 11
        
        gauge.dec(3)
        assert gauge.value == 8


class TestHistogram:
    """Tests for Histogram metric."""
    
    def test_histogram_observe(self):
        histogram = Histogram(
            "latency",
            "Request latency",
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0],
        )
        
        # Record some observations
        histogram.observe(0.008)  # < 0.01
        histogram.observe(0.03)   # < 0.05
        histogram.observe(0.07)   # < 0.1
        histogram.observe(0.3)    # < 0.5
        histogram.observe(0.8)    # < 1.0
        
        assert histogram.count == 5
        assert histogram.sum == pytest.approx(1.188, rel=0.01)
        
    def test_histogram_percentiles(self):
        histogram = Histogram("response_time", "Response time")
        
        # Add known values
        for i in range(100):
            histogram.observe(i / 100)  # 0.0 to 0.99
        
        # Check percentiles (approximate)
        p50 = histogram.percentile(50)
        p99 = histogram.percentile(99)
        
        assert 0.4 <= p50 <= 0.6
        assert p99 > 0.9


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    def test_create_metrics(self):
        collector = MetricsCollector()
        
        counter = collector.counter("test_counter", "A test counter")
        gauge = collector.gauge("test_gauge", "A test gauge")
        histogram = collector.histogram("test_histogram", "A test histogram")
        
        assert isinstance(counter, Counter)
        assert isinstance(gauge, Gauge)
        assert isinstance(histogram, Histogram)
        
    def test_collect_all(self):
        collector = MetricsCollector()
        
        counter = collector.counter("requests", "Total requests")
        gauge = collector.gauge("active", "Active connections")
        
        counter.inc(10)
        gauge.set(5)
        
        metrics = collector.collect()
        
        assert "requests" in metrics
        assert metrics["requests"]["value"] == 10
        assert "active" in metrics
        assert metrics["active"]["value"] == 5
        
    def test_export_prometheus(self):
        collector = MetricsCollector()
        
        counter = collector.counter("http_requests_total", "Total HTTP requests")
        counter.inc(100)
        
        output = collector.export_prometheus()
        
        assert "http_requests_total" in output
        assert "100" in output


class TestStructuredLogger:
    """Tests for StructuredLogger."""
    
    def test_log_levels(self):
        logger = StructuredLogger("test")
        
        # Should not raise
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
        
    def test_structured_fields(self):
        logger = StructuredLogger("test")
        
        # Capture output
        with patch.object(logger, '_emit') as mock_emit:
            logger.info("User logged in", user_id=123, ip="192.168.1.1")
            
            call_args = mock_emit.call_args
            if call_args:
                entry = call_args[0][0]
                assert entry["user_id"] == 123
                assert entry["ip"] == "192.168.1.1"
                
    def test_log_context(self):
        logger = StructuredLogger("test")
        
        # Add context that persists
        logger.set_context(request_id="abc123")
        
        with patch.object(logger, '_emit') as mock_emit:
            logger.info("Processing")
            
            call_args = mock_emit.call_args
            if call_args:
                entry = call_args[0][0]
                assert entry.get("request_id") == "abc123"
                
    def test_json_output(self):
        logger = StructuredLogger("test", format="json")
        
        with patch.object(logger, '_write') as mock_write:
            logger.info("Test message", key="value")
            
            call_args = mock_write.call_args
            if call_args:
                output = call_args[0][0]
                # Should be valid JSON
                parsed = json.loads(output)
                assert parsed["message"] == "Test message"
                assert parsed["key"] == "value"


class TestLogLevel:
    """Tests for LogLevel enum."""
    
    def test_log_level_ordering(self):
        assert LogLevel.DEBUG.value < LogLevel.INFO.value
        assert LogLevel.INFO.value < LogLevel.WARNING.value
        assert LogLevel.WARNING.value < LogLevel.ERROR.value
        assert LogLevel.ERROR.value < LogLevel.CRITICAL.value
        
    def test_level_filtering(self):
        logger = StructuredLogger("test", level=LogLevel.WARNING)
        
        # Track emissions
        emissions = []
        original_emit = logger._emit
        logger._emit = lambda e: emissions.append(e)
        
        logger.debug("debug")
        logger.info("info")
        logger.warning("warning")
        logger.error("error")
        
        # Only WARNING and above should be emitted
        levels = [e["level"] for e in emissions]
        assert "DEBUG" not in levels
        assert "INFO" not in levels
        assert "WARNING" in levels
        assert "ERROR" in levels
