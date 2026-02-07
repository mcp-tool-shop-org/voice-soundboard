"""
Registrar Errors — Domain-specific error types.

Error hierarchy:
    RegistrarError (base)
    ├── InvariantViolationError
    ├── OwnershipError
    ├── AccessibilityBypassError (HALT-level)
    └── RegistrumConnectionError
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class RegistrarError(Exception):
    """Base error for all registrar-related errors."""
    
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvariantViolationError(RegistrarError):
    """
    Raised when an invariant is violated.
    
    Note: This is NOT raised during normal operation.
    Violations are returned as TransitionResult.violations.
    
    This error is raised only when:
    - A HALT-level invariant is violated
    - The system detects a bypass attempt
    """
    
    def __init__(
        self,
        invariant_id: str,
        message: str,
        classification: str = "REJECT",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(f"[{invariant_id}] {message}", details)
        self.invariant_id = invariant_id
        self.classification = classification


class OwnershipError(RegistrarError):
    """
    Raised for ownership-related violations.
    
    Examples:
    - Attempting to claim already-owned stream
    - Attempting to interrupt without ownership
    - Ownership transfer without proper release
    """
    
    def __init__(
        self,
        stream_id: str,
        message: str,
        current_owner: str | None = None,
        requesting_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.stream_id = stream_id
        self.current_owner = current_owner
        self.requesting_agent = requesting_agent


class AccessibilityBypassError(RegistrarError):
    """
    CRITICAL: Raised when accessibility is bypassed.
    
    This is a HALT-level error. The system should stop
    and require investigation before continuing.
    
    Bypass scenarios:
    - Direct state mutation outside registrar
    - Silently ignoring accessibility override
    - Modifying override without explicit action
    """
    
    def __init__(
        self,
        message: str,
        stream_id: str | None = None,
        bypass_type: str = "unknown",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(f"[ACCESSIBILITY BYPASS] {message}", details)
        self.stream_id = stream_id
        self.bypass_type = bypass_type
        self.halt_required = True


class RegistrumConnectionError(RegistrarError):
    """
    Raised when connection to Registrum service fails.
    
    Only raised if fail_closed=False, otherwise the system
    automatically denies all transitions.
    """
    
    def __init__(
        self,
        message: str,
        connection_mode: str = "unknown",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(f"Registrum connection failed: {message}", details)
        self.connection_mode = connection_mode


class InvalidTransitionError(RegistrarError):
    """
    Raised for invalid state transitions.
    
    Examples:
    - IDLE → PLAYING (must compile first)
    - STOPPED → PLAYING (must restart via IDLE)
    """
    
    def __init__(
        self,
        from_state: str,
        to_state: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        msg = message or f"Invalid transition: {from_state} → {to_state}"
        super().__init__(msg, details)
        self.from_state = from_state
        self.to_state = to_state
