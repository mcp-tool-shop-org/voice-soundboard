"""
Core Serverless Handler - Provider-agnostic cloud function support.

Provides a unified interface for serverless TTS synthesis across
different cloud providers.
"""

from __future__ import annotations

import os
import json
import time
import base64
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable
from pathlib import Path


@dataclass
class ServerlessConfig:
    """Configuration for serverless handler."""
    
    # Backend settings
    backend: str = "kokoro"
    voice: str = "af_bella"
    
    # Optimization
    cold_start_optimization: bool = True
    preload_model: bool = True
    cache_dir: str = "/tmp/voice_soundboard"
    
    # Limits
    max_duration_seconds: float = 30.0
    max_text_length: int = 5000
    timeout_seconds: float = 25.0
    
    # Output settings
    output_format: str = "mp3"
    sample_rate: int = 24000
    
    # Response settings
    return_base64: bool = True
    return_url: bool = False
    
    # Warm pool
    keep_warm: bool = True
    warm_interval_seconds: int = 300


@dataclass
class ServerlessRequest:
    """Request structure for serverless handler."""
    
    text: str
    voice: str | None = None
    format: str | None = None
    sample_rate: int | None = None
    
    # Optional parameters
    speed: float = 1.0
    pitch: float = 1.0
    
    # Auto-intelligence features
    auto_emotion: bool = False
    adaptive_pacing: bool = False
    smart_silence: bool = False
    
    # Metadata
    request_id: str | None = None
    client_id: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServerlessRequest":
        """Create request from dictionary."""
        return cls(
            text=data.get("text", ""),
            voice=data.get("voice"),
            format=data.get("format"),
            sample_rate=data.get("sample_rate"),
            speed=data.get("speed", 1.0),
            pitch=data.get("pitch", 1.0),
            auto_emotion=data.get("auto_emotion", False),
            adaptive_pacing=data.get("adaptive_pacing", False),
            smart_silence=data.get("smart_silence", False),
            request_id=data.get("request_id"),
            client_id=data.get("client_id"),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "ServerlessRequest":
        """Create request from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class ServerlessResponse:
    """Response structure for serverless handler."""
    
    success: bool
    audio_base64: str | None = None
    audio_url: str | None = None
    
    # Metadata
    duration_seconds: float = 0.0
    format: str = "mp3"
    sample_rate: int = 24000
    
    # Processing info
    processing_time_ms: float = 0.0
    cold_start: bool = False
    
    # Error info
    error: str | None = None
    error_code: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "audio_base64": self.audio_base64,
            "audio_url": self.audio_url,
            "duration_seconds": self.duration_seconds,
            "format": self.format,
            "sample_rate": self.sample_rate,
            "processing_time_ms": self.processing_time_ms,
            "cold_start": self.cold_start,
            "error": self.error,
            "error_code": self.error_code,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def error_response(cls, error: str, error_code: str = "ERROR") -> "ServerlessResponse":
        """Create error response."""
        return cls(
            success=False,
            error=error,
            error_code=error_code,
        )


class ServerlessHandler:
    """
    Provider-agnostic serverless handler for TTS synthesis.
    
    Handles:
        - Cold start optimization
        - Model caching
        - Request validation
        - Error handling
        - Response formatting
    """
    
    # Class-level engine for warm instances
    _engine = None
    _last_init_time = 0
    _cold_start = True
    
    def __init__(self, config: ServerlessConfig | None = None):
        self.config = config or ServerlessConfig()
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        Path(self.config.cache_dir).mkdir(parents=True, exist_ok=True)
    
    def _get_engine(self):
        """Get or create TTS engine."""
        if ServerlessHandler._engine is None or not self.config.keep_warm:
            from voice_soundboard import VoiceEngine, Config
            
            ServerlessHandler._engine = VoiceEngine(Config(
                backend=self.config.backend,
                model_cache_dir=self.config.cache_dir,
            ))
            ServerlessHandler._last_init_time = time.time()
            ServerlessHandler._cold_start = True
        else:
            ServerlessHandler._cold_start = False
        
        return ServerlessHandler._engine
    
    def handle(self, request: ServerlessRequest) -> ServerlessResponse:
        """
        Handle a synthesis request.
        
        Args:
            request: Synthesis request
            
        Returns:
            ServerlessResponse with audio or error
        """
        start_time = time.time()
        
        # Validate request
        if not request.text:
            return ServerlessResponse.error_response(
                "Text is required",
                "INVALID_REQUEST",
            )
        
        if len(request.text) > self.config.max_text_length:
            return ServerlessResponse.error_response(
                f"Text exceeds maximum length of {self.config.max_text_length}",
                "TEXT_TOO_LONG",
            )
        
        try:
            # Get engine
            engine = self._get_engine()
            cold_start = ServerlessHandler._cold_start
            
            # Apply intelligence if requested
            text = request.text
            
            if request.auto_emotion or request.adaptive_pacing or request.smart_silence:
                text = self._apply_intelligence(text, request)
            
            # Synthesize
            voice = request.voice or self.config.voice
            
            result = engine.speak(
                text,
                voice=voice,
                speed=request.speed,
                pitch=request.pitch,
            )
            
            # Convert to requested format
            output_format = request.format or self.config.output_format
            
            # Read audio file
            audio_bytes = self._read_and_convert(result.audio_path, output_format)
            
            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000
            
            return ServerlessResponse(
                success=True,
                audio_base64=base64.b64encode(audio_bytes).decode() if self.config.return_base64 else None,
                duration_seconds=result.duration,
                format=output_format,
                sample_rate=request.sample_rate or self.config.sample_rate,
                processing_time_ms=processing_time_ms,
                cold_start=cold_start,
            )
            
        except TimeoutError:
            return ServerlessResponse.error_response(
                "Request timed out",
                "TIMEOUT",
            )
        except Exception as e:
            return ServerlessResponse.error_response(
                str(e),
                "SYNTHESIS_ERROR",
            )
    
    def _apply_intelligence(self, text: str, request: ServerlessRequest) -> str:
        """Apply intelligence features to text."""
        if request.auto_emotion:
            from voice_soundboard.intelligence import EmotionDetector
            detector = EmotionDetector()
            # Emotion detection affects prosody, not text
            # This would be passed to the engine
        
        if request.adaptive_pacing:
            from voice_soundboard.intelligence import AdaptivePacer
            pacer = AdaptivePacer()
            text = pacer.apply(text)
        
        if request.smart_silence:
            from voice_soundboard.intelligence import SmartSilence
            silencer = SmartSilence()
            text = silencer.apply(text)
        
        return text
    
    def _read_and_convert(self, audio_path: Path, output_format: str) -> bytes:
        """Read audio file and convert to requested format."""
        # Read the file
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        
        # Convert if necessary (simplified - real implementation would use soundfile/ffmpeg)
        if output_format == "wav" or str(audio_path).endswith(".wav"):
            return audio_bytes
        
        # For other formats, would use soundfile or subprocess ffmpeg
        return audio_bytes
    
    def warmup(self) -> None:
        """Pre-warm the handler for faster cold starts."""
        self._get_engine()
        # Synthesize a short phrase to load model fully
        try:
            engine = self._get_engine()
            engine.speak("Warmup", voice=self.config.voice)
        except Exception:
            pass


def create_handler(
    backend: str = "kokoro",
    voice: str = "af_bella",
    cold_start_optimization: bool = True,
    max_duration_seconds: float = 30.0,
    **kwargs: Any,
) -> Callable:
    """
    Create a serverless handler function.
    
    Args:
        backend: TTS backend to use
        voice: Default voice
        cold_start_optimization: Enable cold start optimization
        max_duration_seconds: Maximum audio duration
        **kwargs: Additional config options
        
    Returns:
        Handler function suitable for cloud deployment
    """
    config = ServerlessConfig(
        backend=backend,
        voice=voice,
        cold_start_optimization=cold_start_optimization,
        max_duration_seconds=max_duration_seconds,
        **kwargs,
    )
    
    handler = ServerlessHandler(config)
    
    def handle_request(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
        """Handle incoming serverless request."""
        # Parse request from different providers
        if "body" in event:
            # AWS Lambda / Azure Functions
            body = event["body"]
            if isinstance(body, str):
                body = json.loads(body)
        else:
            # Direct invocation / GCP
            body = event
        
        request = ServerlessRequest.from_dict(body)
        response = handler.handle(request)
        
        return {
            "statusCode": 200 if response.success else 400,
            "headers": {
                "Content-Type": "application/json",
            },
            "body": response.to_json(),
        }
    
    return handle_request
