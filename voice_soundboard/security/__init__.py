"""
Voice Soundboard v2.4 - Security Module

Production-grade security for enterprise deployments.

Components:
    PluginSandbox   - Isolated plugin execution environment
    InputValidator  - SSML and markup injection prevention
    AuditLogger     - Security event logging and monitoring
    RateLimiter     - Per-client rate limiting
    SecretManager   - Secure API key handling

Usage:
    from voice_soundboard.security import PluginSandbox, InputValidator

    # Sandboxed plugin execution
    sandbox = PluginSandbox(
        max_memory_mb=512,
        max_cpu_seconds=10,
        allowed_imports=["numpy", "scipy"],
        network_access=False,
    )

    with sandbox.execute(plugin):
        result = plugin.process(audio)

    # Input validation
    validator = InputValidator(
        max_length=10000,
        allow_ssml=True,
        sanitize_markup=True,
    )

    safe_text = validator.validate(user_input)
    engine.speak(safe_text)
"""

from voice_soundboard.security.sandbox import (
    PluginSandbox,
    SandboxConfig,
    SandboxViolation,
    SandboxExecutionResult,
)

from voice_soundboard.security.validation import (
    InputValidator,
    ValidationConfig,
    ValidationError,
    SSMLSanitizer,
)

from voice_soundboard.security.audit import (
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditConfig,
)

from voice_soundboard.security.rate_limit import (
    RateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    TokenBucket,
)

from voice_soundboard.security.secrets import (
    SecretManager,
    SecretConfig,
    SecretNotFound,
    SecretExpired,
)

__all__ = [
    # Sandbox
    "PluginSandbox",
    "SandboxConfig",
    "SandboxViolation",
    "SandboxExecutionResult",
    # Validation
    "InputValidator",
    "ValidationConfig",
    "ValidationError",
    "SSMLSanitizer",
    # Audit
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    "AuditConfig",
    # Rate Limiting
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitExceeded",
    "TokenBucket",
    # Secrets
    "SecretManager",
    "SecretConfig",
    "SecretNotFound",
    "SecretExpired",
]
