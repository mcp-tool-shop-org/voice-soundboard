"""
MCP Testing - Testing utilities for MCP-driven behavior.

Provides mock clients, deterministic test harnesses, and replayable
agent traces for testing MCP integrations.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from voice_soundboard.mcp.server import MCPRequest, MCPResponse


@dataclass
class MCPCallRecord:
    """
    Record of an MCP call for testing.
    
    Attributes:
        tool_name: Tool that was called
        arguments: Arguments passed
        result: Result returned
        error: Error if call failed
        timestamp: When call was made
        latency_ms: Call latency
        agent_id: Agent that made the call
        session_id: Session context
    """
    
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)
    latency_ms: float = 0.0
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    
    @property
    def success(self) -> bool:
        """Check if call was successful."""
        return self.error is None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
        }


@dataclass
class MockResponse:
    """Configuration for a mock response.
    
    Attributes:
        result: Result to return
        error: Error to return instead
        latency_ms: Simulated latency
        condition: Condition function for matching
    """
    
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    latency_ms: float = 10.0
    condition: Optional[Callable[[str, Dict[str, Any]], bool]] = None


class MCPMock:
    """
    Mock MCP client for testing.
    
    Records calls and allows configuring responses for testing
    code that uses MCP tools.
    
    Example:
        with MCPMock() as mcp:
            # Configure responses
            mcp.on("voice.speak").returns({"audio_path": "/tmp/test.wav"})
            
            # Code under test
            result = await my_agent.speak("Hello")
            
            # Assertions
            mcp.assert_called("voice.speak")
            mcp.assert_called_with("voice.speak", {"text": "Hello"})
    """
    
    def __init__(self):
        """Initialize mock."""
        self._calls: List[MCPCallRecord] = []
        self._responses: Dict[str, List[MockResponse]] = {}
        self._default_response = MockResponse(result={"status": "ok"})
        self._active = False
    
    def __enter__(self) -> "MCPMock":
        """Enter context manager."""
        self._active = True
        self._calls = []
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        self._active = False
    
    async def __aenter__(self) -> "MCPMock":
        """Async context manager entry."""
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        self.__exit__(exc_type, exc_val, exc_tb)
    
    def on(self, tool_name: str) -> "MockResponseBuilder":
        """
        Configure response for a tool.
        
        Args:
            tool_name: Tool name to configure
            
        Returns:
            MockResponseBuilder for fluent configuration
        """
        if tool_name not in self._responses:
            self._responses[tool_name] = []
        return MockResponseBuilder(self, tool_name)
    
    def _add_response(
        self,
        tool_name: str,
        response: MockResponse,
    ) -> None:
        """Add a response configuration."""
        if tool_name not in self._responses:
            self._responses[tool_name] = []
        self._responses[tool_name].append(response)
    
    async def call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Simulate a tool call.
        
        Args:
            tool_name: Tool to call
            arguments: Tool arguments
            agent_id: Agent making call
            session_id: Session context
            
        Returns:
            Mocked result
        """
        start_time = time.time()
        
        # Find matching response
        response = self._find_response(tool_name, arguments)
        
        # Simulate latency
        if response.latency_ms > 0:
            await asyncio.sleep(response.latency_ms / 1000)
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Record call
        record = MCPCallRecord(
            tool_name=tool_name,
            arguments=arguments,
            result=response.result if not response.error else None,
            error=response.error,
            latency_ms=latency_ms,
            agent_id=agent_id,
            session_id=session_id,
        )
        self._calls.append(record)
        
        # Return result
        if response.error:
            raise Exception(response.error.get("message", "Mock error"))
        
        return response.result or {}
    
    def call_sync(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Synchronous call for non-async tests.
        
        Args:
            tool_name: Tool to call
            arguments: Tool arguments
            
        Returns:
            Mocked result
        """
        return asyncio.get_event_loop().run_until_complete(
            self.call(tool_name, arguments, **kwargs)
        )
    
    def _find_response(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> MockResponse:
        """Find matching response configuration."""
        responses = self._responses.get(tool_name, [])
        
        for response in responses:
            if response.condition is None:
                return response
            if response.condition(tool_name, arguments):
                return response
        
        return self._default_response
    
    @property
    def calls(self) -> List[MCPCallRecord]:
        """Get all recorded calls."""
        return self._calls.copy()
    
    def get_calls(self, tool_name: Optional[str] = None) -> List[MCPCallRecord]:
        """
        Get recorded calls, optionally filtered by tool.
        
        Args:
            tool_name: Filter by tool name
            
        Returns:
            List of call records
        """
        if tool_name is None:
            return self._calls.copy()
        return [c for c in self._calls if c.tool_name == tool_name]
    
    def assert_called(self, tool_name: str) -> None:
        """
        Assert that a tool was called.
        
        Args:
            tool_name: Tool name
            
        Raises:
            AssertionError: If tool was not called
        """
        calls = self.get_calls(tool_name)
        if not calls:
            raise AssertionError(
                f"Tool '{tool_name}' was not called. "
                f"Calls: {[c.tool_name for c in self._calls]}"
            )
    
    def assert_not_called(self, tool_name: str) -> None:
        """
        Assert that a tool was not called.
        
        Args:
            tool_name: Tool name
            
        Raises:
            AssertionError: If tool was called
        """
        calls = self.get_calls(tool_name)
        if calls:
            raise AssertionError(
                f"Tool '{tool_name}' was called {len(calls)} time(s)"
            )
    
    def assert_called_with(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> None:
        """
        Assert that a tool was called with specific arguments.
        
        Args:
            tool_name: Tool name
            arguments: Expected arguments (partial match)
            
        Raises:
            AssertionError: If no matching call found
        """
        calls = self.get_calls(tool_name)
        if not calls:
            raise AssertionError(f"Tool '{tool_name}' was not called")
        
        for call in calls:
            if self._arguments_match(call.arguments, arguments):
                return
        
        raise AssertionError(
            f"Tool '{tool_name}' was not called with arguments {arguments}. "
            f"Actual calls: {[c.arguments for c in calls]}"
        )
    
    def assert_call_count(self, tool_name: str, count: int) -> None:
        """
        Assert call count for a tool.
        
        Args:
            tool_name: Tool name
            count: Expected count
            
        Raises:
            AssertionError: If count doesn't match
        """
        actual = len(self.get_calls(tool_name))
        if actual != count:
            raise AssertionError(
                f"Tool '{tool_name}' called {actual} time(s), expected {count}"
            )
    
    def _arguments_match(
        self,
        actual: Dict[str, Any],
        expected: Dict[str, Any],
    ) -> bool:
        """Check if actual arguments match expected (partial)."""
        for key, value in expected.items():
            if key not in actual:
                return False
            if actual[key] != value:
                return False
        return True
    
    def reset(self) -> None:
        """Reset all recorded calls and responses."""
        self._calls = []
        self._responses = {}


class MockResponseBuilder:
    """
    Builder for configuring mock responses.
    
    Example:
        mcp.on("voice.speak").returns({"audio_path": "/tmp/test.wav"})
        mcp.on("voice.speak").raises({"code": -1, "message": "Error"})
        mcp.on("voice.speak").when(lambda t, a: a.get("text") == "fail").raises(error)
    """
    
    def __init__(self, mock: MCPMock, tool_name: str):
        """Initialize builder."""
        self._mock = mock
        self._tool_name = tool_name
        self._condition: Optional[Callable] = None
    
    def when(
        self,
        condition: Callable[[str, Dict[str, Any]], bool],
    ) -> "MockResponseBuilder":
        """
        Add condition for when this response applies.
        
        Args:
            condition: Function(tool_name, arguments) -> bool
            
        Returns:
            Self for chaining
        """
        self._condition = condition
        return self
    
    def returns(
        self,
        result: Any,
        latency_ms: float = 10.0,
    ) -> None:
        """
        Configure successful response.
        
        Args:
            result: Result to return
            latency_ms: Simulated latency
        """
        self._mock._add_response(
            self._tool_name,
            MockResponse(
                result=result,
                latency_ms=latency_ms,
                condition=self._condition,
            ),
        )
    
    def raises(
        self,
        error: Union[str, Dict[str, Any]],
        latency_ms: float = 10.0,
    ) -> None:
        """
        Configure error response.
        
        Args:
            error: Error message or dict
            latency_ms: Simulated latency
        """
        if isinstance(error, str):
            error = {"code": -1, "message": error}
        
        self._mock._add_response(
            self._tool_name,
            MockResponse(
                error=error,
                latency_ms=latency_ms,
                condition=self._condition,
            ),
        )


@dataclass
class TraceEvent:
    """Event in an agent trace.
    
    Attributes:
        event_type: Type of event
        data: Event data
        timestamp: Event timestamp
    """
    
    event_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class MCPTestHarness:
    """
    Deterministic test harness for MCP behavior.
    
    Enables recording and replaying agent traces for reproducible testing.
    
    Example:
        harness = MCPTestHarness()
        
        # Record a trace
        with harness.record() as trace:
            await agent.run()
        
        # Replay the trace
        with harness.replay(trace):
            await agent.run()  # Same behavior
    """
    
    def __init__(self):
        """Initialize test harness."""
        self._traces: Dict[str, List[TraceEvent]] = {}
        self._current_trace: Optional[str] = None
        self._recording = False
        self._replaying = False
        self._replay_index = 0
    
    def record(self, trace_name: Optional[str] = None) -> "TraceRecorder":
        """
        Start recording a trace.
        
        Args:
            trace_name: Name for the trace
            
        Returns:
            TraceRecorder context manager
        """
        trace_name = trace_name or str(uuid.uuid4())
        return TraceRecorder(self, trace_name)
    
    def replay(
        self,
        trace: Union[str, List[TraceEvent]],
    ) -> "TraceReplayer":
        """
        Start replaying a trace.
        
        Args:
            trace: Trace name or event list
            
        Returns:
            TraceReplayer context manager
        """
        if isinstance(trace, str):
            events = self._traces.get(trace, [])
        else:
            events = trace
        
        return TraceReplayer(self, events)
    
    def get_trace(self, name: str) -> List[TraceEvent]:
        """
        Get a recorded trace.
        
        Args:
            name: Trace name
            
        Returns:
            List of trace events
        """
        return self._traces.get(name, [])
    
    def save_trace(
        self,
        name: str,
        path: str,
    ) -> None:
        """
        Save a trace to file.
        
        Args:
            name: Trace name
            path: File path
        """
        events = self._traces.get(name, [])
        data = [
            {
                "event_type": e.event_type,
                "data": e.data,
                "timestamp": e.timestamp,
            }
            for e in events
        ]
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def load_trace(self, path: str) -> List[TraceEvent]:
        """
        Load a trace from file.
        
        Args:
            path: File path
            
        Returns:
            List of trace events
        """
        with open(path, "r") as f:
            data = json.load(f)
        
        return [
            TraceEvent(
                event_type=e["event_type"],
                data=e["data"],
                timestamp=e["timestamp"],
            )
            for e in data
        ]
    
    def _start_recording(self, name: str) -> None:
        """Start recording a trace."""
        self._current_trace = name
        self._traces[name] = []
        self._recording = True
    
    def _stop_recording(self) -> None:
        """Stop recording."""
        self._recording = False
        self._current_trace = None
    
    def _record_event(
        self,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Record an event."""
        if self._recording and self._current_trace:
            self._traces[self._current_trace].append(
                TraceEvent(event_type=event_type, data=data)
            )
    
    def _start_replay(self, events: List[TraceEvent]) -> None:
        """Start replaying."""
        self._replaying = True
        self._replay_events = events
        self._replay_index = 0
    
    def _stop_replay(self) -> None:
        """Stop replaying."""
        self._replaying = False
        self._replay_events = []
        self._replay_index = 0
    
    def _get_next_event(self) -> Optional[TraceEvent]:
        """Get next replay event."""
        if not self._replaying:
            return None
        if self._replay_index >= len(self._replay_events):
            return None
        
        event = self._replay_events[self._replay_index]
        self._replay_index += 1
        return event


class TraceRecorder:
    """Context manager for recording traces."""
    
    def __init__(self, harness: MCPTestHarness, name: str):
        """Initialize recorder."""
        self._harness = harness
        self._name = name
    
    def __enter__(self) -> "TraceRecorder":
        """Start recording."""
        self._harness._start_recording(self._name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop recording."""
        self._harness._stop_recording()
    
    async def __aenter__(self) -> "TraceRecorder":
        """Async start recording."""
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async stop recording."""
        self.__exit__(exc_type, exc_val, exc_tb)
    
    def record(self, event_type: str, data: Dict[str, Any]) -> None:
        """Record an event manually."""
        self._harness._record_event(event_type, data)


class TraceReplayer:
    """Context manager for replaying traces."""
    
    def __init__(
        self,
        harness: MCPTestHarness,
        events: List[TraceEvent],
    ):
        """Initialize replayer."""
        self._harness = harness
        self._events = events
    
    def __enter__(self) -> "TraceReplayer":
        """Start replaying."""
        self._harness._start_replay(self._events)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop replaying."""
        self._harness._stop_replay()
    
    async def __aenter__(self) -> "TraceReplayer":
        """Async start replaying."""
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async stop replaying."""
        self.__exit__(exc_type, exc_val, exc_tb)
    
    def next_event(self) -> Optional[TraceEvent]:
        """Get next event in replay."""
        return self._harness._get_next_event()
