"""
Quality Monitor - Voice quality monitoring and alerting.

Features:
    - Pronunciation accuracy tracking
    - Naturalness scoring
    - Timing quality metrics
    - Regression detection
    - Alert notifications
"""

from __future__ import annotations

import time
import threading
import random
from dataclasses import dataclass, field
from typing import Any, Callable
from collections import deque
from enum import Enum


class QualityMetricType(Enum):
    """Types of quality metrics."""
    
    PRONUNCIATION = "pronunciation"
    NATURALNESS = "naturalness"
    TIMING = "timing"
    CLARITY = "clarity"
    CONSISTENCY = "consistency"


@dataclass
class QualityMetrics:
    """Quality metrics for a synthesis result."""
    
    pronunciation_score: float = 0.0  # 0-1
    naturalness_score: float = 0.0   # 0-1
    timing_score: float = 0.0        # 0-1
    clarity_score: float = 0.0       # 0-1
    consistency_score: float = 0.0   # 0-1
    
    # Metadata
    voice: str = ""
    timestamp: float = 0.0
    audio_duration: float = 0.0
    text_length: int = 0
    
    @property
    def overall_score(self) -> float:
        """Calculate overall quality score."""
        scores = [
            self.pronunciation_score,
            self.naturalness_score,
            self.timing_score,
            self.clarity_score,
            self.consistency_score,
        ]
        valid_scores = [s for s in scores if s > 0]
        return sum(valid_scores) / len(valid_scores) if valid_scores else 0.0


@dataclass
class QualityAlert:
    """Alert for quality issues."""
    
    metric: QualityMetricType
    threshold: float
    actual_value: float
    voice: str
    timestamp: float = field(default_factory=time.time)
    message: str = ""
    
    @property
    def severity(self) -> str:
        """Get alert severity."""
        diff = self.threshold - self.actual_value
        if diff > 0.3:
            return "critical"
        elif diff > 0.15:
            return "warning"
        else:
            return "info"


@dataclass
class QualityConfig:
    """Configuration for quality monitoring."""
    
    # Sampling
    sample_rate: float = 0.1  # Sample 10% of requests
    max_samples: int = 1000
    
    # Metrics to track
    metrics: list[str] = field(default_factory=lambda: [
        "pronunciation", "naturalness", "timing"
    ])
    
    # Thresholds for alerting
    thresholds: dict[str, float] = field(default_factory=lambda: {
        "pronunciation": 0.7,
        "naturalness": 0.7,
        "timing": 0.7,
        "clarity": 0.7,
        "consistency": 0.8,
    })
    
    # Alerting
    enable_alerts: bool = True
    alert_cooldown_seconds: int = 300
    alert_action: str | None = None  # URL or action identifier
    
    # Analysis
    compare_window_hours: int = 24
    regression_threshold: float = 0.1


class QualityMonitor:
    """
    Monitor voice synthesis quality.
    
    Example:
        monitor = QualityMonitor(
            sample_rate=0.1,  # Sample 10% of requests
            metrics=["pronunciation", "naturalness", "timing"],
        )
        
        # Automatic quality scoring
        engine = VoiceEngine(Config(quality_monitor=monitor))
        
        # Alert on quality regression
        monitor.set_alert(
            metric="naturalness",
            threshold=0.7,
            action="slack://alerts",
        )
    """
    
    def __init__(
        self,
        sample_rate: float = 0.1,
        metrics: list[str] | None = None,
        config: QualityConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = QualityConfig(
                sample_rate=sample_rate,
                metrics=metrics or QualityConfig().metrics,
            )
        
        # Storage
        self._samples: deque[QualityMetrics] = deque(maxlen=self.config.max_samples)
        self._alerts: list[QualityAlert] = []
        self._last_alert_time: dict[str, float] = {}
        self._lock = threading.Lock()
        
        # Handlers
        self._alert_handlers: list[Callable[[QualityAlert], None]] = []
    
    def should_sample(self) -> bool:
        """Check if current request should be sampled."""
        return random.random() < self.config.sample_rate
    
    def record(
        self,
        audio_path: str,
        text: str,
        voice: str,
    ) -> QualityMetrics | None:
        """
        Record and analyze a synthesis result.
        
        Args:
            audio_path: Path to generated audio
            text: Original text
            voice: Voice used
            
        Returns:
            QualityMetrics if sampled, None otherwise
        """
        if not self.should_sample():
            return None
        
        # Analyze quality
        metrics = self._analyze_quality(audio_path, text, voice)
        
        # Store
        with self._lock:
            self._samples.append(metrics)
        
        # Check for alerts
        self._check_alerts(metrics)
        
        return metrics
    
    def _analyze_quality(
        self,
        audio_path: str,
        text: str,
        voice: str,
    ) -> QualityMetrics:
        """Analyze audio quality."""
        metrics = QualityMetrics(
            voice=voice,
            timestamp=time.time(),
            text_length=len(text),
        )
        
        # Pronunciation analysis
        if "pronunciation" in self.config.metrics:
            metrics.pronunciation_score = self._analyze_pronunciation(audio_path, text)
        
        # Naturalness analysis
        if "naturalness" in self.config.metrics:
            metrics.naturalness_score = self._analyze_naturalness(audio_path)
        
        # Timing analysis
        if "timing" in self.config.metrics:
            metrics.timing_score = self._analyze_timing(audio_path, text)
        
        # Clarity analysis
        if "clarity" in self.config.metrics:
            metrics.clarity_score = self._analyze_clarity(audio_path)
        
        return metrics
    
    def _analyze_pronunciation(self, audio_path: str, text: str) -> float:
        """Analyze pronunciation accuracy."""
        # This would use ASR to transcribe and compare
        # Simplified implementation returns placeholder
        try:
            # Would use speech recognition to get transcript
            # Then compare with original text
            # Using word error rate or similar metric
            return 0.85  # Placeholder
        except Exception:
            return 0.0
    
    def _analyze_naturalness(self, audio_path: str) -> float:
        """Analyze naturalness of speech."""
        # This would use MOS prediction model
        # Simplified implementation returns placeholder
        try:
            # Would analyze prosody, rhythm, intonation
            return 0.82  # Placeholder
        except Exception:
            return 0.0
    
    def _analyze_timing(self, audio_path: str, text: str) -> float:
        """Analyze timing quality."""
        # Check speech rate, pauses, etc.
        try:
            # Would calculate words per minute
            # Check for appropriate pauses
            # Verify no unnatural gaps
            return 0.88  # Placeholder
        except Exception:
            return 0.0
    
    def _analyze_clarity(self, audio_path: str) -> float:
        """Analyze audio clarity."""
        # Check for artifacts, distortion
        try:
            # Would analyze SNR, clipping, artifacts
            return 0.90  # Placeholder
        except Exception:
            return 0.0
    
    def _check_alerts(self, metrics: QualityMetrics) -> None:
        """Check if metrics trigger any alerts."""
        if not self.config.enable_alerts:
            return
        
        now = time.time()
        
        checks = [
            (QualityMetricType.PRONUNCIATION, metrics.pronunciation_score),
            (QualityMetricType.NATURALNESS, metrics.naturalness_score),
            (QualityMetricType.TIMING, metrics.timing_score),
            (QualityMetricType.CLARITY, metrics.clarity_score),
        ]
        
        for metric_type, value in checks:
            if value == 0:
                continue
            
            threshold = self.config.thresholds.get(metric_type.value, 0.7)
            
            if value < threshold:
                # Check cooldown
                alert_key = f"{metric_type.value}:{metrics.voice}"
                last_alert = self._last_alert_time.get(alert_key, 0)
                
                if now - last_alert < self.config.alert_cooldown_seconds:
                    continue
                
                # Create alert
                alert = QualityAlert(
                    metric=metric_type,
                    threshold=threshold,
                    actual_value=value,
                    voice=metrics.voice,
                    message=f"{metric_type.value} score {value:.2f} below threshold {threshold:.2f}",
                )
                
                self._alerts.append(alert)
                self._last_alert_time[alert_key] = now
                
                # Notify handlers
                for handler in self._alert_handlers:
                    try:
                        handler(alert)
                    except Exception:
                        pass
    
    def set_alert(
        self,
        metric: str,
        threshold: float,
        action: str | None = None,
    ) -> None:
        """
        Set an alert threshold.
        
        Args:
            metric: Metric name
            threshold: Alert threshold (0-1)
            action: Action to take (URL for webhook)
        """
        self.config.thresholds[metric] = threshold
        
        if action:
            self.config.alert_action = action
    
    def add_alert_handler(self, handler: Callable[[QualityAlert], None]) -> None:
        """Add an alert handler."""
        self._alert_handlers.append(handler)
    
    def get_average(
        self,
        voice: str | None = None,
        hours: int | None = None,
    ) -> QualityMetrics:
        """
        Get average quality metrics.
        
        Args:
            voice: Filter by voice
            hours: Time window in hours
            
        Returns:
            Average QualityMetrics
        """
        cutoff = time.time() - (hours * 3600) if hours else 0
        
        with self._lock:
            samples = [
                s for s in self._samples
                if s.timestamp > cutoff
                and (voice is None or s.voice == voice)
            ]
        
        if not samples:
            return QualityMetrics()
        
        return QualityMetrics(
            pronunciation_score=sum(s.pronunciation_score for s in samples) / len(samples),
            naturalness_score=sum(s.naturalness_score for s in samples) / len(samples),
            timing_score=sum(s.timing_score for s in samples) / len(samples),
            clarity_score=sum(s.clarity_score for s in samples) / len(samples),
            consistency_score=sum(s.consistency_score for s in samples) / len(samples),
        )
    
    def detect_regression(self) -> list[dict[str, Any]]:
        """
        Detect quality regressions.
        
        Returns:
            List of regression info dicts
        """
        regressions = []
        
        # Compare recent vs historical
        hours = self.config.compare_window_hours
        
        with self._lock:
            now = time.time()
            recent_cutoff = now - (hours * 3600)
            historical_cutoff = now - (hours * 2 * 3600)
            
            recent = [s for s in self._samples if s.timestamp > recent_cutoff]
            historical = [
                s for s in self._samples
                if historical_cutoff < s.timestamp <= recent_cutoff
            ]
        
        if not recent or not historical:
            return regressions
        
        # Compare averages
        metrics = ["pronunciation", "naturalness", "timing", "clarity"]
        
        for metric in metrics:
            recent_avg = sum(getattr(s, f"{metric}_score") for s in recent) / len(recent)
            historical_avg = sum(getattr(s, f"{metric}_score") for s in historical) / len(historical)
            
            if historical_avg - recent_avg > self.config.regression_threshold:
                regressions.append({
                    "metric": metric,
                    "recent_avg": recent_avg,
                    "historical_avg": historical_avg,
                    "regression": historical_avg - recent_avg,
                })
        
        return regressions
    
    def get_recent_alerts(self, hours: int = 24) -> list[QualityAlert]:
        """Get recent alerts."""
        cutoff = time.time() - (hours * 3600)
        return [a for a in self._alerts if a.timestamp > cutoff]
