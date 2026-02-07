"""
Real-Time Audio Pipeline (v2.3)

Provides low-latency synthesis for interactive applications like
voice assistants, games, and conversational agents.

Key Components:
    RealtimeEngine      - Low-latency engine with real-time guarantees
    RealtimeConfig      - Configuration for real-time mode
    BackpressurePolicy  - How to handle when synthesis can't keep up

Example:
    from voice_soundboard.realtime import RealtimeEngine, RealtimeConfig
    
    engine = RealtimeEngine(
        RealtimeConfig(
            max_latency_ms=50,
            drop_policy="graceful"
        )
    )
    
    with engine.session() as session:
        for word in llm_stream():
            session.speak(word)
"""

from voice_soundboard.realtime.engine import (
    RealtimeEngine,
    RealtimeSession,
)
from voice_soundboard.realtime.config import (
    RealtimeConfig,
    BackpressurePolicy,
    DropPolicy,
)
from voice_soundboard.realtime.buffer import (
    RealtimeBuffer,
    BufferStats,
)

__all__ = [
    "RealtimeEngine",
    "RealtimeSession",
    "RealtimeConfig",
    "BackpressurePolicy",
    "DropPolicy",
    "RealtimeBuffer",
    "BufferStats",
]
