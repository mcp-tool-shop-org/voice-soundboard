"""
MCP Tools - Tool definitions for Voice Soundboard MCP integration.

Provides standardized tool interfaces for speech synthesis that AI agents
can discover and invoke through the Model Context Protocol.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from voice_soundboard.adapters import VoiceEngine
    from voice_soundboard.mcp.sessions import MCPSession


class ToolCategory(Enum):
    """Categories of MCP tools."""
    
    SYNTHESIS = "synthesis"
    CONTROL = "control"
    QUERY = "query"
    ADMIN = "admin"


@dataclass
class ToolSchema:
    """JSON Schema for tool input/output."""
    
    type: str = "object"
    properties: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "properties": self.properties,
            "required": self.required,
        }


class MCPTool(ABC):
    """
    Base class for MCP tools.
    
    All tools must implement:
    - name: Tool name (e.g., "voice.speak")
    - description: Human-readable description
    - input_schema: JSON schema for inputs
    - execute(): Async execution method
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (e.g., 'voice.speak')."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""
        pass
    
    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """JSON schema for tool inputs."""
        pass
    
    @property
    def category(self) -> ToolCategory:
        """Tool category."""
        return ToolCategory.SYNTHESIS
    
    @property
    def streaming(self) -> bool:
        """Whether tool supports streaming."""
        return False
    
    @property
    def interruptible(self) -> bool:
        """Whether tool execution can be interrupted."""
        return True
    
    @abstractmethod
    async def execute(
        self,
        engine: "VoiceEngine",
        arguments: Dict[str, Any],
        session: Optional["MCPSession"] = None,
    ) -> Dict[str, Any]:
        """
        Execute the tool.
        
        Args:
            engine: Voice engine instance
            arguments: Tool arguments
            session: Optional session context
            
        Returns:
            Result dictionary
        """
        pass
    
    def validate_arguments(self, arguments: Dict[str, Any]) -> None:
        """
        Validate tool arguments against schema.
        
        Args:
            arguments: Arguments to validate
            
        Raises:
            ValueError: If validation fails
        """
        schema = self.input_schema
        required = schema.get("required", [])
        
        for field_name in required:
            if field_name not in arguments:
                raise ValueError(f"Missing required argument: {field_name}")
        
        properties = schema.get("properties", {})
        for key, value in arguments.items():
            if key in properties:
                prop_schema = properties[key]
                expected_type = prop_schema.get("type")
                
                # Basic type checking
                type_map = {
                    "string": str,
                    "number": (int, float),
                    "integer": int,
                    "boolean": bool,
                    "array": list,
                    "object": dict,
                }
                
                if expected_type in type_map:
                    expected = type_map[expected_type]
                    if not isinstance(value, expected):
                        raise ValueError(
                            f"Argument '{key}' must be {expected_type}, "
                            f"got {type(value).__name__}"
                        )


class SpeakTool(MCPTool):
    """
    Tool for synthesizing speech.
    
    Synthesizes text to speech and returns audio data or path.
    
    Example:
        result = await tool.execute(engine, {
            "text": "Hello, world!",
            "voice": "af_bella",
            "emotion": "joy",
        })
    """
    
    @property
    def name(self) -> str:
        return "voice.speak"
    
    @property
    def description(self) -> str:
        return "Synthesize expressive speech from text"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to synthesize",
                },
                "voice": {
                    "type": "string",
                    "description": "Voice identifier",
                },
                "emotion": {
                    "type": "string",
                    "description": "Emotion to apply (joy, sadness, anger, etc.)",
                    "enum": ["joy", "sadness", "anger", "fear", "surprise", "neutral"],
                },
                "speed": {
                    "type": "number",
                    "description": "Speed multiplier (0.5 to 2.0)",
                    "minimum": 0.5,
                    "maximum": 2.0,
                },
                "pitch": {
                    "type": "number",
                    "description": "Pitch multiplier (0.5 to 2.0)",
                    "minimum": 0.5,
                    "maximum": 2.0,
                },
                "interruptible": {
                    "type": "boolean",
                    "description": "Whether synthesis can be interrupted",
                    "default": True,
                },
                "output_format": {
                    "type": "string",
                    "description": "Output audio format",
                    "enum": ["wav", "mp3", "ogg", "raw"],
                    "default": "wav",
                },
            },
            "required": ["text"],
        }
    
    async def execute(
        self,
        engine: "VoiceEngine",
        arguments: Dict[str, Any],
        session: Optional["MCPSession"] = None,
    ) -> Dict[str, Any]:
        """Execute speech synthesis."""
        self.validate_arguments(arguments)
        
        text = arguments["text"]
        voice = arguments.get("voice")
        emotion = arguments.get("emotion")
        speed = arguments.get("speed", 1.0)
        pitch = arguments.get("pitch", 1.0)
        
        # Build synthesis parameters
        params = {}
        if voice:
            params["voice"] = voice
        if speed != 1.0:
            params["speed"] = speed
        if pitch != 1.0:
            params["pitch"] = pitch
        
        # Record start time for metadata
        start_time = time.time()
        
        # Perform synthesis
        result = engine.speak(text, **params)
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Build response with observability metadata
        return {
            "audio_path": str(result.audio_path) if result.audio_path else None,
            "duration_ms": result.duration * 1000 if hasattr(result, "duration") else None,
            "text": text,
            "voice": voice or engine.config.default_voice if hasattr(engine, "config") else None,
            "emotion": emotion,
            "latency_ms": round(latency_ms, 2),
            "backend": getattr(engine, "_backend_name", "unknown"),
            "cost_estimate": 0.0,  # Local synthesis is free
            "cache_hit": False,
        }


class StreamTool(MCPTool):
    """
    Tool for incremental/streaming synthesis.
    
    Streams audio chunks as they are generated, enabling
    low-latency audio playback.
    """
    
    @property
    def name(self) -> str:
        return "voice.stream"
    
    @property
    def description(self) -> str:
        return "Stream speech synthesis incrementally"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to synthesize",
                },
                "voice": {
                    "type": "string",
                    "description": "Voice identifier",
                },
                "chunk_size_ms": {
                    "type": "integer",
                    "description": "Chunk size in milliseconds",
                    "default": 100,
                },
                "interruptible": {
                    "type": "boolean",
                    "description": "Whether stream can be interrupted",
                    "default": True,
                },
            },
            "required": ["text"],
        }
    
    @property
    def streaming(self) -> bool:
        return True
    
    async def execute(
        self,
        engine: "VoiceEngine",
        arguments: Dict[str, Any],
        session: Optional["MCPSession"] = None,
    ) -> Dict[str, Any]:
        """Execute streaming synthesis."""
        self.validate_arguments(arguments)
        
        text = arguments["text"]
        voice = arguments.get("voice")
        chunk_size_ms = arguments.get("chunk_size_ms", 100)
        
        # Generate stream ID for tracking
        stream_id = str(uuid.uuid4())
        
        # Register stream with session if available
        if session:
            session.register_stream(stream_id)
        
        start_time = time.time()
        
        # Check if engine supports streaming
        if hasattr(engine, "stream"):
            # Use streaming API
            chunks_sent = 0
            total_duration_ms = 0
            
            async for chunk in engine.stream(text, voice=voice):
                chunks_sent += 1
                total_duration_ms += chunk_size_ms
                
                # Check for interruption
                if session and session.is_interrupted(stream_id):
                    break
            
            latency_ms = (time.time() - start_time) * 1000
            
            return {
                "stream_id": stream_id,
                "status": "completed",
                "chunks_sent": chunks_sent,
                "duration_ms": total_duration_ms,
                "latency_ms": round(latency_ms, 2),
                "interrupted": session.is_interrupted(stream_id) if session else False,
            }
        else:
            # Fallback to non-streaming synthesis
            result = engine.speak(text, voice=voice)
            latency_ms = (time.time() - start_time) * 1000
            
            return {
                "stream_id": stream_id,
                "status": "completed",
                "audio_path": str(result.audio_path) if result.audio_path else None,
                "duration_ms": result.duration * 1000 if hasattr(result, "duration") else None,
                "latency_ms": round(latency_ms, 2),
                "streaming_supported": False,
            }


class InterruptTool(MCPTool):
    """
    Tool for interrupting active audio.
    
    Stops or rolls back active synthesis with structured
    interrupt acknowledgements.
    """
    
    @property
    def name(self) -> str:
        return "voice.interrupt"
    
    @property
    def description(self) -> str:
        return "Stop or rollback active audio synthesis"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "stream_id": {
                    "type": "string",
                    "description": "Stream ID to interrupt (optional, interrupts all if not specified)",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for interruption",
                    "enum": ["user_spoke", "context_change", "timeout", "manual"],
                    "default": "manual",
                },
                "fade_out_ms": {
                    "type": "integer",
                    "description": "Fade out duration in milliseconds",
                    "default": 50,
                },
            },
            "required": [],
        }
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CONTROL
    
    @property
    def interruptible(self) -> bool:
        return False  # Interrupt itself cannot be interrupted
    
    async def execute(
        self,
        engine: "VoiceEngine",
        arguments: Dict[str, Any],
        session: Optional["MCPSession"] = None,
    ) -> Dict[str, Any]:
        """Execute interruption."""
        stream_id = arguments.get("stream_id")
        reason = arguments.get("reason", "manual")
        fade_out_ms = arguments.get("fade_out_ms", 50)
        
        audio_ms_played = 0
        streams_interrupted = 0
        
        if session:
            if stream_id:
                # Interrupt specific stream
                audio_ms_played = session.interrupt_stream(
                    stream_id,
                    reason=reason,
                    fade_out_ms=fade_out_ms,
                )
                streams_interrupted = 1
            else:
                # Interrupt all streams
                streams_interrupted = session.interrupt_all(
                    reason=reason,
                    fade_out_ms=fade_out_ms,
                )
        
        return {
            "event": "voice.interrupted",
            "reason": reason,
            "stream_id": stream_id,
            "audio_ms_played": audio_ms_played,
            "streams_interrupted": streams_interrupted,
            "fade_out_ms": fade_out_ms,
        }


class ListVoicesTool(MCPTool):
    """
    Tool for enumerating available voices.
    
    Returns a list of voices with their metadata.
    """
    
    @property
    def name(self) -> str:
        return "voice.list_voices"
    
    @property
    def description(self) -> str:
        return "Enumerate available voices"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "description": "Filter by language code (e.g., 'en', 'es')",
                },
                "gender": {
                    "type": "string",
                    "description": "Filter by gender",
                    "enum": ["male", "female", "neutral"],
                },
                "backend": {
                    "type": "string",
                    "description": "Filter by backend",
                },
            },
            "required": [],
        }
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.QUERY
    
    async def execute(
        self,
        engine: "VoiceEngine",
        arguments: Dict[str, Any],
        session: Optional["MCPSession"] = None,
    ) -> Dict[str, Any]:
        """List available voices."""
        language = arguments.get("language")
        gender = arguments.get("gender")
        backend = arguments.get("backend")
        
        # Get voices from engine
        voices = []
        
        if hasattr(engine, "list_voices"):
            all_voices = engine.list_voices()
            
            for voice in all_voices:
                # Apply filters
                if language and voice.get("language", "").startswith(language):
                    continue
                if gender and voice.get("gender") != gender:
                    continue
                if backend and voice.get("backend") != backend:
                    continue
                
                voices.append(voice)
        else:
            # Default voices if engine doesn't support listing
            voices = [
                {
                    "id": "af_bella",
                    "name": "Bella",
                    "language": "en-US",
                    "gender": "female",
                    "backend": "kokoro",
                    "styles": ["conversational", "news"],
                },
                {
                    "id": "am_adam",
                    "name": "Adam",
                    "language": "en-US",
                    "gender": "male",
                    "backend": "kokoro",
                    "styles": ["conversational", "news"],
                },
            ]
        
        return {
            "voices": voices,
            "count": len(voices),
        }


class StatusTool(MCPTool):
    """
    Tool for checking engine health and capabilities.
    
    Returns engine status, health, and available capabilities.
    """
    
    @property
    def name(self) -> str:
        return "voice.status"
    
    @property
    def description(self) -> str:
        return "Get engine health and capabilities"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "include_metrics": {
                    "type": "boolean",
                    "description": "Include performance metrics",
                    "default": False,
                },
            },
            "required": [],
        }
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.QUERY
    
    async def execute(
        self,
        engine: "VoiceEngine",
        arguments: Dict[str, Any],
        session: Optional["MCPSession"] = None,
    ) -> Dict[str, Any]:
        """Get engine status."""
        include_metrics = arguments.get("include_metrics", False)
        
        status = {
            "healthy": True,
            "backend": getattr(engine, "_backend_name", "unknown"),
            "capabilities": {
                "streaming": hasattr(engine, "stream"),
                "emotion": hasattr(engine, "emotion_detect"),
                "cloning": hasattr(engine, "clone_voice"),
                "ssml": True,
            },
        }
        
        # Check backend health
        if hasattr(engine, "health_check"):
            try:
                health = engine.health_check()
                status["healthy"] = health.get("healthy", True)
                status["backend_status"] = health
            except Exception as e:
                status["healthy"] = False
                status["error"] = str(e)
        
        # Include metrics if requested
        if include_metrics and hasattr(engine, "get_metrics"):
            status["metrics"] = engine.get_metrics()
        
        return status


class ToolRegistry:
    """
    Registry for MCP tools.
    
    Manages tool registration, discovery, and lookup.
    """
    
    def __init__(self):
        """Initialize tool registry."""
        self._tools: Dict[str, MCPTool] = {}
    
    def register(self, tool: MCPTool) -> None:
        """
        Register a tool.
        
        Args:
            tool: Tool to register
        """
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a tool.
        
        Args:
            name: Tool name
            
        Returns:
            True if tool was removed
        """
        if name in self._tools:
            del self._tools[name]
            return True
        return False
    
    def get_tool(self, name: str) -> Optional[MCPTool]:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None
        """
        return self._tools.get(name)
    
    def list_tools(self) -> Dict[str, MCPTool]:
        """
        List all registered tools.
        
        Returns:
            Dictionary of tool name to tool instance
        """
        return self._tools.copy()
    
    def list_by_category(self, category: ToolCategory) -> List[MCPTool]:
        """
        List tools by category.
        
        Args:
            category: Tool category
            
        Returns:
            List of tools in category
        """
        return [
            tool for tool in self._tools.values()
            if tool.category == category
        ]


def create_default_tools() -> List[MCPTool]:
    """
    Create the default set of MCP tools.
    
    Returns:
        List of default tool instances
    """
    return [
        SpeakTool(),
        StreamTool(),
        InterruptTool(),
        ListVoicesTool(),
        StatusTool(),
    ]
