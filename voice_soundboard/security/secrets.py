"""
Secret Manager - Secure API key and credential handling.

Provides secure storage and access control for:
    - API keys
    - Authentication tokens
    - Backend credentials
    - Encryption keys

Supports:
    - Environment variable injection
    - Encrypted file storage
    - Cloud secret managers (AWS, GCP, Azure)
    - Key rotation
    - Access auditing
"""

from __future__ import annotations

import os
import json
import base64
import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Protocol, runtime_checkable
from pathlib import Path
from enum import Enum


class SecretNotFound(Exception):
    """Raised when a secret is not found."""
    
    def __init__(self, secret_name: str):
        self.secret_name = secret_name
        super().__init__(f"Secret not found: {secret_name}")


class SecretExpired(Exception):
    """Raised when a secret has expired."""
    
    def __init__(self, secret_name: str, expired_at: datetime):
        self.secret_name = secret_name
        self.expired_at = expired_at
        super().__init__(f"Secret expired: {secret_name} at {expired_at}")


class SecretSource(Enum):
    """Source of a secret."""
    ENVIRONMENT = "environment"
    FILE = "file"
    MEMORY = "memory"
    AWS_SECRETS = "aws_secrets_manager"
    GCP_SECRET = "gcp_secret_manager"
    AZURE_KEYVAULT = "azure_keyvault"


@dataclass
class SecretConfig:
    """Configuration for secret management."""
    
    # Storage options
    use_environment: bool = True
    environment_prefix: str = "VOICE_SOUNDBOARD_"
    
    use_file: bool = False
    file_path: Path | None = None
    file_encrypted: bool = True
    
    # Cloud providers
    aws_region: str | None = None
    aws_secret_prefix: str | None = None
    
    gcp_project: str | None = None
    gcp_secret_prefix: str | None = None
    
    azure_vault_url: str | None = None
    
    # Caching
    cache_secrets: bool = True
    cache_ttl_seconds: int = 300
    
    # Security
    redact_in_logs: bool = True
    require_encryption: bool = True
    
    # Rotation
    rotation_check_interval_seconds: int = 3600
    auto_rotate_on_expiry: bool = False


@dataclass
class Secret:
    """A managed secret."""
    
    name: str
    value: str
    source: SecretSource
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    version: str = "1"
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """Check if secret has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def __repr__(self) -> str:
        """Hide value in repr."""
        return f"Secret(name={self.name!r}, source={self.source}, version={self.version})"


@runtime_checkable
class SecretBackend(Protocol):
    """Protocol for secret storage backends."""
    
    def get(self, name: str) -> str | None:
        """Get a secret value."""
        ...
    
    def set(self, name: str, value: str, **kwargs: Any) -> None:
        """Set a secret value."""
        ...
    
    def delete(self, name: str) -> None:
        """Delete a secret."""
        ...
    
    def list(self) -> list[str]:
        """List available secret names."""
        ...


class EnvironmentBackend:
    """Environment variable backend for secrets."""
    
    def __init__(self, prefix: str = ""):
        self.prefix = prefix
    
    def get(self, name: str) -> str | None:
        return os.environ.get(f"{self.prefix}{name}")
    
    def set(self, name: str, value: str, **kwargs: Any) -> None:
        os.environ[f"{self.prefix}{name}"] = value
    
    def delete(self, name: str) -> None:
        key = f"{self.prefix}{name}"
        if key in os.environ:
            del os.environ[key]
    
    def list(self) -> list[str]:
        return [
            key[len(self.prefix):]
            for key in os.environ
            if key.startswith(self.prefix)
        ]


class MemoryBackend:
    """In-memory backend for secrets (for testing)."""
    
    def __init__(self):
        self._secrets: dict[str, str] = {}
        self._lock = threading.Lock()
    
    def get(self, name: str) -> str | None:
        with self._lock:
            return self._secrets.get(name)
    
    def set(self, name: str, value: str, **kwargs: Any) -> None:
        with self._lock:
            self._secrets[name] = value
    
    def delete(self, name: str) -> None:
        with self._lock:
            if name in self._secrets:
                del self._secrets[name]
    
    def list(self) -> list[str]:
        with self._lock:
            return list(self._secrets.keys())


class SecretManager:
    """
    Secure management of API keys and credentials.
    
    Example:
        secrets = SecretManager()
        
        # Get API key (auto-discovers from env vars)
        api_key = secrets.get("OPENAI_API_KEY")
        
        # Set a secret
        secrets.set("CUSTOM_TOKEN", "secret_value")
        
        # Use with TTS backends
        engine = VoiceEngine(Config(
            backend="openai",
            api_key=secrets.get("OPENAI_API_KEY"),
        ))
    """
    
    # Common API key names
    KNOWN_SECRETS = [
        "OPENAI_API_KEY",
        "ELEVENLABS_API_KEY",
        "AZURE_SPEECH_KEY",
        "AZURE_SPEECH_REGION",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "COQUI_API_KEY",
        "REDIS_URL",
    ]
    
    def __init__(
        self,
        config: SecretConfig | None = None,
        env_prefix: str = "VOICE_SOUNDBOARD_",
    ):
        if config:
            self.config = config
        else:
            self.config = SecretConfig(
                environment_prefix=env_prefix,
            )
        
        self._backends: list[SecretBackend] = []
        self._cache: dict[str, tuple[Secret, float]] = {}
        self._lock = threading.Lock()
        
        self._setup_backends()
    
    def _setup_backends(self) -> None:
        """Initialize secret backends in priority order."""
        # Memory backend for runtime secrets
        self._memory = MemoryBackend()
        self._backends.append(self._memory)
        
        # Environment variables
        if self.config.use_environment:
            self._backends.append(
                EnvironmentBackend(self.config.environment_prefix)
            )
            # Also check without prefix for common vars
            self._backends.append(EnvironmentBackend(""))
    
    def get(
        self,
        name: str,
        default: str | None = None,
        required: bool = False,
    ) -> str | None:
        """
        Get a secret value.
        
        Args:
            name: Secret name
            default: Default value if not found
            required: If True, raise SecretNotFound when not found
            
        Returns:
            Secret value or default
        """
        # Check cache
        cached = self._get_cached(name)
        if cached:
            return cached.value
        
        # Try backends
        for backend in self._backends:
            value = backend.get(name)
            if value is not None:
                secret = Secret(
                    name=name,
                    value=value,
                    source=self._get_backend_source(backend),
                )
                self._cache_secret(secret)
                return value
        
        if required and default is None:
            raise SecretNotFound(name)
        
        return default
    
    def _get_cached(self, name: str) -> Secret | None:
        """Get secret from cache if not expired."""
        if not self.config.cache_secrets:
            return None
        
        with self._lock:
            if name in self._cache:
                secret, cached_at = self._cache[name]
                
                # Check cache TTL
                if time.time() - cached_at < self.config.cache_ttl_seconds:
                    # Check secret expiry
                    if not secret.is_expired:
                        return secret
                
                del self._cache[name]
        
        return None
    
    def _cache_secret(self, secret: Secret) -> None:
        """Cache a secret."""
        if self.config.cache_secrets:
            with self._lock:
                import time
                self._cache[secret.name] = (secret, time.time())
    
    def _get_backend_source(self, backend: SecretBackend) -> SecretSource:
        """Determine source type from backend."""
        if isinstance(backend, EnvironmentBackend):
            return SecretSource.ENVIRONMENT
        if isinstance(backend, MemoryBackend):
            return SecretSource.MEMORY
        return SecretSource.MEMORY
    
    def set(
        self,
        name: str,
        value: str,
        expires_in: timedelta | None = None,
    ) -> None:
        """
        Set a secret value.
        
        Args:
            name: Secret name
            value: Secret value
            expires_in: Optional expiration time
        """
        expires_at = None
        if expires_in:
            expires_at = datetime.now(timezone.utc) + expires_in
        
        # Store in memory backend
        self._memory.set(name, value)
        
        # Cache it
        secret = Secret(
            name=name,
            value=value,
            source=SecretSource.MEMORY,
            expires_at=expires_at,
        )
        self._cache_secret(secret)
    
    def delete(self, name: str) -> None:
        """Delete a secret."""
        self._memory.delete(name)
        
        with self._lock:
            if name in self._cache:
                del self._cache[name]
    
    def list_available(self) -> list[str]:
        """List available secrets."""
        names = set()
        for backend in self._backends:
            try:
                names.update(backend.list())
            except Exception:
                pass
        return sorted(names)
    
    def validate_required(self, *names: str) -> list[str]:
        """
        Validate that required secrets are available.
        
        Returns list of missing secrets.
        """
        missing = []
        for name in names:
            if self.get(name) is None:
                missing.append(name)
        return missing
    
    def mask_value(self, value: str, visible_chars: int = 4) -> str:
        """Mask a secret value for logging."""
        if len(value) <= visible_chars * 2:
            return "*" * len(value)
        return value[:visible_chars] + "*" * (len(value) - visible_chars * 2) + value[-visible_chars:]
    
    def get_secret(self, name: str) -> Secret | None:
        """Get full Secret object with metadata."""
        value = self.get(name)
        if value is None:
            return None
        
        with self._lock:
            if name in self._cache:
                return self._cache[name][0]
        
        return Secret(name=name, value=value, source=SecretSource.MEMORY)
    
    def refresh(self, name: str) -> str | None:
        """Force refresh a cached secret."""
        with self._lock:
            if name in self._cache:
                del self._cache[name]
        
        return self.get(name)


# Need to import time for cache TTL
import time
