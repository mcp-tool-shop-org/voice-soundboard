"""
MCP Integration Module - Model Context Protocol support for Voice Soundboard.

v2.5 introduces MCP integration, making Voice Soundboard a first-class,
agent-native capability. This module provides:

Server & Tools (P0):
    MCPServer           - Embedded MCP-compliant server
    create_mcp_server   - Factory function for server creation
    
Tools (P0):
    SpeakTool           - Synthesize speech (voice.speak)
    StreamTool          - Streaming synthesis (voice.stream)
    InterruptTool       - Stop/rollback audio (voice.interrupt)
    ListVoicesTool      - Enumerate voices (voice.list_voices)
    StatusTool          - Engine health (voice.status)
    
Sessions (P0):
    MCPSession          - Agent-aware audio session
    SessionManager      - Session lifecycle management
    SessionConfig       - Session configuration
    
Interrupts (P1):
    InterruptReason     - Reason codes for interruption
    InterruptHandler    - Handles graceful interrupts
    InterruptEvent      - Structured interrupt events

Observability (P1):
    SynthesisMetadata   - Structured output metadata
    MetadataCollector   - Collects synthesis metrics
    
Policy (P2):
    MCPPolicy           - Permissions and safety model
    PolicyEnforcer      - Enforces policies
    CapabilityFlags     - Capability flags for agents

Testing (P2):
    MCPMock             - Mock MCP client for testing
    MCPTestHarness      - Deterministic test harness

Example:
    from voice_soundboard.mcp import MCPServer, create_mcp_server
    
    # Create and run MCP server
    server = create_mcp_server(engine)
    await server.run()
    
    # Agent calls
    result = await server.call("voice.speak", {"text": "Hello!"})
"""

from voice_soundboard.mcp.server import (
    MCPServer,
    MCPConfig,
    create_mcp_server,
)
from voice_soundboard.mcp.tools import (
    MCPTool,
    SpeakTool,
    StreamTool,
    InterruptTool,
    ListVoicesTool,
    StatusTool,
    ToolRegistry,
)
from voice_soundboard.mcp.sessions import (
    MCPSession,
    SessionManager,
    SessionConfig,
    SessionState,
)
from voice_soundboard.mcp.interrupts import (
    InterruptReason,
    InterruptHandler,
    InterruptEvent,
    InterruptConfig,
)
from voice_soundboard.mcp.observability import (
    SynthesisMetadata,
    MetadataCollector,
    MetadataConfig,
)
from voice_soundboard.mcp.policy import (
    MCPPolicy,
    PolicyEnforcer,
    CapabilityFlags,
    PolicyViolation,
)
from voice_soundboard.mcp.testing import (
    MCPMock,
    MCPTestHarness,
    MCPCallRecord,
)

__all__ = [
    # Server
    "MCPServer",
    "MCPConfig",
    "create_mcp_server",
    # Tools
    "MCPTool",
    "SpeakTool",
    "StreamTool",
    "InterruptTool",
    "ListVoicesTool",
    "StatusTool",
    "ToolRegistry",
    # Sessions
    "MCPSession",
    "SessionManager",
    "SessionConfig",
    "SessionState",
    # Interrupts
    "InterruptReason",
    "InterruptHandler",
    "InterruptEvent",
    "InterruptConfig",
    # Observability
    "SynthesisMetadata",
    "MetadataCollector",
    "MetadataConfig",
    # Policy
    "MCPPolicy",
    "PolicyEnforcer",
    "CapabilityFlags",
    "PolicyViolation",
    # Testing
    "MCPMock",
    "MCPTestHarness",
    "MCPCallRecord",
]
