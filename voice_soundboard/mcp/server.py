"""
MCP Server - Model Context Protocol server for Voice Soundboard.

Provides an embedded MCP-compliant server that exposes Voice Soundboard
as a tool provider for AI agents.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from voice_soundboard.adapters import VoiceEngine
    from voice_soundboard.mcp.tools import MCPTool, ToolRegistry
    from voice_soundboard.mcp.sessions import SessionManager
    from voice_soundboard.mcp.policy import PolicyEnforcer

logger = logging.getLogger(__name__)


class ServerState(Enum):
    """MCP server states."""
    
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class MCPConfig:
    """Configuration for MCP server.
    
    Attributes:
        host: Server host address
        port: Server port
        name: Server name for discovery
        version: Server version string
        max_concurrent_requests: Maximum concurrent requests
        request_timeout: Request timeout in seconds
        enable_streaming: Enable streaming tool support
        enable_sessions: Enable session management
        enable_policy: Enable policy enforcement
        metadata: Additional server metadata
    """
    
    host: str = "localhost"
    port: int = 8765
    name: str = "voice-soundboard"
    version: str = "2.5.0"
    max_concurrent_requests: int = 100
    request_timeout: float = 30.0
    enable_streaming: bool = True
    enable_sessions: bool = True
    enable_policy: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPRequest:
    """Represents an MCP request.
    
    Attributes:
        id: Unique request identifier
        method: Method being called
        params: Method parameters
        agent_id: Agent making the request
        session_id: Session context
        timestamp: Request timestamp
    """
    
    id: str
    method: str
    params: Dict[str, Any]
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class MCPResponse:
    """Represents an MCP response.
    
    Attributes:
        id: Request ID this responds to
        result: Result data
        error: Error information if failed
        metadata: Response metadata
    """
    
    id: str
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """Check if response is successful."""
        return self.error is None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {"id": self.id}
        if self.error:
            data["error"] = self.error
        else:
            data["result"] = self.result
        if self.metadata:
            data["metadata"] = self.metadata
        return data


class MCPServer:
    """
    Model Context Protocol server for Voice Soundboard.
    
    Exposes Voice Soundboard capabilities as MCP-compliant tools
    for AI agents to consume.
    
    Example:
        engine = VoiceEngine()
        server = MCPServer(engine)
        
        # Register tools
        server.register_tool(SpeakTool())
        server.register_tool(StreamTool())
        
        # Start server
        await server.start()
        
        # Handle requests
        result = await server.call("voice.speak", {"text": "Hello"})
    """
    
    def __init__(
        self,
        engine: "VoiceEngine",
        config: Optional[MCPConfig] = None,
        tool_registry: Optional["ToolRegistry"] = None,
        session_manager: Optional["SessionManager"] = None,
        policy_enforcer: Optional["PolicyEnforcer"] = None,
    ):
        """
        Initialize MCP server.
        
        Args:
            engine: Voice engine instance
            config: Server configuration
            tool_registry: Tool registry for tool management
            session_manager: Session manager for sessions
            policy_enforcer: Policy enforcer for permissions
        """
        self.engine = engine
        self.config = config or MCPConfig()
        self._tool_registry = tool_registry
        self._session_manager = session_manager
        self._policy_enforcer = policy_enforcer
        
        self._state = ServerState.INITIALIZING
        self._server = None
        self._active_requests: Dict[str, MCPRequest] = {}
        self._request_semaphore: Optional[asyncio.Semaphore] = None
        self._handlers: Dict[str, Callable] = {}
        self._event_listeners: List[Callable] = []
        
        self._setup_default_handlers()
    
    @property
    def state(self) -> ServerState:
        """Get current server state."""
        return self._state
    
    @property
    def tools(self) -> List[str]:
        """Get list of registered tools."""
        if self._tool_registry:
            return list(self._tool_registry.list_tools().keys())
        return []
    
    def _setup_default_handlers(self) -> None:
        """Set up default protocol handlers."""
        self._handlers["initialize"] = self._handle_initialize
        self._handlers["tools/list"] = self._handle_list_tools
        self._handlers["tools/call"] = self._handle_call_tool
        self._handlers["ping"] = self._handle_ping
        self._handlers["shutdown"] = self._handle_shutdown
    
    async def _handle_initialize(
        self,
        request: MCPRequest,
    ) -> Dict[str, Any]:
        """Handle initialization request."""
        return {
            "protocolVersion": "1.0",
            "serverInfo": {
                "name": self.config.name,
                "version": self.config.version,
            },
            "capabilities": {
                "tools": True,
                "streaming": self.config.enable_streaming,
                "sessions": self.config.enable_sessions,
            },
        }
    
    async def _handle_list_tools(
        self,
        request: MCPRequest,
    ) -> Dict[str, Any]:
        """Handle tool listing request."""
        tools = []
        
        if self._tool_registry:
            for name, tool in self._tool_registry.list_tools().items():
                tools.append({
                    "name": name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                })
        
        return {"tools": tools}
    
    async def _handle_call_tool(
        self,
        request: MCPRequest,
    ) -> Dict[str, Any]:
        """Handle tool call request."""
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        
        if not tool_name:
            raise ValueError("Tool name required")
        
        # Check policy if enabled
        if self.config.enable_policy and self._policy_enforcer:
            self._policy_enforcer.check_tool_access(
                tool_name,
                request.agent_id,
            )
        
        # Get tool from registry
        if not self._tool_registry:
            raise ValueError("No tool registry configured")
        
        tool = self._tool_registry.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        # Get or create session
        session = None
        if self.config.enable_sessions and self._session_manager:
            session = self._session_manager.get_or_create_session(
                request.session_id or request.agent_id,
                request.agent_id,
            )
        
        # Execute tool
        start_time = time.time()
        result = await tool.execute(
            self.engine,
            arguments,
            session=session,
        )
        latency_ms = (time.time() - start_time) * 1000
        
        # Add metadata
        result["_metadata"] = {
            "latency_ms": round(latency_ms, 2),
            "tool": tool_name,
            "session_id": session.session_id if session else None,
        }
        
        return result
    
    async def _handle_ping(
        self,
        request: MCPRequest,
    ) -> Dict[str, Any]:
        """Handle ping request."""
        return {"pong": True, "timestamp": time.time()}
    
    async def _handle_shutdown(
        self,
        request: MCPRequest,
    ) -> Dict[str, Any]:
        """Handle shutdown request."""
        asyncio.create_task(self.stop())
        return {"status": "shutting_down"}
    
    def register_tool(self, tool: "MCPTool") -> None:
        """
        Register a tool with the server.
        
        Args:
            tool: Tool to register
        """
        if self._tool_registry:
            self._tool_registry.register(tool)
        else:
            logger.warning("No tool registry configured")
    
    def on_event(self, callback: Callable) -> None:
        """
        Register an event listener.
        
        Args:
            callback: Callback function for events
        """
        self._event_listeners.append(callback)
    
    async def _emit_event(self, event_type: str, data: Any) -> None:
        """Emit an event to listeners."""
        for listener in self._event_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event_type, data)
                else:
                    listener(event_type, data)
            except Exception as e:
                logger.error(f"Event listener error: {e}")
    
    async def call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> MCPResponse:
        """
        Call a tool directly.
        
        Args:
            tool_name: Name of tool to call
            arguments: Tool arguments
            agent_id: Agent making the call
            session_id: Session context
            
        Returns:
            MCPResponse with result or error
        """
        request = MCPRequest(
            id=str(uuid.uuid4()),
            method="tools/call",
            params={"name": tool_name, "arguments": arguments},
            agent_id=agent_id,
            session_id=session_id,
        )
        
        return await self._process_request(request)
    
    async def _process_request(
        self,
        request: MCPRequest,
    ) -> MCPResponse:
        """Process an MCP request."""
        # Check concurrency limit
        if self._request_semaphore:
            async with self._request_semaphore:
                return await self._execute_request(request)
        else:
            return await self._execute_request(request)
    
    async def _execute_request(
        self,
        request: MCPRequest,
    ) -> MCPResponse:
        """Execute a request."""
        self._active_requests[request.id] = request
        
        try:
            # Find handler
            handler = self._handlers.get(request.method)
            if not handler:
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32601,
                        "message": f"Unknown method: {request.method}",
                    },
                )
            
            # Execute with timeout
            try:
                result = await asyncio.wait_for(
                    handler(request),
                    timeout=self.config.request_timeout,
                )
                return MCPResponse(id=request.id, result=result)
            except asyncio.TimeoutError:
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32000,
                        "message": "Request timeout",
                    },
                )
            except Exception as e:
                logger.error(f"Request error: {e}")
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32603,
                        "message": str(e),
                    },
                )
        finally:
            self._active_requests.pop(request.id, None)
    
    async def start(self) -> None:
        """Start the MCP server."""
        if self._state not in (ServerState.INITIALIZING, ServerState.STOPPED):
            raise RuntimeError(f"Cannot start from state: {self._state}")
        
        self._state = ServerState.READY
        self._request_semaphore = asyncio.Semaphore(
            self.config.max_concurrent_requests
        )
        
        logger.info(
            f"MCP server '{self.config.name}' ready on "
            f"{self.config.host}:{self.config.port}"
        )
        
        await self._emit_event("server_started", {
            "host": self.config.host,
            "port": self.config.port,
        })
        
        self._state = ServerState.RUNNING
    
    async def run(self) -> None:
        """Run the server (blocking)."""
        await self.start()
        
        # Start WebSocket server for external connections
        try:
            import websockets
            
            async with websockets.serve(
                self._handle_websocket,
                self.config.host,
                self.config.port,
            ):
                logger.info(f"WebSocket server running on {self.config.host}:{self.config.port}")
                await asyncio.Future()  # Run forever
        except ImportError:
            logger.warning("websockets not installed, running without WebSocket support")
            await asyncio.Future()
    
    async def _handle_websocket(self, websocket, path: str) -> None:
        """Handle WebSocket connections."""
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    request = MCPRequest(
                        id=data.get("id", str(uuid.uuid4())),
                        method=data.get("method", ""),
                        params=data.get("params", {}),
                        agent_id=data.get("agent_id"),
                        session_id=data.get("session_id"),
                    )
                    
                    response = await self._process_request(request)
                    await websocket.send(json.dumps(response.to_dict()))
                    
                except json.JSONDecodeError as e:
                    await websocket.send(json.dumps({
                        "error": {"code": -32700, "message": f"Parse error: {e}"}
                    }))
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    async def stop(self) -> None:
        """Stop the MCP server."""
        if self._state == ServerState.STOPPED:
            return
        
        self._state = ServerState.STOPPING
        
        # Cancel active requests
        for request_id in list(self._active_requests.keys()):
            logger.warning(f"Cancelling request: {request_id}")
        
        await self._emit_event("server_stopped", {})
        
        self._state = ServerState.STOPPED
        logger.info("MCP server stopped")
    
    def get_info(self) -> Dict[str, Any]:
        """Get server information."""
        return {
            "name": self.config.name,
            "version": self.config.version,
            "state": self._state.value,
            "tools": self.tools,
            "active_requests": len(self._active_requests),
            "capabilities": {
                "streaming": self.config.enable_streaming,
                "sessions": self.config.enable_sessions,
                "policy": self.config.enable_policy,
            },
        }


def create_mcp_server(
    engine: "VoiceEngine",
    config: Optional[MCPConfig] = None,
    register_default_tools: bool = True,
) -> MCPServer:
    """
    Factory function to create a configured MCP server.
    
    Args:
        engine: Voice engine instance
        config: Server configuration
        register_default_tools: Whether to register default tools
        
    Returns:
        Configured MCPServer instance
        
    Example:
        engine = VoiceEngine()
        server = create_mcp_server(engine)
        await server.run()
    """
    from voice_soundboard.mcp.tools import ToolRegistry, create_default_tools
    from voice_soundboard.mcp.sessions import SessionManager
    from voice_soundboard.mcp.policy import PolicyEnforcer, MCPPolicy
    
    config = config or MCPConfig()
    
    # Create components
    tool_registry = ToolRegistry()
    session_manager = SessionManager() if config.enable_sessions else None
    policy_enforcer = PolicyEnforcer(MCPPolicy()) if config.enable_policy else None
    
    # Create server
    server = MCPServer(
        engine=engine,
        config=config,
        tool_registry=tool_registry,
        session_manager=session_manager,
        policy_enforcer=policy_enforcer,
    )
    
    # Register default tools
    if register_default_tools:
        for tool in create_default_tools():
            server.register_tool(tool)
    
    return server
