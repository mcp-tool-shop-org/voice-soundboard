"""
Audit Logger - Security event logging and monitoring.

Provides comprehensive audit logging for:
    - Authentication events
    - Authorization decisions
    - Plugin execution
    - Input validation
    - Rate limit events
    - Security violations
"""

from __future__ import annotations

import json
import time
import uuid
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Protocol, runtime_checkable
from enum import Enum, auto
from pathlib import Path


class AuditEventType(Enum):
    """Types of audit events."""
    
    # Authentication
    AUTH_SUCCESS = auto()
    AUTH_FAILURE = auto()
    AUTH_EXPIRED = auto()
    
    # Authorization
    AUTHZ_GRANTED = auto()
    AUTHZ_DENIED = auto()
    
    # Plugin events
    PLUGIN_LOADED = auto()
    PLUGIN_EXECUTED = auto()
    PLUGIN_SANDBOX_VIOLATION = auto()
    PLUGIN_ERROR = auto()
    
    # Input validation
    INPUT_VALIDATED = auto()
    INPUT_REJECTED = auto()
    INPUT_SANITIZED = auto()
    
    # Rate limiting
    RATE_LIMIT_CHECK = auto()
    RATE_LIMIT_EXCEEDED = auto()
    
    # Secrets
    SECRET_ACCESSED = auto()
    SECRET_ROTATED = auto()
    SECRET_EXPIRED = auto()
    
    # Security violations
    SECURITY_VIOLATION = auto()
    INTRUSION_ATTEMPT = auto()


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """An audit event record."""
    
    event_type: AuditEventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: AuditSeverity = AuditSeverity.INFO
    
    # Context
    client_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    
    # Event details
    resource: str | None = None
    action: str | None = None
    outcome: str | None = None
    message: str | None = None
    
    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Source info
    source_ip: str | None = None
    user_agent: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["event_type"] = self.event_type.name
        data["severity"] = self.severity.value
        data["timestamp"] = self.timestamp.isoformat()
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class AuditConfig:
    """Configuration for audit logging."""
    
    # Output destinations
    log_to_file: bool = True
    log_file_path: Path | None = None
    log_to_stdout: bool = False
    log_to_callback: bool = False
    
    # Filtering
    min_severity: AuditSeverity = AuditSeverity.INFO
    event_types_include: list[AuditEventType] | None = None
    event_types_exclude: list[AuditEventType] | None = None
    
    # Formatting
    format_json: bool = True
    include_metadata: bool = True
    redact_sensitive: bool = True
    
    # Performance
    async_logging: bool = True
    buffer_size: int = 100
    flush_interval_seconds: float = 5.0
    
    # Retention
    max_file_size_mb: int = 100
    max_files: int = 10
    compress_old_files: bool = True


@runtime_checkable
class AuditBackend(Protocol):
    """Protocol for audit log backends."""
    
    def write(self, event: AuditEvent) -> None:
        """Write an audit event."""
        ...
    
    def flush(self) -> None:
        """Flush buffered events."""
        ...
    
    def close(self) -> None:
        """Close the backend."""
        ...


class FileAuditBackend:
    """File-based audit backend with rotation."""
    
    def __init__(self, path: Path, config: AuditConfig):
        self.path = path
        self.config = config
        self._file = None
        self._lock = threading.Lock()
        self._current_size = 0
        self._ensure_file()
    
    def _ensure_file(self) -> None:
        """Ensure audit file exists and is open."""
        if self._file is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._file = open(self.path, "a", encoding="utf-8")
            self._current_size = self.path.stat().st_size if self.path.exists() else 0
    
    def write(self, event: AuditEvent) -> None:
        """Write an event to the file."""
        with self._lock:
            self._ensure_file()
            
            line = event.to_json() + "\n"
            self._file.write(line)
            self._current_size += len(line)
            
            # Check for rotation
            if self._current_size >= self.config.max_file_size_mb * 1024 * 1024:
                self._rotate()
    
    def _rotate(self) -> None:
        """Rotate the log file."""
        if self._file:
            self._file.close()
        
        # Rename existing files
        for i in range(self.config.max_files - 1, 0, -1):
            old_path = self.path.with_suffix(f".{i}.log")
            new_path = self.path.with_suffix(f".{i + 1}.log")
            if old_path.exists():
                if i + 1 >= self.config.max_files:
                    old_path.unlink()
                else:
                    old_path.rename(new_path)
        
        # Rotate current file
        if self.path.exists():
            self.path.rename(self.path.with_suffix(".1.log"))
        
        self._file = open(self.path, "w", encoding="utf-8")
        self._current_size = 0
    
    def flush(self) -> None:
        """Flush the file buffer."""
        with self._lock:
            if self._file:
                self._file.flush()
    
    def close(self) -> None:
        """Close the file."""
        with self._lock:
            if self._file:
                self._file.close()
                self._file = None


class AuditLogger:
    """
    Security event logging system.
    
    Example:
        logger = AuditLogger(
            log_file="audit.log",
            min_severity=AuditSeverity.INFO,
        )
        
        # Log plugin execution
        logger.log(AuditEventType.PLUGIN_EXECUTED,
            resource="my_plugin",
            action="process",
            outcome="success",
            client_id="client_123",
        )
        
        # Log security violation
        logger.security_violation(
            message="Sandbox escape attempt detected",
            plugin_id="malicious_plugin",
            severity=AuditSeverity.CRITICAL,
        )
    """
    
    # Sensitive fields to redact
    SENSITIVE_FIELDS = {"api_key", "password", "token", "secret", "credential"}
    
    def __init__(
        self,
        log_file: str | Path | None = None,
        min_severity: AuditSeverity = AuditSeverity.INFO,
        config: AuditConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = AuditConfig(
                log_file_path=Path(log_file) if log_file else None,
                min_severity=min_severity,
            )
        
        self._backends: list[AuditBackend] = []
        self._callbacks: list[Callable[[AuditEvent], None]] = []
        self._buffer: list[AuditEvent] = []
        self._lock = threading.Lock()
        self._flush_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        
        self._setup_backends()
        self._start_flush_thread()
    
    def _setup_backends(self) -> None:
        """Initialize audit backends."""
        if self.config.log_to_file and self.config.log_file_path:
            self._backends.append(
                FileAuditBackend(self.config.log_file_path, self.config)
            )
    
    def _start_flush_thread(self) -> None:
        """Start background flush thread."""
        if self.config.async_logging:
            self._flush_thread = threading.Thread(
                target=self._flush_loop,
                daemon=True,
            )
            self._flush_thread.start()
    
    def _flush_loop(self) -> None:
        """Background flush loop."""
        while not self._stop_event.wait(self.config.flush_interval_seconds):
            self.flush()
    
    def log(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity = AuditSeverity.INFO,
        **kwargs: Any,
    ) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            severity: Event severity
            **kwargs: Event attributes
            
        Returns:
            The created AuditEvent
        """
        # Check severity filter
        if severity.value < self.config.min_severity.value:
            return None
        
        # Check event type filter
        if self.config.event_types_include:
            if event_type not in self.config.event_types_include:
                return None
        
        if self.config.event_types_exclude:
            if event_type in self.config.event_types_exclude:
                return None
        
        # Create event
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            **kwargs,
        )
        
        # Redact sensitive data
        if self.config.redact_sensitive and event.metadata:
            event.metadata = self._redact_sensitive(event.metadata)
        
        # Buffer or write immediately
        if self.config.async_logging:
            with self._lock:
                self._buffer.append(event)
                if len(self._buffer) >= self.config.buffer_size:
                    self._flush_buffer()
        else:
            self._write_event(event)
        
        # Callbacks
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception:
                pass
        
        return event
    
    def _redact_sensitive(self, data: dict[str, Any]) -> dict[str, Any]:
        """Redact sensitive fields from metadata."""
        redacted = {}
        for key, value in data.items():
            if key.lower() in self.SENSITIVE_FIELDS:
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_sensitive(value)
            else:
                redacted[key] = value
        return redacted
    
    def _write_event(self, event: AuditEvent) -> None:
        """Write event to all backends."""
        for backend in self._backends:
            try:
                backend.write(event)
            except Exception:
                pass
        
        if self.config.log_to_stdout:
            print(event.to_json())
    
    def _flush_buffer(self) -> None:
        """Flush buffered events."""
        events = self._buffer.copy()
        self._buffer.clear()
        
        for event in events:
            self._write_event(event)
    
    def flush(self) -> None:
        """Flush all pending events."""
        with self._lock:
            self._flush_buffer()
        
        for backend in self._backends:
            backend.flush()
    
    def close(self) -> None:
        """Close the audit logger."""
        self._stop_event.set()
        self.flush()
        
        for backend in self._backends:
            backend.close()
    
    def add_callback(self, callback: Callable[[AuditEvent], None]) -> None:
        """Add a callback for real-time event processing."""
        self._callbacks.append(callback)
    
    # Convenience methods
    
    def security_violation(
        self,
        message: str,
        severity: AuditSeverity = AuditSeverity.ERROR,
        **kwargs: Any,
    ) -> AuditEvent:
        """Log a security violation."""
        return self.log(
            AuditEventType.SECURITY_VIOLATION,
            severity=severity,
            message=message,
            **kwargs,
        )
    
    def plugin_executed(
        self,
        plugin_id: str,
        outcome: str,
        execution_time: float | None = None,
        **kwargs: Any,
    ) -> AuditEvent:
        """Log plugin execution."""
        return self.log(
            AuditEventType.PLUGIN_EXECUTED,
            resource=plugin_id,
            outcome=outcome,
            metadata={"execution_time": execution_time} if execution_time else {},
            **kwargs,
        )
    
    def input_rejected(
        self,
        reason: str,
        input_preview: str | None = None,
        **kwargs: Any,
    ) -> AuditEvent:
        """Log rejected input."""
        return self.log(
            AuditEventType.INPUT_REJECTED,
            severity=AuditSeverity.WARNING,
            message=reason,
            metadata={"input_preview": input_preview[:100] if input_preview else None},
            **kwargs,
        )
    
    def rate_limit_exceeded(
        self,
        client_id: str,
        limit: int,
        window_seconds: int,
        **kwargs: Any,
    ) -> AuditEvent:
        """Log rate limit exceeded."""
        return self.log(
            AuditEventType.RATE_LIMIT_EXCEEDED,
            severity=AuditSeverity.WARNING,
            client_id=client_id,
            metadata={"limit": limit, "window_seconds": window_seconds},
            **kwargs,
        )
