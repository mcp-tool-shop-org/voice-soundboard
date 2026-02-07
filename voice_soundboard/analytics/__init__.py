"""
Voice Soundboard v2.4 - Analytics Module

Production observability and insights.

Components:
    UsageTracker    - Request and usage analytics
    QualityMonitor  - Voice quality monitoring
    CostTracker     - Backend cost attribution

Usage:
    from voice_soundboard.analytics import UsageTracker

    tracker = UsageTracker(backend="prometheus")
    engine = VoiceEngine(Config(analytics=tracker))

    # Query insights
    insights = tracker.query(timeframe="7d", group_by="voice")
"""

from voice_soundboard.analytics.usage import (
    UsageTracker,
    UsageConfig,
    UsageMetrics,
    UsageQuery,
)

from voice_soundboard.analytics.quality import (
    QualityMonitor,
    QualityConfig,
    QualityMetrics,
    QualityAlert,
)

from voice_soundboard.analytics.cost import (
    CostTracker,
    CostConfig,
    CostReport,
    PricingTier,
)

__all__ = [
    # Usage
    "UsageTracker",
    "UsageConfig",
    "UsageMetrics",
    "UsageQuery",
    # Quality
    "QualityMonitor",
    "QualityConfig",
    "QualityMetrics",
    "QualityAlert",
    # Cost
    "CostTracker",
    "CostConfig",
    "CostReport",
    "PricingTier",
]
