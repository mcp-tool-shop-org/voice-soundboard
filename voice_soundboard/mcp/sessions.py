"""
MCP Sessions - Agent-aware audio session management.

Provides session-scoped synthesis with ownership, isolation,
and priority rules for agent-driven audio.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session lifecycle states."""
    
    CREATED = "created"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class SessionPriority(Enum):
    """Session priority levels for interruption."""
    
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class SessionConfig:
    """Configuration for MCP sessions.
    
    Attributes:
        timeout_seconds: Session timeout in seconds
        max_concurrent_streams: Maximum concurrent streams per session
        allow_self_interrupt: Whether session can interrupt itself
        priority: Session priority level
        metadata: Additional session metadata
    """
    
    timeout_seconds: float = 300.0  # 5 minutes default
    max_concurrent_streams: int = 10
    allow_self_interrupt: bool = True
    priority: SessionPriority = SessionPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamInfo:
    """Information about an active stream.
    
    Attributes:
        stream_id: Unique stream identifier
        started_at: Stream start timestamp
        text: Text being synthesized
        voice: Voice being used
        interruptible: Whether stream can be interrupted
        audio_ms_played: Milliseconds of audio played
        interrupted: Whether stream was interrupted
        interrupt_reason: Reason for interruption
    """
    
    stream_id: str
    started_at: float = field(default_factory=time.time)
    text: str = ""
    voice: Optional[str] = None
    interruptible: bool = True
    audio_ms_played: int = 0
    interrupted: bool = False
    interrupt_reason: Optional[str] = None


class MCPSession:
    """
    Agent-aware audio session.
    
    Provides session-scoped synthesis with ownership and isolation.
    Only the owning agent can interrupt its audio.
    
    Example:
        session = mcp.create_session(agent_id="planner")
        
        # Synthesize with session context
        result = await mcp.call(
            tool="voice.stream",
            session=session,
            input={"text": "Let me explain..."}
        )
        
        # Only this agent can interrupt
        await session.interrupt_all(reason="context_change")
    """
    
    def __init__(
        self,
        session_id: str,
        agent_id: str,
        config: Optional[SessionConfig] = None,
    ):
        """
        Initialize session.
        
        Args:
            session_id: Unique session identifier
            agent_id: Owning agent identifier
            config: Session configuration
        """
        self.session_id = session_id
        self.agent_id = agent_id
        self.config = config or SessionConfig()
        
        self._state = SessionState.CREATED
        self._created_at = time.time()
        self._last_activity = time.time()
        self._streams: Dict[str, StreamInfo] = {}
        self._conversation_ids: Set[str] = set()
        self._lock = threading.RLock()
        self._event_listeners: List[Callable] = []
    
    @property
    def state(self) -> SessionState:
        """Get current session state."""
        return self._state
    
    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self._state == SessionState.ACTIVE
    
    @property
    def active_streams(self) -> List[StreamInfo]:
        """Get list of active streams."""
        with self._lock:
            return [
                s for s in self._streams.values()
                if not s.interrupted
            ]
    
    @property
    def age_seconds(self) -> float:
        """Get session age in seconds."""
        return time.time() - self._created_at
    
    @property
    def idle_seconds(self) -> float:
        """Get idle time since last activity."""
        return time.time() - self._last_activity
    
    def activate(self) -> None:
        """Activate the session."""
        self._state = SessionState.ACTIVE
        self._last_activity = time.time()
        self._emit_event("session_activated", {"session_id": self.session_id})
    
    def suspend(self) -> None:
        """Suspend the session."""
        self._state = SessionState.SUSPENDED
        self._emit_event("session_suspended", {"session_id": self.session_id})
    
    def close(self) -> None:
        """Close the session."""
        # Interrupt all streams
        self.interrupt_all(reason="session_closed")
        self._state = SessionState.CLOSED
        self._emit_event("session_closed", {"session_id": self.session_id})
    
    def touch(self) -> None:
        """Update last activity timestamp."""
        self._last_activity = time.time()
    
    def register_stream(
        self,
        stream_id: str,
        text: str = "",
        voice: Optional[str] = None,
        interruptible: bool = True,
    ) -> StreamInfo:
        """
        Register a new stream.
        
        Args:
            stream_id: Unique stream identifier
            text: Text being synthesized
            voice: Voice being used
            interruptible: Whether stream can be interrupted
            
        Returns:
            StreamInfo for the registered stream
        """
        with self._lock:
            if len(self._streams) >= self.config.max_concurrent_streams:
                raise RuntimeError("Maximum concurrent streams exceeded")
            
            info = StreamInfo(
                stream_id=stream_id,
                text=text,
                voice=voice,
                interruptible=interruptible,
            )
            self._streams[stream_id] = info
            self._last_activity = time.time()
            
            self._emit_event("stream_started", {
                "session_id": self.session_id,
                "stream_id": stream_id,
            })
            
            return info
    
    def update_stream(
        self,
        stream_id: str,
        audio_ms_played: Optional[int] = None,
    ) -> None:
        """
        Update stream information.
        
        Args:
            stream_id: Stream identifier
            audio_ms_played: Updated audio played duration
        """
        with self._lock:
            if stream_id in self._streams:
                if audio_ms_played is not None:
                    self._streams[stream_id].audio_ms_played = audio_ms_played
                self._last_activity = time.time()
    
    def complete_stream(self, stream_id: str) -> None:
        """
        Mark a stream as completed.
        
        Args:
            stream_id: Stream identifier
        """
        with self._lock:
            if stream_id in self._streams:
                del self._streams[stream_id]
                self._last_activity = time.time()
                
                self._emit_event("stream_completed", {
                    "session_id": self.session_id,
                    "stream_id": stream_id,
                })
    
    def is_interrupted(self, stream_id: str) -> bool:
        """
        Check if a stream is interrupted.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            True if stream is interrupted
        """
        with self._lock:
            if stream_id in self._streams:
                return self._streams[stream_id].interrupted
            return True  # Unknown stream treated as interrupted
    
    def interrupt_stream(
        self,
        stream_id: str,
        reason: str = "manual",
        fade_out_ms: int = 50,
    ) -> int:
        """
        Interrupt a specific stream.
        
        Args:
            stream_id: Stream identifier
            reason: Reason for interruption
            fade_out_ms: Fade out duration
            
        Returns:
            Audio milliseconds played before interruption
        """
        with self._lock:
            if stream_id not in self._streams:
                return 0
            
            info = self._streams[stream_id]
            
            if not info.interruptible:
                raise RuntimeError(f"Stream {stream_id} is not interruptible")
            
            info.interrupted = True
            info.interrupt_reason = reason
            audio_played = info.audio_ms_played
            
            self._emit_event("stream_interrupted", {
                "session_id": self.session_id,
                "stream_id": stream_id,
                "reason": reason,
                "audio_ms_played": audio_played,
            })
            
            self._last_activity = time.time()
            return audio_played
    
    def interrupt_all(
        self,
        reason: str = "manual",
        fade_out_ms: int = 50,
    ) -> int:
        """
        Interrupt all active streams.
        
        Args:
            reason: Reason for interruption
            fade_out_ms: Fade out duration
            
        Returns:
            Number of streams interrupted
        """
        with self._lock:
            count = 0
            for stream_id, info in self._streams.items():
                if not info.interrupted and info.interruptible:
                    info.interrupted = True
                    info.interrupt_reason = reason
                    count += 1
            
            if count > 0:
                self._emit_event("all_streams_interrupted", {
                    "session_id": self.session_id,
                    "reason": reason,
                    "count": count,
                })
            
            self._last_activity = time.time()
            return count
    
    def add_conversation(self, conversation_id: str) -> None:
        """
        Associate a conversation with this session.
        
        Args:
            conversation_id: Conversation identifier
        """
        self._conversation_ids.add(conversation_id)
    
    def has_conversation(self, conversation_id: str) -> bool:
        """
        Check if conversation belongs to this session.
        
        Args:
            conversation_id: Conversation identifier
            
        Returns:
            True if conversation is associated
        """
        return conversation_id in self._conversation_ids
    
    def on_event(self, callback: Callable) -> None:
        """
        Register an event listener.
        
        Args:
            callback: Callback function for events
        """
        self._event_listeners.append(callback)
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event to listeners."""
        for listener in self._event_listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                logger.error(f"Session event listener error: {e}")
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get session information.
        
        Returns:
            Session information dictionary
        """
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "state": self._state.value,
            "created_at": self._created_at,
            "last_activity": self._last_activity,
            "age_seconds": self.age_seconds,
            "idle_seconds": self.idle_seconds,
            "active_streams": len(self.active_streams),
            "conversations": list(self._conversation_ids),
            "priority": self.config.priority.value,
        }


class SessionManager:
    """
    Manager for MCP sessions.
    
    Handles session lifecycle, cleanup, and cross-session operations.
    
    Example:
        manager = SessionManager()
        
        # Create session for agent
        session = manager.create_session("agent-123")
        
        # Get existing session
        session = manager.get_session(session_id)
        
        # Clean up expired sessions
        manager.cleanup_expired()
    """
    
    def __init__(
        self,
        default_config: Optional[SessionConfig] = None,
    ):
        """
        Initialize session manager.
        
        Args:
            default_config: Default configuration for new sessions
        """
        self._default_config = default_config or SessionConfig()
        self._sessions: Dict[str, MCPSession] = {}
        self._agent_sessions: Dict[str, Set[str]] = {}  # agent_id -> session_ids
        self._lock = threading.RLock()
        self._cleanup_task: Optional[asyncio.Task] = None
    
    @property
    def session_count(self) -> int:
        """Get total number of sessions."""
        return len(self._sessions)
    
    @property
    def active_session_count(self) -> int:
        """Get number of active sessions."""
        return sum(1 for s in self._sessions.values() if s.is_active)
    
    def create_session(
        self,
        agent_id: str,
        config: Optional[SessionConfig] = None,
    ) -> MCPSession:
        """
        Create a new session.
        
        Args:
            agent_id: Agent identifier
            config: Session configuration
            
        Returns:
            New MCPSession instance
        """
        session_id = str(uuid.uuid4())
        config = config or self._default_config
        
        session = MCPSession(
            session_id=session_id,
            agent_id=agent_id,
            config=config,
        )
        
        with self._lock:
            self._sessions[session_id] = session
            
            if agent_id not in self._agent_sessions:
                self._agent_sessions[agent_id] = set()
            self._agent_sessions[agent_id].add(session_id)
        
        session.activate()
        logger.info(f"Created session {session_id} for agent {agent_id}")
        
        return session
    
    def get_session(self, session_id: str) -> Optional[MCPSession]:
        """
        Get a session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            MCPSession or None
        """
        return self._sessions.get(session_id)
    
    def get_or_create_session(
        self,
        session_id: Optional[str],
        agent_id: str,
    ) -> MCPSession:
        """
        Get existing session or create new one.
        
        Args:
            session_id: Optional session identifier
            agent_id: Agent identifier
            
        Returns:
            MCPSession instance
        """
        if session_id:
            session = self.get_session(session_id)
            if session:
                session.touch()
                return session
        
        return self.create_session(agent_id)
    
    def get_agent_sessions(self, agent_id: str) -> List[MCPSession]:
        """
        Get all sessions for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            List of sessions
        """
        with self._lock:
            session_ids = self._agent_sessions.get(agent_id, set())
            return [
                self._sessions[sid]
                for sid in session_ids
                if sid in self._sessions
            ]
    
    def close_session(self, session_id: str) -> bool:
        """
        Close a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was closed
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            
            session.close()
            
            # Remove from agent mapping
            agent_sessions = self._agent_sessions.get(session.agent_id)
            if agent_sessions:
                agent_sessions.discard(session_id)
            
            del self._sessions[session_id]
            logger.info(f"Closed session {session_id}")
            return True
    
    def close_agent_sessions(self, agent_id: str) -> int:
        """
        Close all sessions for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Number of sessions closed
        """
        with self._lock:
            session_ids = list(self._agent_sessions.get(agent_id, set()))
            count = 0
            
            for session_id in session_ids:
                if self.close_session(session_id):
                    count += 1
            
            return count
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        with self._lock:
            expired = []
            
            for session_id, session in self._sessions.items():
                if session.idle_seconds > session.config.timeout_seconds:
                    expired.append(session_id)
            
            for session_id in expired:
                self.close_session(session_id)
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired sessions")
            
            return len(expired)
    
    async def start_cleanup_loop(
        self,
        interval_seconds: float = 60.0,
    ) -> None:
        """
        Start background cleanup loop.
        
        Args:
            interval_seconds: Cleanup interval in seconds
        """
        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval_seconds)
                self.cleanup_expired()
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    def stop_cleanup_loop(self) -> None:
        """Stop background cleanup loop."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
    
    def can_interrupt(
        self,
        requesting_agent: str,
        target_session: MCPSession,
    ) -> bool:
        """
        Check if an agent can interrupt a session.
        
        Args:
            requesting_agent: Agent requesting interruption
            target_session: Session to interrupt
            
        Returns:
            True if interruption is allowed
        """
        # Owner can always interrupt
        if target_session.agent_id == requesting_agent:
            return target_session.config.allow_self_interrupt
        
        # Check priority-based interruption
        requesting_sessions = self.get_agent_sessions(requesting_agent)
        if not requesting_sessions:
            return False
        
        # Higher priority can interrupt lower
        max_priority = max(s.config.priority.value for s in requesting_sessions)
        return max_priority > target_session.config.priority.value
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get session manager statistics.
        
        Returns:
            Statistics dictionary
        """
        with self._lock:
            total_streams = sum(
                len(s.active_streams)
                for s in self._sessions.values()
            )
            
            return {
                "total_sessions": self.session_count,
                "active_sessions": self.active_session_count,
                "total_agents": len(self._agent_sessions),
                "total_active_streams": total_streams,
            }
