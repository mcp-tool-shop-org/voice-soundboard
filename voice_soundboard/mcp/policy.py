"""
MCP Policy - Permissions and safety model for agent-driven audio.

Provides clear boundaries for agent-driven audio without hard-coding policy.
Builds on v2.4 security foundations with MCP-specific controls.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Flag, auto
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class CapabilityFlags(Flag):
    """
    Capability flags for agent permissions.
    
    Agents can be granted specific capabilities based on trust level.
    """
    
    NONE = 0
    """No capabilities."""
    
    SPEAK = auto()
    """Basic speech synthesis."""
    
    STREAM = auto()
    """Streaming synthesis."""
    
    INTERRUPT = auto()
    """Interrupt active audio."""
    
    LIST_VOICES = auto()
    """List available voices."""
    
    STATUS = auto()
    """Query engine status."""
    
    EXTERNAL_BACKENDS = auto()
    """Use external (cloud) backends."""
    
    EMOTION_DETECTION = auto()
    """Use emotion detection."""
    
    VOICE_CLONING = auto()
    """Use voice cloning."""
    
    ANALYTICS = auto()
    """Access analytics data."""
    
    ADMIN = auto()
    """Administrative operations."""
    
    # Common presets
    BASIC = SPEAK | LIST_VOICES | STATUS
    """Basic read/speak capabilities."""
    
    STANDARD = BASIC | STREAM | INTERRUPT | EMOTION_DETECTION
    """Standard agent capabilities."""
    
    FULL = STANDARD | EXTERNAL_BACKENDS | ANALYTICS
    """Full capabilities (no admin)."""
    
    ALL = FULL | VOICE_CLONING | ADMIN
    """All capabilities."""


# Map tool names to required capabilities
TOOL_CAPABILITIES: Dict[str, CapabilityFlags] = {
    "voice.speak": CapabilityFlags.SPEAK,
    "voice.stream": CapabilityFlags.STREAM,
    "voice.interrupt": CapabilityFlags.INTERRUPT,
    "voice.list_voices": CapabilityFlags.LIST_VOICES,
    "voice.status": CapabilityFlags.STATUS,
}


class PolicyViolation(Exception):
    """Exception raised when policy is violated."""
    
    def __init__(
        self,
        message: str,
        tool: Optional[str] = None,
        agent_id: Optional[str] = None,
        violation_type: str = "unknown",
    ):
        """
        Initialize policy violation.
        
        Args:
            message: Error message
            tool: Tool that was accessed
            agent_id: Agent that violated policy
            violation_type: Type of violation
        """
        super().__init__(message)
        self.tool = tool
        self.agent_id = agent_id
        self.violation_type = violation_type


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting.
    
    Attributes:
        requests_per_minute: Maximum requests per minute
        characters_per_minute: Maximum characters per minute
        concurrent_streams: Maximum concurrent streams
        burst_allowance: Burst allowance multiplier
    """
    
    requests_per_minute: int = 60
    characters_per_minute: int = 10000
    concurrent_streams: int = 5
    burst_allowance: float = 1.5


@dataclass
class MCPPolicy:
    """
    Policy configuration for MCP access control.
    
    Defines what agents are allowed to do without hard-coding
    specific restrictions.
    
    Attributes:
        allow_tools: Set of allowed tool names (None = all)
        deny_tools: Set of denied tool names
        capabilities: Capability flags
        rate_limit: Rate limit configuration
        allow_external_backends: Whether to allow external backends
        max_text_length: Maximum text length per request
        allowed_voices: Set of allowed voices (None = all)
        allowed_backends: Set of allowed backends (None = all)
        metadata: Additional policy metadata
    
    Example:
        policy = MCPPolicy(
            allow_tools=["voice.speak", "voice.stream"],
            max_requests_per_minute=60,
            allow_external_backends=False,
        )
    """
    
    allow_tools: Optional[Set[str]] = None
    deny_tools: Set[str] = field(default_factory=set)
    capabilities: CapabilityFlags = CapabilityFlags.STANDARD
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    allow_external_backends: bool = False
    max_text_length: int = 10000
    allowed_voices: Optional[Set[str]] = None
    allowed_backends: Optional[Set[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def allows_tool(self, tool_name: str) -> bool:
        """
        Check if a tool is allowed.
        
        Args:
            tool_name: Tool name to check
            
        Returns:
            True if tool is allowed
        """
        # Check explicit deny
        if tool_name in self.deny_tools:
            return False
        
        # Check explicit allow (if specified)
        if self.allow_tools is not None:
            return tool_name in self.allow_tools
        
        # Check capability flags
        required = TOOL_CAPABILITIES.get(tool_name)
        if required:
            return bool(self.capabilities & required)
        
        return True  # Unknown tools allowed by default
    
    def allows_voice(self, voice: str) -> bool:
        """
        Check if a voice is allowed.
        
        Args:
            voice: Voice identifier
            
        Returns:
            True if voice is allowed
        """
        if self.allowed_voices is None:
            return True
        return voice in self.allowed_voices
    
    def allows_backend(self, backend: str) -> bool:
        """
        Check if a backend is allowed.
        
        Args:
            backend: Backend identifier
            
        Returns:
            True if backend is allowed
        """
        # Check external backend flag
        external_backends = {"openai", "elevenlabs", "azure", "google", "amazon"}
        if backend in external_backends and not self.allow_external_backends:
            return False
        
        # Check allowed list
        if self.allowed_backends is None:
            return True
        return backend in self.allowed_backends
    
    def has_capability(self, capability: CapabilityFlags) -> bool:
        """
        Check if capability is granted.
        
        Args:
            capability: Capability to check
            
        Returns:
            True if capability is granted
        """
        return bool(self.capabilities & capability)


@dataclass
class AgentRecord:
    """Record of agent activity for rate limiting.
    
    Attributes:
        agent_id: Agent identifier
        request_timestamps: Request timestamps (last minute)
        character_count: Characters synthesized (last minute)
        active_streams: Current active stream count
        violations: Violation count
    """
    
    agent_id: str
    request_timestamps: List[float] = field(default_factory=list)
    character_count: int = 0
    character_reset_time: float = field(default_factory=time.time)
    active_streams: int = 0
    violations: int = 0


class PolicyEnforcer:
    """
    Enforces MCP policies for agent access control.
    
    Checks permissions, enforces rate limits, and logs violations.
    
    Example:
        policy = MCPPolicy(allow_tools=["voice.speak"])
        enforcer = PolicyEnforcer(policy)
        
        # Check access
        enforcer.check_tool_access("voice.speak", "agent-123")
        
        # Track usage
        enforcer.record_request("agent-123", character_count=100)
    """
    
    def __init__(
        self,
        policy: MCPPolicy,
        agent_policies: Optional[Dict[str, MCPPolicy]] = None,
    ):
        """
        Initialize policy enforcer.
        
        Args:
            policy: Default policy
            agent_policies: Per-agent policy overrides
        """
        self._default_policy = policy
        self._agent_policies = agent_policies or {}
        self._agent_records: Dict[str, AgentRecord] = {}
    
    def get_policy(self, agent_id: Optional[str]) -> MCPPolicy:
        """
        Get policy for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Applicable policy
        """
        if agent_id and agent_id in self._agent_policies:
            return self._agent_policies[agent_id]
        return self._default_policy
    
    def set_agent_policy(
        self,
        agent_id: str,
        policy: MCPPolicy,
    ) -> None:
        """
        Set policy for a specific agent.
        
        Args:
            agent_id: Agent identifier
            policy: Policy to apply
        """
        self._agent_policies[agent_id] = policy
    
    def check_tool_access(
        self,
        tool_name: str,
        agent_id: Optional[str],
    ) -> None:
        """
        Check if agent can access a tool.
        
        Args:
            tool_name: Tool name
            agent_id: Agent identifier
            
        Raises:
            PolicyViolation: If access is denied
        """
        policy = self.get_policy(agent_id)
        
        if not policy.allows_tool(tool_name):
            self._record_violation(agent_id, "tool_access")
            raise PolicyViolation(
                f"Access denied to tool: {tool_name}",
                tool=tool_name,
                agent_id=agent_id,
                violation_type="tool_access",
            )
    
    def check_voice_access(
        self,
        voice: str,
        agent_id: Optional[str],
    ) -> None:
        """
        Check if agent can use a voice.
        
        Args:
            voice: Voice identifier
            agent_id: Agent identifier
            
        Raises:
            PolicyViolation: If access is denied
        """
        policy = self.get_policy(agent_id)
        
        if not policy.allows_voice(voice):
            self._record_violation(agent_id, "voice_access")
            raise PolicyViolation(
                f"Access denied to voice: {voice}",
                agent_id=agent_id,
                violation_type="voice_access",
            )
    
    def check_backend_access(
        self,
        backend: str,
        agent_id: Optional[str],
    ) -> None:
        """
        Check if agent can use a backend.
        
        Args:
            backend: Backend identifier
            agent_id: Agent identifier
            
        Raises:
            PolicyViolation: If access is denied
        """
        policy = self.get_policy(agent_id)
        
        if not policy.allows_backend(backend):
            self._record_violation(agent_id, "backend_access")
            raise PolicyViolation(
                f"Access denied to backend: {backend}",
                agent_id=agent_id,
                violation_type="backend_access",
            )
    
    def check_text_length(
        self,
        text: str,
        agent_id: Optional[str],
    ) -> None:
        """
        Check if text length is within limit.
        
        Args:
            text: Text to check
            agent_id: Agent identifier
            
        Raises:
            PolicyViolation: If text is too long
        """
        policy = self.get_policy(agent_id)
        
        if len(text) > policy.max_text_length:
            self._record_violation(agent_id, "text_length")
            raise PolicyViolation(
                f"Text length {len(text)} exceeds limit {policy.max_text_length}",
                agent_id=agent_id,
                violation_type="text_length",
            )
    
    def check_rate_limit(
        self,
        agent_id: Optional[str],
        character_count: int = 0,
    ) -> None:
        """
        Check rate limits for an agent.
        
        Args:
            agent_id: Agent identifier
            character_count: Characters in this request
            
        Raises:
            PolicyViolation: If rate limit exceeded
        """
        if not agent_id:
            return
        
        policy = self.get_policy(agent_id)
        record = self._get_or_create_record(agent_id)
        
        # Clean old timestamps
        now = time.time()
        cutoff = now - 60  # Last minute
        record.request_timestamps = [
            ts for ts in record.request_timestamps
            if ts > cutoff
        ]
        
        # Reset character count each minute
        if now - record.character_reset_time > 60:
            record.character_count = 0
            record.character_reset_time = now
        
        # Check request rate
        max_requests = int(
            policy.rate_limit.requests_per_minute *
            policy.rate_limit.burst_allowance
        )
        if len(record.request_timestamps) >= max_requests:
            self._record_violation(agent_id, "rate_limit")
            raise PolicyViolation(
                f"Rate limit exceeded: {max_requests} requests/minute",
                agent_id=agent_id,
                violation_type="rate_limit",
            )
        
        # Check character rate
        max_chars = int(
            policy.rate_limit.characters_per_minute *
            policy.rate_limit.burst_allowance
        )
        if record.character_count + character_count > max_chars:
            self._record_violation(agent_id, "rate_limit")
            raise PolicyViolation(
                f"Character rate limit exceeded: {max_chars} chars/minute",
                agent_id=agent_id,
                violation_type="rate_limit",
            )
    
    def check_concurrent_streams(
        self,
        agent_id: Optional[str],
    ) -> None:
        """
        Check concurrent stream limit.
        
        Args:
            agent_id: Agent identifier
            
        Raises:
            PolicyViolation: If limit exceeded
        """
        if not agent_id:
            return
        
        policy = self.get_policy(agent_id)
        record = self._get_or_create_record(agent_id)
        
        if record.active_streams >= policy.rate_limit.concurrent_streams:
            self._record_violation(agent_id, "concurrent_streams")
            raise PolicyViolation(
                f"Concurrent stream limit exceeded: {policy.rate_limit.concurrent_streams}",
                agent_id=agent_id,
                violation_type="concurrent_streams",
            )
    
    def record_request(
        self,
        agent_id: Optional[str],
        character_count: int = 0,
    ) -> None:
        """
        Record a request for rate limiting.
        
        Args:
            agent_id: Agent identifier
            character_count: Characters in request
        """
        if not agent_id:
            return
        
        record = self._get_or_create_record(agent_id)
        record.request_timestamps.append(time.time())
        record.character_count += character_count
    
    def record_stream_start(self, agent_id: Optional[str]) -> None:
        """Record stream start for concurrent limit tracking."""
        if agent_id:
            record = self._get_or_create_record(agent_id)
            record.active_streams += 1
    
    def record_stream_end(self, agent_id: Optional[str]) -> None:
        """Record stream end for concurrent limit tracking."""
        if agent_id:
            record = self._get_or_create_record(agent_id)
            record.active_streams = max(0, record.active_streams - 1)
    
    def _get_or_create_record(self, agent_id: str) -> AgentRecord:
        """Get or create agent record."""
        if agent_id not in self._agent_records:
            self._agent_records[agent_id] = AgentRecord(agent_id=agent_id)
        return self._agent_records[agent_id]
    
    def _record_violation(
        self,
        agent_id: Optional[str],
        violation_type: str,
    ) -> None:
        """Record a policy violation."""
        if agent_id:
            record = self._get_or_create_record(agent_id)
            record.violations += 1
        
        logger.warning(
            f"Policy violation: type={violation_type}, agent={agent_id}"
        )
    
    def get_agent_stats(
        self,
        agent_id: str,
    ) -> Dict[str, Any]:
        """
        Get statistics for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Statistics dictionary
        """
        record = self._agent_records.get(agent_id)
        if not record:
            return {}
        
        return {
            "agent_id": agent_id,
            "requests_last_minute": len(record.request_timestamps),
            "characters_last_minute": record.character_count,
            "active_streams": record.active_streams,
            "violations": record.violations,
        }
    
    def check_all(
        self,
        tool_name: str,
        agent_id: Optional[str],
        text: Optional[str] = None,
        voice: Optional[str] = None,
        backend: Optional[str] = None,
    ) -> None:
        """
        Run all policy checks for a request.
        
        Args:
            tool_name: Tool being called
            agent_id: Agent identifier
            text: Text to synthesize (optional)
            voice: Voice to use (optional)
            backend: Backend to use (optional)
            
        Raises:
            PolicyViolation: If any check fails
        """
        self.check_tool_access(tool_name, agent_id)
        
        if text:
            self.check_text_length(text, agent_id)
            self.check_rate_limit(agent_id, len(text))
        
        if voice:
            self.check_voice_access(voice, agent_id)
        
        if backend:
            self.check_backend_access(backend, agent_id)


def create_restricted_policy(
    allowed_tools: Optional[List[str]] = None,
    max_requests: int = 30,
    max_characters: int = 5000,
) -> MCPPolicy:
    """
    Create a restricted policy for untrusted agents.
    
    Args:
        allowed_tools: List of allowed tools
        max_requests: Max requests per minute
        max_characters: Max characters per minute
        
    Returns:
        Restricted MCPPolicy
    """
    return MCPPolicy(
        allow_tools=set(allowed_tools) if allowed_tools else {"voice.speak", "voice.list_voices"},
        capabilities=CapabilityFlags.BASIC,
        rate_limit=RateLimitConfig(
            requests_per_minute=max_requests,
            characters_per_minute=max_characters,
            concurrent_streams=1,
        ),
        allow_external_backends=False,
        max_text_length=1000,
    )


def create_trusted_policy() -> MCPPolicy:
    """
    Create a trusted policy for verified agents.
    
    Returns:
        Trusted MCPPolicy
    """
    return MCPPolicy(
        capabilities=CapabilityFlags.FULL,
        rate_limit=RateLimitConfig(
            requests_per_minute=120,
            characters_per_minute=50000,
            concurrent_streams=10,
        ),
        allow_external_backends=True,
        max_text_length=50000,
    )
