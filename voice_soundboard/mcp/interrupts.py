"""
MCP Interrupts - Explicit interrupt semantics for agent-driven audio.

Provides structured interrupt handling with reasons, graceful fade-out,
rollback support, and acknowledgement events.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from voice_soundboard.mcp.sessions import MCPSession

logger = logging.getLogger(__name__)


class InterruptReason(Enum):
    """
    Standardized reasons for audio interruption.
    
    Agents should use these to communicate why audio was interrupted,
    enabling proper handling and logging.
    """
    
    USER_SPOKE = "user_spoke"
    """User started speaking (voice activity detected)."""
    
    CONTEXT_CHANGE = "context_change"
    """Context or topic changed, previous audio no longer relevant."""
    
    TIMEOUT = "timeout"
    """Audio exceeded maximum duration."""
    
    MANUAL = "manual"
    """Manual interruption by agent or user."""
    
    PRIORITY = "priority"
    """Higher priority audio needs to play."""
    
    ERROR = "error"
    """Error occurred during synthesis."""
    
    SESSION_CLOSED = "session_closed"
    """Session was closed, all audio interrupted."""
    
    ROLLBACK = "rollback"
    """Rolling back to previous state."""


class InterruptBehavior(Enum):
    """How to handle audio when interrupted."""
    
    IMMEDIATE = "immediate"
    """Stop immediately (no fade)."""
    
    FADE_OUT = "fade_out"
    """Fade out audio gracefully."""
    
    COMPLETE_WORD = "complete_word"
    """Complete current word then stop."""
    
    COMPLETE_SENTENCE = "complete_sentence"
    """Complete current sentence then stop."""


@dataclass
class InterruptConfig:
    """Configuration for interrupt handling.
    
    Attributes:
        default_behavior: Default interrupt behavior
        fade_out_ms: Default fade out duration in milliseconds
        min_audio_before_interrupt_ms: Minimum audio to play before allowing interrupt
        enable_rollback: Whether to support audio rollback
        max_rollback_ms: Maximum duration to support rollback
    """
    
    default_behavior: InterruptBehavior = InterruptBehavior.FADE_OUT
    fade_out_ms: int = 50
    min_audio_before_interrupt_ms: int = 100
    enable_rollback: bool = True
    max_rollback_ms: int = 5000


@dataclass
class InterruptEvent:
    """
    Structured interrupt event.
    
    Provides all information about an interruption for logging,
    debugging, and agent reasoning.
    
    Attributes:
        event_type: Always "voice.interrupted"
        stream_id: Stream that was interrupted
        session_id: Session context
        reason: Why the interruption occurred
        audio_ms_played: How much audio was played
        audio_ms_remaining: How much audio remained
        behavior: How the interrupt was handled
        fade_out_ms: Fade duration applied
        timestamp: When interruption occurred
        metadata: Additional metadata
    """
    
    event_type: str = "voice.interrupted"
    stream_id: Optional[str] = None
    session_id: Optional[str] = None
    reason: InterruptReason = InterruptReason.MANUAL
    audio_ms_played: int = 0
    audio_ms_remaining: int = 0
    behavior: InterruptBehavior = InterruptBehavior.FADE_OUT
    fade_out_ms: int = 50
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event": self.event_type,
            "stream_id": self.stream_id,
            "session_id": self.session_id,
            "reason": self.reason.value,
            "audio_ms_played": self.audio_ms_played,
            "audio_ms_remaining": self.audio_ms_remaining,
            "behavior": self.behavior.value,
            "fade_out_ms": self.fade_out_ms,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class RollbackPoint:
    """Point in audio stream that can be rolled back to.
    
    Attributes:
        position_ms: Position in audio stream
        text_offset: Character offset in text
        timestamp: When this point was recorded
        audio_data: Cached audio data (if available)
    """
    
    position_ms: int
    text_offset: int
    timestamp: float = field(default_factory=time.time)
    audio_data: Optional[bytes] = None


class InterruptHandler:
    """
    Handler for audio interruption semantics.
    
    Manages graceful interrupts, rollback points, and structured
    event emission.
    
    Example:
        handler = InterruptHandler()
        
        # Handle interruption
        event = handler.interrupt(
            stream_id="stream-123",
            reason=InterruptReason.USER_SPOKE,
            audio_ms_played=420,
        )
        
        # Result:
        # {
        #   "event": "voice.interrupted",
        #   "reason": "user_spoke",
        #   "audio_ms_played": 420
        # }
    """
    
    def __init__(
        self,
        config: Optional[InterruptConfig] = None,
    ):
        """
        Initialize interrupt handler.
        
        Args:
            config: Interrupt configuration
        """
        self.config = config or InterruptConfig()
        
        self._active_streams: Dict[str, Dict[str, Any]] = {}
        self._rollback_points: Dict[str, List[RollbackPoint]] = {}
        self._event_listeners: List[Callable] = []
    
    def register_stream(
        self,
        stream_id: str,
        total_duration_ms: int,
        interruptible: bool = True,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Register a stream for interrupt handling.
        
        Args:
            stream_id: Stream identifier
            total_duration_ms: Total audio duration
            interruptible: Whether stream can be interrupted
            session_id: Session context
        """
        self._active_streams[stream_id] = {
            "total_duration_ms": total_duration_ms,
            "current_position_ms": 0,
            "interruptible": interruptible,
            "session_id": session_id,
            "started_at": time.time(),
        }
        
        if self.config.enable_rollback:
            self._rollback_points[stream_id] = []
    
    def update_position(
        self,
        stream_id: str,
        position_ms: int,
        text_offset: Optional[int] = None,
    ) -> None:
        """
        Update stream position for interrupt tracking.
        
        Args:
            stream_id: Stream identifier
            position_ms: Current position in milliseconds
            text_offset: Current text character offset
        """
        if stream_id not in self._active_streams:
            return
        
        self._active_streams[stream_id]["current_position_ms"] = position_ms
        
        # Create rollback point if enabled and interval reached
        if self.config.enable_rollback and text_offset is not None:
            if stream_id not in self._rollback_points:
                self._rollback_points[stream_id] = []
            
            points = self._rollback_points[stream_id]
            
            # Add rollback point every second
            if not points or position_ms - points[-1].position_ms >= 1000:
                points.append(RollbackPoint(
                    position_ms=position_ms,
                    text_offset=text_offset,
                ))
                
                # Trim old points beyond max rollback
                while points and points[0].position_ms < position_ms - self.config.max_rollback_ms:
                    points.pop(0)
    
    def can_interrupt(self, stream_id: str) -> bool:
        """
        Check if a stream can be interrupted.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            True if stream can be interrupted
        """
        info = self._active_streams.get(stream_id)
        if not info:
            return False
        
        if not info["interruptible"]:
            return False
        
        # Check minimum play time
        if info["current_position_ms"] < self.config.min_audio_before_interrupt_ms:
            return False
        
        return True
    
    def interrupt(
        self,
        stream_id: str,
        reason: InterruptReason = InterruptReason.MANUAL,
        behavior: Optional[InterruptBehavior] = None,
        fade_out_ms: Optional[int] = None,
        session: Optional["MCPSession"] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InterruptEvent:
        """
        Interrupt a stream.
        
        Args:
            stream_id: Stream identifier
            reason: Reason for interruption
            behavior: How to handle the interrupt
            fade_out_ms: Fade out duration override
            session: Session context
            metadata: Additional metadata
            
        Returns:
            InterruptEvent with details
        """
        info = self._active_streams.get(stream_id, {})
        
        behavior = behavior or self.config.default_behavior
        fade_out_ms = fade_out_ms if fade_out_ms is not None else self.config.fade_out_ms
        
        audio_played = info.get("current_position_ms", 0)
        total_duration = info.get("total_duration_ms", 0)
        audio_remaining = max(0, total_duration - audio_played)
        
        event = InterruptEvent(
            stream_id=stream_id,
            session_id=info.get("session_id") or (session.session_id if session else None),
            reason=reason,
            audio_ms_played=audio_played,
            audio_ms_remaining=audio_remaining,
            behavior=behavior,
            fade_out_ms=fade_out_ms,
            metadata=metadata or {},
        )
        
        # Notify session if available
        if session:
            session.interrupt_stream(stream_id, reason.value, fade_out_ms)
        
        # Clean up
        self._active_streams.pop(stream_id, None)
        self._rollback_points.pop(stream_id, None)
        
        # Emit event
        self._emit_event(event)
        
        logger.info(
            f"Interrupted stream {stream_id}: reason={reason.value}, "
            f"played={audio_played}ms, remaining={audio_remaining}ms"
        )
        
        return event
    
    def interrupt_all(
        self,
        reason: InterruptReason = InterruptReason.MANUAL,
        session_id: Optional[str] = None,
    ) -> List[InterruptEvent]:
        """
        Interrupt all streams (optionally filtered by session).
        
        Args:
            reason: Reason for interruption
            session_id: Filter by session (None = all)
            
        Returns:
            List of interrupt events
        """
        events = []
        stream_ids = list(self._active_streams.keys())
        
        for stream_id in stream_ids:
            info = self._active_streams.get(stream_id, {})
            
            # Filter by session if specified
            if session_id and info.get("session_id") != session_id:
                continue
            
            if self.can_interrupt(stream_id):
                event = self.interrupt(stream_id, reason)
                events.append(event)
        
        return events
    
    def get_rollback_points(
        self,
        stream_id: str,
    ) -> List[RollbackPoint]:
        """
        Get available rollback points for a stream.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            List of rollback points
        """
        return self._rollback_points.get(stream_id, [])
    
    def rollback(
        self,
        stream_id: str,
        target_ms: Optional[int] = None,
    ) -> Optional[RollbackPoint]:
        """
        Rollback to a previous point in the stream.
        
        Args:
            stream_id: Stream identifier
            target_ms: Target position (None = most recent)
            
        Returns:
            RollbackPoint or None if not available
        """
        points = self._rollback_points.get(stream_id, [])
        if not points:
            return None
        
        if target_ms is None:
            # Use most recent point
            return points[-1]
        
        # Find closest point before target
        for point in reversed(points):
            if point.position_ms <= target_ms:
                return point
        
        return points[0] if points else None
    
    def complete_stream(self, stream_id: str) -> None:
        """
        Mark a stream as completed (no interruption).
        
        Args:
            stream_id: Stream identifier
        """
        self._active_streams.pop(stream_id, None)
        self._rollback_points.pop(stream_id, None)
    
    def on_event(self, callback: Callable[[InterruptEvent], None]) -> None:
        """
        Register an event listener.
        
        Args:
            callback: Callback for interrupt events
        """
        self._event_listeners.append(callback)
    
    def _emit_event(self, event: InterruptEvent) -> None:
        """Emit an interrupt event to listeners."""
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Interrupt event listener error: {e}")
    
    def get_active_streams(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all active streams being managed.
        
        Returns:
            Dictionary of stream_id to stream info
        """
        return self._active_streams.copy()


async def apply_fade_out(
    audio_callback: Callable[[float], None],
    duration_ms: int,
    steps: int = 10,
) -> None:
    """
    Apply a fade-out effect.
    
    Args:
        audio_callback: Callback to set volume (0.0 to 1.0)
        duration_ms: Fade duration in milliseconds
        steps: Number of fade steps
    """
    step_duration = duration_ms / steps / 1000
    
    for i in range(steps):
        volume = 1.0 - (i / steps)
        audio_callback(volume)
        await asyncio.sleep(step_duration)
    
    audio_callback(0.0)


def create_interrupt_acknowledgement(
    event: InterruptEvent,
) -> Dict[str, Any]:
    """
    Create a structured interrupt acknowledgement for agents.
    
    Args:
        event: Interrupt event
        
    Returns:
        Agent-friendly acknowledgement dictionary
    """
    return {
        "acknowledged": True,
        "event": "voice.interrupted",
        "reason": event.reason.value,
        "audio_ms_played": event.audio_ms_played,
        "audio_ms_remaining": event.audio_ms_remaining,
        "can_resume": event.audio_ms_remaining > 0,
        "timestamp": event.timestamp,
    }
