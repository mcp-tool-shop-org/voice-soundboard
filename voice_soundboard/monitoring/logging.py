"""
Structured logging for Voice Soundboard.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, TextIO
import threading


class LogLevel(Enum):
    """Log levels."""
    
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    
    @property
    def numeric(self) -> int:
        """Get numeric log level."""
        return {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }[self.value]


@dataclass
class LogRecord:
    """A structured log record.
    
    Attributes:
        level: Log level.
        event: Event name/type.
        message: Human-readable message.
        timestamp: Unix timestamp.
        data: Additional structured data.
    """
    
    level: str
    event: str
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)
    
    # Context fields (set by logger)
    logger_name: str = ""
    thread_name: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        d.update(d.pop("data", {}))
        return d
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class StructuredLogger:
    """Structured logging with JSON output.
    
    Provides consistent, machine-parseable logs for production:
    - JSON format by default
    - Contextual data binding
    - Event-based logging
    - Integration with standard logging
    
    Example:
        logger = StructuredLogger("voice_soundboard")
        
        # Log an event
        logger.info(
            "synthesis_complete",
            message="Synthesis completed successfully",
            duration_ms=145.2,
            backend="kokoro",
        )
        
        # Output (JSON):
        # {"level": "info", "event": "synthesis_complete", 
        #  "message": "Synthesis completed successfully",
        #  "duration_ms": 145.2, "backend": "kokoro", ...}
        
        # Create a bound logger with context
        ctx_logger = logger.bind(request_id="abc123")
        ctx_logger.info("processing", message="Processing request")
        # All logs include request_id="abc123"
    """
    
    def __init__(
        self,
        name: str = "voice_soundboard",
        level: LogLevel = LogLevel.INFO,
        output: TextIO | None = None,
        json_format: bool = True,
    ):
        """Initialize the logger.
        
        Args:
            name: Logger name.
            level: Minimum log level.
            output: Output stream (default: stderr).
            json_format: Output as JSON (vs. human-readable).
        """
        self.name = name
        self._level = level
        self._output = output or sys.stderr
        self._json_format = json_format
        
        # Bound context
        self._context: dict[str, Any] = {}
        
        # Thread safety
        self._lock = threading.Lock()
    
    def bind(self, **context: Any) -> "StructuredLogger":
        """Create a new logger with bound context.
        
        Args:
            **context: Context to bind to all log records.
        
        Returns:
            New logger with bound context.
        """
        new_logger = StructuredLogger(
            name=self.name,
            level=self._level,
            output=self._output,
            json_format=self._json_format,
        )
        new_logger._context = {**self._context, **context}
        return new_logger
    
    def _log(
        self,
        level: LogLevel,
        event: str,
        message: str = "",
        **data: Any,
    ) -> None:
        """Internal logging method.
        
        Args:
            level: Log level.
            event: Event name.
            message: Human-readable message.
            **data: Additional data.
        """
        if level.numeric < self._level.numeric:
            return
        
        record = LogRecord(
            level=level.value,
            event=event,
            message=message,
            data={**self._context, **data},
            logger_name=self.name,
            thread_name=threading.current_thread().name,
        )
        
        self._emit(record)
    
    def _emit(self, record: LogRecord) -> None:
        """Emit a log record.
        
        Args:
            record: Log record to emit.
        """
        with self._lock:
            if self._json_format:
                line = record.to_json()
            else:
                line = self._format_human(record)
            
            print(line, file=self._output)
    
    def _format_human(self, record: LogRecord) -> str:
        """Format record for human reading.
        
        Args:
            record: Log record.
        
        Returns:
            Formatted string.
        """
        timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(record.timestamp),
        )
        
        parts = [
            f"[{timestamp}]",
            f"[{record.level.upper()}]",
            f"[{record.event}]",
        ]
        
        if record.message:
            parts.append(record.message)
        
        if record.data:
            data_str = " ".join(f"{k}={v}" for k, v in record.data.items())
            parts.append(f"({data_str})")
        
        return " ".join(parts)
    
    def debug(self, event: str, message: str = "", **data: Any) -> None:
        """Log at DEBUG level."""
        self._log(LogLevel.DEBUG, event, message, **data)
    
    def info(self, event: str, message: str = "", **data: Any) -> None:
        """Log at INFO level."""
        self._log(LogLevel.INFO, event, message, **data)
    
    def warning(self, event: str, message: str = "", **data: Any) -> None:
        """Log at WARNING level."""
        self._log(LogLevel.WARNING, event, message, **data)
    
    def error(self, event: str, message: str = "", **data: Any) -> None:
        """Log at ERROR level."""
        self._log(LogLevel.ERROR, event, message, **data)
    
    def critical(self, event: str, message: str = "", **data: Any) -> None:
        """Log at CRITICAL level."""
        self._log(LogLevel.CRITICAL, event, message, **data)
    
    # Convenience methods for common events
    
    def synthesis_start(
        self,
        text: str,
        voice: str = "",
        backend: str = "",
        **extra: Any,
    ) -> None:
        """Log synthesis start."""
        self.info(
            "synthesis_start",
            f"Starting synthesis",
            text_length=len(text),
            voice=voice,
            backend=backend,
            **extra,
        )
    
    def synthesis_complete(
        self,
        duration_ms: float,
        audio_duration_s: float = 0,
        backend: str = "",
        cached: bool = False,
        **extra: Any,
    ) -> None:
        """Log synthesis completion."""
        self.info(
            "synthesis_complete",
            f"Synthesis completed in {duration_ms:.1f}ms",
            duration_ms=duration_ms,
            audio_duration_s=audio_duration_s,
            backend=backend,
            cached=cached,
            **extra,
        )
    
    def synthesis_error(
        self,
        error: Exception,
        **extra: Any,
    ) -> None:
        """Log synthesis error."""
        self.error(
            "synthesis_error",
            str(error),
            error_type=type(error).__name__,
            **extra,
        )
    
    def stream_chunk(
        self,
        chunk_index: int,
        chunk_size: int,
        latency_ms: float = 0,
        **extra: Any,
    ) -> None:
        """Log streaming chunk."""
        self.debug(
            "stream_chunk",
            chunk_index=chunk_index,
            chunk_size=chunk_size,
            latency_ms=latency_ms,
            **extra,
        )
    
    def rollback(
        self,
        samples_rolled_back: int,
        reason: str = "",
        **extra: Any,
    ) -> None:
        """Log rollback event."""
        self.info(
            "rollback",
            f"Rolled back {samples_rolled_back} samples",
            samples_rolled_back=samples_rolled_back,
            reason=reason,
            **extra,
        )


# Global logger instance
_global_logger: StructuredLogger | None = None


def configure_logging(
    level: LogLevel | str = LogLevel.INFO,
    output: TextIO | None = None,
    json_format: bool = True,
) -> StructuredLogger:
    """Configure global logging.
    
    Args:
        level: Log level.
        output: Output stream.
        json_format: Use JSON format.
    
    Returns:
        Configured logger.
    """
    global _global_logger
    
    if isinstance(level, str):
        level = LogLevel(level)
    
    _global_logger = StructuredLogger(
        name="voice_soundboard",
        level=level,
        output=output,
        json_format=json_format,
    )
    
    return _global_logger


def get_logger(name: str = "voice_soundboard") -> StructuredLogger:
    """Get a logger instance.
    
    Args:
        name: Logger name.
    
    Returns:
        Logger instance.
    """
    global _global_logger
    
    if _global_logger is None:
        _global_logger = StructuredLogger(name=name)
    
    return _global_logger
