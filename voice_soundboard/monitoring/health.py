"""
Health checks for Voice Soundboard.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class HealthStatus(Enum):
    """Health status values."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component.
    
    Attributes:
        name: Component identifier.
        status: Health status.
        message: Optional status message.
        latency_ms: Response latency.
        metadata: Additional component data.
    """
    
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class HealthCheck:
    """Health and readiness checks for production deployments.
    
    Provides:
    - Liveness checks (is the service running?)
    - Readiness checks (can the service handle requests?)
    - Component-level health status
    - Aggregated health reporting
    
    Example:
        health = HealthCheck(engine)
        
        # Simple health check
        status = health.check()
        print(status)
        # {
        #   "status": "healthy",
        #   "backend": "kokoro",
        #   "model_loaded": True,
        #   "memory_mb": 312,
        #   "queue_depth": 3
        # }
        
        # Detailed component health
        components = health.check_components()
        for comp in components:
            print(f"{comp.name}: {comp.status.value}")
    """
    
    def __init__(
        self,
        engine: Any = None,
        check_interval: float = 5.0,
    ):
        """Initialize health checker.
        
        Args:
            engine: VoiceEngine instance to monitor.
            check_interval: Seconds between background checks.
        """
        self._engine = engine
        self._check_interval = check_interval
        
        # Custom health checkers
        self._checkers: dict[str, Callable[[], ComponentHealth]] = {}
        
        # Cached health status
        self._last_check: dict[str, Any] | None = None
        self._last_check_time: float = 0
        
        # Background monitoring
        self._background_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
    
    def register_checker(
        self,
        name: str,
        checker: Callable[[], ComponentHealth],
    ) -> None:
        """Register a custom health checker.
        
        Args:
            name: Component name.
            checker: Function that returns ComponentHealth.
        """
        self._checkers[name] = checker
    
    def check(self, force: bool = False) -> dict[str, Any]:
        """Perform a health check.
        
        Args:
            force: Force a fresh check (ignore cache).
        
        Returns:
            Dictionary with health status.
        """
        now = time.time()
        
        # Use cache if recent
        if not force and self._last_check and (now - self._last_check_time) < 1.0:
            return self._last_check
        
        status = {
            "status": "healthy",
            "timestamp": now,
            "components": {},
        }
        
        components = self.check_components()
        worst_status = HealthStatus.HEALTHY
        
        for comp in components:
            status["components"][comp.name] = {
                "status": comp.status.value,
                "message": comp.message,
                "latency_ms": comp.latency_ms,
                **comp.metadata,
            }
            
            # Track worst status
            if comp.status == HealthStatus.UNHEALTHY:
                worst_status = HealthStatus.UNHEALTHY
            elif comp.status == HealthStatus.DEGRADED and worst_status != HealthStatus.UNHEALTHY:
                worst_status = HealthStatus.DEGRADED
        
        status["status"] = worst_status.value
        
        # Add engine-specific info
        if self._engine:
            status.update(self._check_engine())
        
        self._last_check = status
        self._last_check_time = now
        
        return status
    
    def check_components(self) -> list[ComponentHealth]:
        """Check health of all components.
        
        Returns:
            List of component health objects.
        """
        results = []
        
        # Built-in checks
        results.append(self._check_memory())
        results.append(self._check_backend())
        
        # Custom checks
        for name, checker in self._checkers.items():
            try:
                start = time.time()
                result = checker()
                result.latency_ms = (time.time() - start) * 1000
                results.append(result)
            except Exception as e:
                results.append(ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                ))
        
        return results
    
    def is_healthy(self) -> bool:
        """Quick health check.
        
        Returns:
            True if service is healthy.
        """
        status = self.check()
        return status["status"] == "healthy"
    
    def is_ready(self) -> bool:
        """Check if service is ready to handle requests.
        
        Returns:
            True if service is ready.
        """
        if not self._engine:
            return True
        
        # Check if model is loaded
        try:
            return self._engine._backend is not None
        except Exception:
            return False
    
    def start_background_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._background_thread and self._background_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._background_thread = threading.Thread(
            target=self._background_loop,
            daemon=True,
            name="health-monitor",
        )
        self._background_thread.start()
    
    def stop_background_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._stop_event.set()
        if self._background_thread:
            self._background_thread.join(timeout=2.0)
    
    def _background_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_event.is_set():
            try:
                self.check(force=True)
            except Exception:
                pass
            self._stop_event.wait(self._check_interval)
    
    def _check_engine(self) -> dict[str, Any]:
        """Check engine-specific health metrics."""
        if not self._engine:
            return {}
        
        info = {}
        
        try:
            info["backend"] = self._engine._backend.name if self._engine._backend else "none"
            info["model_loaded"] = self._engine._backend is not None
        except Exception:
            pass
        
        # Add realtime stats if available
        try:
            if hasattr(self._engine, "buffer_stats"):
                stats = self._engine.buffer_stats
                info["buffer_fill"] = stats.buffer_fill_ratio
                info["underruns"] = stats.underruns
                info["overruns"] = stats.overruns
        except Exception:
            pass
        
        return info
    
    def _check_memory(self) -> ComponentHealth:
        """Check memory usage."""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)
            
            status = HealthStatus.HEALTHY
            if memory_mb > 2048:  # > 2GB
                status = HealthStatus.DEGRADED
            if memory_mb > 4096:  # > 4GB
                status = HealthStatus.UNHEALTHY
            
            return ComponentHealth(
                name="memory",
                status=status,
                metadata={"memory_mb": round(memory_mb, 1)},
            )
        except ImportError:
            return ComponentHealth(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message="psutil not installed",
            )
        except Exception as e:
            return ComponentHealth(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message=str(e),
            )
    
    def _check_backend(self) -> ComponentHealth:
        """Check TTS backend health."""
        if not self._engine:
            return ComponentHealth(
                name="backend",
                status=HealthStatus.UNKNOWN,
                message="No engine configured",
            )
        
        try:
            backend = self._engine._backend
            if backend is None:
                return ComponentHealth(
                    name="backend",
                    status=HealthStatus.UNHEALTHY,
                    message="No backend loaded",
                )
            
            return ComponentHealth(
                name="backend",
                status=HealthStatus.HEALTHY,
                metadata={
                    "name": backend.name,
                    "sample_rate": backend.sample_rate,
                },
            )
        except Exception as e:
            return ComponentHealth(
                name="backend",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
