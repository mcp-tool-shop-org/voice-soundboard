"""
v3.1 Plugin Interface - Safe Extensibility.

Enables custom DSP and analysis nodes with strict sandbox rules:
- Plugins must not introduce external state
- Plugins must not bypass registrar
- Plugins must not block real-time processing
- Plugins must not access filesystem/network directly

This is the right place for extensibility — not inside DSP core.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol
import time

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore


class PluginCategory(str, Enum):
    """Category of plugin functionality."""
    DSP = "dsp"              # Audio processing
    ANALYSIS = "analysis"    # Audio analysis (non-modifying)
    TRANSFORM = "transform"  # Graph transforms
    UTILITY = "utility"      # Helper plugins


@dataclass
class PluginMetrics:
    """Metrics collected during plugin execution."""
    
    _metrics: dict[str, list[float]] = field(default_factory=dict)
    _tags: dict[str, str] = field(default_factory=dict)
    
    def record(self, name: str, value: float) -> None:
        """Record a metric value."""
        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(value)
    
    def tag(self, name: str, value: str) -> None:
        """Add a tag for grouping."""
        self._tags[name] = value
    
    def get(self, name: str) -> list[float]:
        """Get all recorded values for a metric."""
        return self._metrics.get(name, [])
    
    def get_latest(self, name: str) -> float | None:
        """Get the most recent value for a metric."""
        values = self._metrics.get(name, [])
        return values[-1] if values else None
    
    def get_average(self, name: str) -> float | None:
        """Get the average value for a metric."""
        values = self._metrics.get(name, [])
        return sum(values) / len(values) if values else None
    
    def clear(self) -> None:
        """Clear all recorded metrics."""
        self._metrics.clear()
        self._tags.clear()
    
    def to_dict(self) -> dict:
        """Export metrics as dictionary."""
        return {
            "metrics": {
                name: {
                    "values": values,
                    "count": len(values),
                    "latest": values[-1] if values else None,
                    "average": sum(values) / len(values) if values else None,
                }
                for name, values in self._metrics.items()
            },
            "tags": self._tags.copy(),
        }


@dataclass
class PluginContext:
    """Context provided to plugins during execution.
    
    Provides:
    - Metrics recording
    - Configuration access
    - Safe resource access
    
    Does NOT provide:
    - Filesystem access
    - Network access
    - External state modification
    """
    
    # Metrics collection
    metrics: PluginMetrics = field(default_factory=PluginMetrics)
    
    # Plugin configuration
    config: dict[str, Any] = field(default_factory=dict)
    
    # Sample rate of audio being processed
    sample_rate: int = 24000
    
    # Chunk index (for streaming)
    chunk_index: int = 0
    
    # Timestamp (for logging)
    timestamp: float = field(default_factory=time.time)
    
    # Read-only graph metadata
    graph_metadata: dict[str, Any] = field(default_factory=dict)
    
    def log(self, message: str, level: str = "info") -> None:
        """Log a message (captured for debugging)."""
        # Logs are captured, not printed directly
        if "_logs" not in self.config:
            self.config["_logs"] = []
        self.config["_logs"].append({
            "time": time.time(),
            "level": level,
            "message": message,
        })


class AudioPlugin(ABC):
    """Base class for audio plugins.
    
    Subclass this to create custom DSP or analysis plugins.
    All plugins must:
    1. Declare their name and category
    2. Declare whether they have external state
    3. Implement the process() method
    
    Example:
        class LoudnessAnalyzer(AudioPlugin):
            name = "loudness_analyzer"
            category = PluginCategory.ANALYSIS
            
            def process(self, samples, ctx):
                lufs = self._calculate_lufs(samples)
                ctx.metrics.record("lufs", lufs)
                return samples  # Analysis plugins pass through
            
            @property
            def has_external_state(self):
                return False
    """
    
    # Plugin identity (must be set by subclass)
    name: str = "unnamed_plugin"
    category: PluginCategory = PluginCategory.UTILITY
    
    # Description for documentation
    description: str = ""
    
    # Version
    version: str = "1.0.0"
    
    @property
    @abstractmethod
    def has_external_state(self) -> bool:
        """Declare if plugin maintains external state.
        
        Plugins with external state are FORBIDDEN.
        This declaration is verified during registration.
        """
        ...
    
    @abstractmethod
    def process(self, samples: Any, ctx: PluginContext) -> Any:
        """Process audio samples.
        
        Args:
            samples: Audio samples (numpy array or similar)
            ctx: Plugin context for metrics and config
        
        Returns:
            Processed samples (same shape as input)
        
        For analysis plugins, return samples unchanged.
        For DSP plugins, return modified samples.
        """
        ...
    
    def validate(self) -> list[str]:
        """Validate plugin configuration.
        
        Returns list of issues (empty = valid).
        Override to add custom validation.
        """
        issues = []
        
        if not self.name or self.name == "unnamed_plugin":
            issues.append("Plugin name not set")
        
        if self.has_external_state:
            issues.append("Plugins with external state are forbidden")
        
        return issues
    
    def reset(self) -> None:
        """Reset any internal state.
        
        Called between processing sessions.
        Override if plugin has internal buffers.
        """
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, category={self.category.value})"


class DSPPlugin(AudioPlugin):
    """Base class for DSP (audio modifying) plugins.
    
    DSP plugins modify the audio signal. They must be:
    - Deterministic (same input = same output)
    - Real-time safe (no blocking operations)
    - Stateless or with reset capability
    """
    
    category = PluginCategory.DSP
    
    @property
    def has_external_state(self) -> bool:
        """DSP plugins should not have external state."""
        return False


class AnalysisPlugin(AudioPlugin):
    """Base class for analysis (non-modifying) plugins.
    
    Analysis plugins measure audio properties without modifying
    the signal. They must pass samples through unchanged.
    """
    
    category = PluginCategory.ANALYSIS
    
    @property
    def has_external_state(self) -> bool:
        """Analysis plugins should not have external state."""
        return False
    
    @abstractmethod
    def process(self, samples: Any, ctx: PluginContext) -> Any:
        """Analyze samples and return unchanged.
        
        Record measurements via ctx.metrics.record().
        """
        ...


class GraphTransformPlugin(ABC):
    """Base class for graph transform plugins.
    
    Transform plugins modify the AudioGraph structure itself,
    not the audio data. Use for automated graph optimization,
    effect chain insertion, etc.
    """
    
    name: str = "unnamed_transform"
    description: str = ""
    
    @abstractmethod
    def transform(self, graph: Any) -> Any:
        """Transform the graph and return modified version.
        
        Args:
            graph: AudioGraph to transform
        
        Returns:
            Modified AudioGraph
        
        Transforms should be idempotent when possible.
        """
        ...
    
    def validate(self, graph: Any) -> list[str]:
        """Validate that transform can be applied.
        
        Returns list of issues (empty = can apply).
        """
        return []


# ============================================================================
# Built-in Plugins
# ============================================================================

class LoudnessAnalyzer(AnalysisPlugin):
    """Measures loudness in LUFS (Loudness Units Full Scale)."""
    
    name = "loudness_analyzer"
    description = "Measures integrated loudness in LUFS"
    
    def process(self, samples: Any, ctx: PluginContext) -> Any:
        """Analyze loudness and record to metrics."""
        if np is None:
            ctx.log("numpy not available, skipping loudness analysis", "warning")
            return samples
        
        if len(samples) == 0:
            return samples
        
        # Simplified LUFS calculation (reference implementation)
        # Real implementation would use ITU-R BS.1770-4
        rms = float(np.sqrt(np.mean(samples ** 2)))
        lufs_approx = 20 * np.log10(rms + 1e-10) - 0.691
        
        ctx.metrics.record("lufs", lufs_approx)
        ctx.metrics.record("rms", rms)
        
        return samples  # Pass through unchanged


class PeakDetector(AnalysisPlugin):
    """Detects peak levels and clipping."""
    
    name = "peak_detector"
    description = "Detects peak levels and counts clipping events"
    
    def __init__(self, threshold: float = 0.99):
        self.threshold = threshold
    
    def process(self, samples: Any, ctx: PluginContext) -> Any:
        """Analyze peaks and clipping."""
        if np is None:
            return samples
        
        if len(samples) == 0:
            return samples
        
        peak = float(np.max(np.abs(samples)))
        peak_db = 20 * np.log10(peak + 1e-10)
        clipping = int(np.sum(np.abs(samples) >= self.threshold))
        
        ctx.metrics.record("peak", peak)
        ctx.metrics.record("peak_db", peak_db)
        ctx.metrics.record("clipping_samples", float(clipping))
        
        if clipping > 0:
            ctx.log(f"Clipping detected: {clipping} samples", "warning")
        
        return samples


class SilenceDetector(AnalysisPlugin):
    """Detects silence in audio."""
    
    name = "silence_detector"
    description = "Detects silence regions in audio"
    
    def __init__(self, threshold_db: float = -60.0):
        self.threshold_db = threshold_db
        self._threshold_linear = 10 ** (threshold_db / 20)
    
    def process(self, samples: Any, ctx: PluginContext) -> Any:
        """Detect silence."""
        if np is None:
            return samples
        
        if len(samples) == 0:
            return samples
        
        rms = float(np.sqrt(np.mean(samples ** 2)))
        is_silence = rms < self._threshold_linear
        silence_ratio = float(np.mean(np.abs(samples) < self._threshold_linear))
        
        ctx.metrics.record("is_silence", float(is_silence))
        ctx.metrics.record("silence_ratio", silence_ratio)
        
        return samples


class LatencyMeasurer(AnalysisPlugin):
    """Measures processing latency."""
    
    name = "latency_measurer"
    description = "Measures time spent in audio processing"
    
    def process(self, samples: Any, ctx: PluginContext) -> Any:
        """Measure and record processing time."""
        start = time.perf_counter()
        
        # This plugin just measures the overhead of measurement itself
        # In real use, it would wrap other processing
        
        elapsed_ms = (time.perf_counter() - start) * 1000
        ctx.metrics.record("latency_ms", elapsed_ms)
        
        return samples


# ============================================================================
# Plugin Registry
# ============================================================================

class PluginRegistry:
    """Central registry for plugins.
    
    Validates and stores plugins, ensuring sandbox compliance.
    """
    
    def __init__(self):
        self._plugins: dict[str, AudioPlugin] = {}
        self._transforms: dict[str, GraphTransformPlugin] = {}
    
    def register(self, plugin: AudioPlugin) -> None:
        """Register a plugin after validation."""
        issues = plugin.validate()
        if issues:
            raise PluginValidationError(plugin.name, issues)
        
        if plugin.has_external_state:
            raise PluginSandboxViolation(
                plugin.name,
                "Plugins with external state are forbidden"
            )
        
        self._plugins[plugin.name] = plugin
    
    def register_transform(self, transform: GraphTransformPlugin) -> None:
        """Register a graph transform plugin."""
        self._transforms[transform.name] = transform
    
    def get(self, name: str) -> AudioPlugin | None:
        """Get plugin by name."""
        return self._plugins.get(name)
    
    def get_transform(self, name: str) -> GraphTransformPlugin | None:
        """Get transform by name."""
        return self._transforms.get(name)
    
    def list_plugins(self) -> list[str]:
        """List all registered plugin names."""
        return list(self._plugins.keys())
    
    def list_by_category(self, category: PluginCategory) -> list[str]:
        """List plugins of a specific category."""
        return [
            name for name, plugin in self._plugins.items()
            if plugin.category == category
        ]


class PluginValidationError(Exception):
    """Raised when plugin validation fails."""
    
    def __init__(self, plugin_name: str, issues: list[str]):
        self.plugin_name = plugin_name
        self.issues = issues
        super().__init__(f"Plugin '{plugin_name}' validation failed: {issues}")


class PluginSandboxViolation(Exception):
    """Raised when a plugin violates sandbox rules."""
    
    def __init__(self, plugin_name: str, violation: str):
        self.plugin_name = plugin_name
        self.violation = violation
        super().__init__(f"Plugin '{plugin_name}' sandbox violation: {violation}")
