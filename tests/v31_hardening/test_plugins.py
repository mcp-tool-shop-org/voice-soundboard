"""
v3.1 Hardening Tests - Plugin Interface.

Tests for the plugin system ensuring:
- Plugins comply with sandbox rules
- External state is forbidden
- Plugin validation works
- Built-in plugins function correctly
"""

import pytest
from unittest.mock import MagicMock, patch
import time

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

from voice_soundboard.v3.plugins import (
    AudioPlugin,
    DSPPlugin,
    AnalysisPlugin,
    GraphTransformPlugin,
    PluginContext,
    PluginMetrics,
    PluginCategory,
    PluginRegistry,
    PluginValidationError,
    PluginSandboxViolation,
    LoudnessAnalyzer,
    PeakDetector,
    SilenceDetector,
    LatencyMeasurer,
)


class TestPluginContext:
    """Tests for PluginContext."""
    
    def test_context_creation(self):
        """Context should initialize with defaults."""
        ctx = PluginContext()
        
        assert ctx.sample_rate == 24000
        assert ctx.chunk_index == 0
        assert isinstance(ctx.metrics, PluginMetrics)
    
    def test_context_metrics_recording(self):
        """Context should allow metrics recording."""
        ctx = PluginContext()
        
        ctx.metrics.record("lufs", -16.0)
        ctx.metrics.record("lufs", -15.5)
        
        values = ctx.metrics.get("lufs")
        assert len(values) == 2
        assert values[0] == -16.0
    
    def test_context_logging(self):
        """Context should capture logs."""
        ctx = PluginContext()
        
        ctx.log("Test message", "info")
        ctx.log("Warning!", "warning")
        
        logs = ctx.config.get("_logs", [])
        assert len(logs) == 2
        assert logs[0]["message"] == "Test message"
        assert logs[1]["level"] == "warning"


class TestPluginMetrics:
    """Tests for PluginMetrics."""
    
    def test_record_and_get(self):
        """Should record and retrieve metrics."""
        metrics = PluginMetrics()
        
        metrics.record("test", 1.0)
        metrics.record("test", 2.0)
        metrics.record("test", 3.0)
        
        values = metrics.get("test")
        assert values == [1.0, 2.0, 3.0]
    
    def test_get_latest(self):
        """Should get latest value."""
        metrics = PluginMetrics()
        
        metrics.record("metric", 10)
        metrics.record("metric", 20)
        metrics.record("metric", 30)
        
        assert metrics.get_latest("metric") == 30
    
    def test_get_average(self):
        """Should calculate average."""
        metrics = PluginMetrics()
        
        metrics.record("avg_test", 10)
        metrics.record("avg_test", 20)
        metrics.record("avg_test", 30)
        
        assert metrics.get_average("avg_test") == 20.0
    
    def test_tags(self):
        """Should store tags."""
        metrics = PluginMetrics()
        
        metrics.tag("effect", "compressor")
        metrics.tag("track", "dialogue")
        
        data = metrics.to_dict()
        assert data["tags"]["effect"] == "compressor"
    
    def test_clear(self):
        """Should clear all data."""
        metrics = PluginMetrics()
        metrics.record("test", 1)
        metrics.tag("key", "value")
        
        metrics.clear()
        
        assert metrics.get("test") == []
        assert metrics.to_dict()["tags"] == {}
    
    def test_empty_metric_returns_none(self):
        """Should return None for empty metrics."""
        metrics = PluginMetrics()
        
        assert metrics.get_latest("nonexistent") is None
        assert metrics.get_average("nonexistent") is None


class TestAudioPluginBase:
    """Tests for AudioPlugin base class."""
    
    def test_plugin_must_declare_external_state(self):
        """Plugin must implement has_external_state."""
        
        # This should raise because abstract method not implemented
        class IncompletePlugin(AudioPlugin):
            def process(self, samples, ctx):
                return samples
        
        with pytest.raises(TypeError):
            IncompletePlugin()
    
    def test_plugin_with_external_state_fails_validation(self):
        """Plugin with external state should fail validation."""
        
        class BadPlugin(AudioPlugin):
            name = "bad_plugin"
            
            @property
            def has_external_state(self):
                return True  # Forbidden!
            
            def process(self, samples, ctx):
                return samples
        
        plugin = BadPlugin()
        issues = plugin.validate()
        
        assert len(issues) > 0
        assert any("external state" in issue.lower() for issue in issues)
    
    def test_unnamed_plugin_fails_validation(self):
        """Plugin without name should fail validation."""
        
        class UnnamedPlugin(AudioPlugin):
            # name = "unnamed_plugin" (default)
            
            @property
            def has_external_state(self):
                return False
            
            def process(self, samples, ctx):
                return samples
        
        plugin = UnnamedPlugin()
        issues = plugin.validate()
        
        assert any("name" in issue.lower() for issue in issues)
    
    def test_valid_plugin_passes_validation(self):
        """Well-formed plugin should pass validation."""
        
        class GoodPlugin(AudioPlugin):
            name = "good_plugin"
            category = PluginCategory.DSP
            
            @property
            def has_external_state(self):
                return False
            
            def process(self, samples, ctx):
                return samples
        
        plugin = GoodPlugin()
        issues = plugin.validate()
        
        assert len(issues) == 0


class TestPluginRegistry:
    """Tests for PluginRegistry."""
    
    def test_register_valid_plugin(self):
        """Should register valid plugins."""
        registry = PluginRegistry()
        
        class ValidPlugin(AudioPlugin):
            name = "valid_plugin"
            
            @property
            def has_external_state(self):
                return False
            
            def process(self, samples, ctx):
                return samples
        
        plugin = ValidPlugin()
        registry.register(plugin)
        
        assert "valid_plugin" in registry.list_plugins()
        assert registry.get("valid_plugin") == plugin
    
    def test_register_invalid_plugin_raises(self):
        """Should reject plugins that fail validation."""
        registry = PluginRegistry()
        
        class InvalidPlugin(AudioPlugin):
            name = ""  # Invalid: empty name
            
            @property
            def has_external_state(self):
                return False
            
            def process(self, samples, ctx):
                return samples
        
        InvalidPlugin.name = ""  # Ensure empty
        
        with pytest.raises(PluginValidationError):
            # Need to work around the validation
            plugin = InvalidPlugin()
            plugin.name = ""  # Force empty after creation
            registry.register(plugin)
    
    def test_register_external_state_plugin_raises(self):
        """Should reject plugins with external state."""
        registry = PluginRegistry()
        
        class ExternalStatePlugin(AudioPlugin):
            name = "external_state"
            
            @property
            def has_external_state(self):
                return True
            
            def process(self, samples, ctx):
                return samples
        
        with pytest.raises(PluginSandboxViolation):
            registry.register(ExternalStatePlugin())
    
    def test_list_by_category(self):
        """Should filter plugins by category."""
        registry = PluginRegistry()
        
        class DSPPlugin1(AudioPlugin):
            name = "dsp1"
            category = PluginCategory.DSP
            
            @property
            def has_external_state(self):
                return False
            
            def process(self, samples, ctx):
                return samples
        
        class AnalysisPlugin1(AudioPlugin):
            name = "analysis1"
            category = PluginCategory.ANALYSIS
            
            @property
            def has_external_state(self):
                return False
            
            def process(self, samples, ctx):
                return samples
        
        registry.register(DSPPlugin1())
        registry.register(AnalysisPlugin1())
        
        dsp_plugins = registry.list_by_category(PluginCategory.DSP)
        analysis_plugins = registry.list_by_category(PluginCategory.ANALYSIS)
        
        assert "dsp1" in dsp_plugins
        assert "analysis1" in analysis_plugins
        assert "analysis1" not in dsp_plugins


@pytest.mark.skipif(not HAS_NUMPY, reason="numpy required")
class TestBuiltinPlugins:
    """Tests for built-in plugin implementations."""
    
    def test_loudness_analyzer_records_metrics(self):
        """LoudnessAnalyzer should record LUFS."""
        analyzer = LoudnessAnalyzer()
        ctx = PluginContext()
        
        # Create test audio (1 second of -20dBFS sine)
        samples = np.sin(np.linspace(0, 2 * np.pi * 440, 24000)) * 0.1
        
        output = analyzer.process(samples, ctx)
        
        # Should pass through unchanged
        assert np.array_equal(output, samples)
        
        # Should record metrics
        assert ctx.metrics.get_latest("lufs") is not None
        assert ctx.metrics.get_latest("rms") is not None
    
    def test_peak_detector_finds_peaks(self):
        """PeakDetector should find peak levels."""
        detector = PeakDetector()
        ctx = PluginContext()
        
        # Audio with known peak
        samples = np.zeros(1000)
        samples[500] = 0.9  # Peak at 0.9
        
        output = detector.process(samples, ctx)
        
        assert np.array_equal(output, samples)
        assert ctx.metrics.get_latest("peak") == pytest.approx(0.9, abs=0.01)
    
    def test_peak_detector_counts_clipping(self):
        """PeakDetector should count clipping samples."""
        detector = PeakDetector(threshold=0.95)
        ctx = PluginContext()
        
        # Audio with clipping
        samples = np.array([0.5, 0.96, 0.97, 0.98, 0.5])  # 3 clipping samples
        
        detector.process(samples, ctx)
        
        assert ctx.metrics.get_latest("clipping_samples") == 3
    
    def test_silence_detector_finds_silence(self):
        """SilenceDetector should detect silence."""
        detector = SilenceDetector(threshold_db=-50)
        ctx = PluginContext()
        
        # Very quiet audio
        samples = np.random.randn(1000) * 0.00001  # ~-100dB
        
        detector.process(samples, ctx)
        
        assert ctx.metrics.get_latest("is_silence") == 1.0
    
    def test_silence_detector_finds_audio(self):
        """SilenceDetector should detect non-silence."""
        detector = SilenceDetector(threshold_db=-50)
        ctx = PluginContext()
        
        # Normal audio
        samples = np.sin(np.linspace(0, 2 * np.pi * 440, 1000)) * 0.5
        
        detector.process(samples, ctx)
        
        assert ctx.metrics.get_latest("is_silence") == 0.0
    
    def test_latency_measurer_records_time(self):
        """LatencyMeasurer should record processing time."""
        measurer = LatencyMeasurer()
        ctx = PluginContext()
        
        samples = np.zeros(1000)
        
        measurer.process(samples, ctx)
        
        latency = ctx.metrics.get_latest("latency_ms")
        assert latency is not None
        assert latency >= 0


class TestAnalysisPluginBase:
    """Tests for AnalysisPlugin base class."""
    
    def test_analysis_plugin_should_not_modify(self):
        """Analysis plugins should pass through unchanged."""
        
        class CounterAnalyzer(AnalysisPlugin):
            name = "counter"
            
            def process(self, samples, ctx):
                ctx.metrics.record("count", len(samples))
                return samples  # Must return unchanged
        
        analyzer = CounterAnalyzer()
        ctx = PluginContext()
        
        if HAS_NUMPY:
            original = np.array([1, 2, 3, 4, 5])
            output = analyzer.process(original, ctx)
            assert np.array_equal(output, original)
        else:
            original = [1, 2, 3, 4, 5]
            output = analyzer.process(original, ctx)
            assert output == original


class TestDSPPluginBase:
    """Tests for DSPPlugin base class."""
    
    def test_dsp_plugin_no_external_state(self):
        """DSPPlugin should declare no external state."""
        
        class SimpleDSP(DSPPlugin):
            name = "simple_dsp"
            
            def process(self, samples, ctx):
                return samples * 0.5  # Halve volume
        
        dsp = SimpleDSP()
        assert dsp.has_external_state is False


class TestPluginReset:
    """Tests for plugin reset functionality."""
    
    def test_reset_clears_internal_state(self):
        """Reset should clear any internal buffers."""
        
        class BufferedPlugin(AudioPlugin):
            name = "buffered"
            
            def __init__(self):
                self._buffer = []
            
            @property
            def has_external_state(self):
                return False  # Internal buffer is OK
            
            def process(self, samples, ctx):
                self._buffer.append(samples)
                return samples
            
            def reset(self):
                self._buffer.clear()
        
        plugin = BufferedPlugin()
        ctx = PluginContext()
        
        if HAS_NUMPY:
            plugin.process(np.array([1, 2, 3]), ctx)
        else:
            plugin.process([1, 2, 3], ctx)
        
        assert len(plugin._buffer) == 1
        
        plugin.reset()
        
        assert len(plugin._buffer) == 0


class TestPluginPerformance:
    """Performance tests for plugins."""
    
    @pytest.mark.skipif(not HAS_NUMPY, reason="numpy required")
    def test_loudness_analyzer_performance(self):
        """LoudnessAnalyzer should be fast enough for real-time."""
        analyzer = LoudnessAnalyzer()
        ctx = PluginContext()
        
        # 1 second of audio at 48kHz
        samples = np.random.randn(48000) * 0.1
        
        # Process 100 chunks
        start = time.perf_counter()
        for _ in range(100):
            analyzer.process(samples, ctx)
        elapsed = time.perf_counter() - start
        
        per_call_ms = (elapsed / 100) * 1000
        
        # Should take less than 10ms per call for real-time viability
        assert per_call_ms < 10, f"Analysis took {per_call_ms:.2f}ms"
    
    @pytest.mark.skipif(not HAS_NUMPY, reason="numpy required")
    def test_peak_detector_performance(self):
        """PeakDetector should be fast."""
        detector = PeakDetector()
        ctx = PluginContext()
        
        samples = np.random.randn(48000)
        
        start = time.perf_counter()
        for _ in range(100):
            detector.process(samples, ctx)
        elapsed = time.perf_counter() - start
        
        per_call_ms = (elapsed / 100) * 1000
        assert per_call_ms < 5, f"Peak detection took {per_call_ms:.2f}ms"
