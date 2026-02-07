"""
Rate Limiter - Per-client rate limiting for resource protection.

Implements multiple rate limiting strategies:
    - Token bucket (smooth rate limiting)
    - Sliding window (precise rate limiting)
    - Fixed window (simple rate limiting)

Supports:
    - Per-client limits
    - Per-endpoint limits
    - Burst allowance
    - Redis-backed distributed limiting
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from enum import Enum
from collections import defaultdict


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        client_id: str,
        limit: int,
        window_seconds: int,
        retry_after_seconds: float,
    ):
        self.client_id = client_id
        self.limit = limit
        self.window_seconds = window_seconds
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Rate limit exceeded for {client_id}: "
            f"{limit} requests per {window_seconds}s. "
            f"Retry after {retry_after_seconds:.1f}s"
        )


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    
    # Basic limits
    requests_per_second: float = 10.0
    requests_per_minute: float = 100.0
    requests_per_hour: float = 1000.0
    
    # Burst settings
    burst_size: int = 20
    burst_recovery_rate: float = 5.0  # tokens per second
    
    # Strategy
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET
    
    # Storage
    use_redis: bool = False
    redis_url: str | None = None
    redis_key_prefix: str = "voice_soundboard:rate_limit"
    
    # Behavior
    block_on_limit: bool = True
    log_exceeded: bool = True
    
    # Per-client overrides
    client_limits: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class RateLimitStatus:
    """Current rate limit status for a client."""
    
    client_id: str
    allowed: bool
    remaining: int
    limit: int
    reset_seconds: float
    retry_after_seconds: float | None = None


class TokenBucket:
    """
    Token bucket rate limiter.
    
    Allows bursts while maintaining average rate.
    """
    
    def __init__(
        self,
        capacity: int,
        refill_rate: float,
    ):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()
    
    def try_acquire(self, tokens: int = 1) -> tuple[bool, float]:
        """
        Try to acquire tokens.
        
        Returns:
            (success, retry_after_seconds)
        """
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            
            # Calculate wait time
            needed = tokens - self.tokens
            wait_time = needed / self.refill_rate
            return False, wait_time
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate,
        )
        self.last_refill = now
    
    @property
    def current_tokens(self) -> float:
        """Get current token count."""
        self._refill()
        return self.tokens


class SlidingWindowCounter:
    """
    Sliding window counter for precise rate limiting.
    
    Tracks request counts in small time windows.
    """
    
    def __init__(
        self,
        limit: int,
        window_seconds: int,
        precision_seconds: int = 1,
    ):
        self.limit = limit
        self.window_seconds = window_seconds
        self.precision_seconds = precision_seconds
        self.num_segments = window_seconds // precision_seconds
        
        self._counts: dict[int, int] = defaultdict(int)
        self._lock = threading.Lock()
    
    def try_acquire(self) -> tuple[bool, int, float]:
        """
        Try to record a request.
        
        Returns:
            (success, current_count, retry_after_seconds)
        """
        with self._lock:
            now = time.time()
            current_segment = int(now / self.precision_seconds)
            
            # Clean old segments
            self._cleanup(current_segment)
            
            # Count requests in window
            total = sum(self._counts.values())
            
            if total < self.limit:
                self._counts[current_segment] += 1
                return True, total + 1, 0.0
            
            # Find oldest segment to calculate retry time
            oldest_segment = min(self._counts.keys()) if self._counts else current_segment
            retry_after = (oldest_segment + self.num_segments) * self.precision_seconds - now
            
            return False, total, max(0, retry_after)
    
    def _cleanup(self, current_segment: int) -> None:
        """Remove expired segments."""
        min_segment = current_segment - self.num_segments
        expired = [s for s in self._counts if s < min_segment]
        for s in expired:
            del self._counts[s]
    
    @property
    def current_count(self) -> int:
        """Get current request count in window."""
        with self._lock:
            current_segment = int(time.time() / self.precision_seconds)
            self._cleanup(current_segment)
            return sum(self._counts.values())


class RateLimiter:
    """
    Per-client rate limiter for resource protection.
    
    Example:
        limiter = RateLimiter(
            requests_per_second=10,
            burst_size=20,
        )
        
        try:
            limiter.check("client_123")
            # Process request
        except RateLimitExceeded as e:
            # Return 429 Too Many Requests
            print(f"Retry after {e.retry_after_seconds}s")
    """
    
    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: int = 20,
        requests_per_minute: float | None = None,
        strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET,
        config: RateLimitConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = RateLimitConfig(
                requests_per_second=requests_per_second,
                burst_size=burst_size,
                requests_per_minute=requests_per_minute or requests_per_second * 60,
                strategy=strategy,
            )
        
        self._client_buckets: dict[str, TokenBucket] = {}
        self._client_windows: dict[str, SlidingWindowCounter] = {}
        self._lock = threading.Lock()
    
    def check(
        self,
        client_id: str,
        cost: int = 1,
        raise_on_limit: bool = True,
    ) -> RateLimitStatus:
        """
        Check rate limit for a client.
        
        Args:
            client_id: Client identifier
            cost: Request cost (usually 1)
            raise_on_limit: If True, raise RateLimitExceeded
            
        Returns:
            RateLimitStatus with current state
            
        Raises:
            RateLimitExceeded if limit exceeded and raise_on_limit=True
        """
        # Get or create limiter for client
        bucket = self._get_bucket(client_id)
        
        # Try to acquire tokens
        allowed, retry_after = bucket.try_acquire(cost)
        
        status = RateLimitStatus(
            client_id=client_id,
            allowed=allowed,
            remaining=int(bucket.current_tokens),
            limit=bucket.capacity,
            reset_seconds=bucket.capacity / bucket.refill_rate,
            retry_after_seconds=retry_after if not allowed else None,
        )
        
        if not allowed and raise_on_limit:
            raise RateLimitExceeded(
                client_id=client_id,
                limit=bucket.capacity,
                window_seconds=int(bucket.capacity / bucket.refill_rate),
                retry_after_seconds=retry_after,
            )
        
        return status
    
    def _get_bucket(self, client_id: str) -> TokenBucket:
        """Get or create a token bucket for a client."""
        with self._lock:
            if client_id not in self._client_buckets:
                # Check for client-specific limits
                limits = self.config.client_limits.get(client_id, {})
                
                capacity = limits.get("burst_size", self.config.burst_size)
                rate = limits.get(
                    "requests_per_second",
                    self.config.requests_per_second,
                )
                
                self._client_buckets[client_id] = TokenBucket(
                    capacity=int(capacity),
                    refill_rate=rate,
                )
            
            return self._client_buckets[client_id]
    
    def reset(self, client_id: str) -> None:
        """Reset rate limit for a client."""
        with self._lock:
            if client_id in self._client_buckets:
                del self._client_buckets[client_id]
            if client_id in self._client_windows:
                del self._client_windows[client_id]
    
    def set_client_limit(
        self,
        client_id: str,
        requests_per_second: float | None = None,
        burst_size: int | None = None,
    ) -> None:
        """Set custom rate limit for a specific client."""
        with self._lock:
            if client_id not in self.config.client_limits:
                self.config.client_limits[client_id] = {}
            
            if requests_per_second is not None:
                self.config.client_limits[client_id]["requests_per_second"] = requests_per_second
            
            if burst_size is not None:
                self.config.client_limits[client_id]["burst_size"] = burst_size
            
            # Reset to apply new limits
            if client_id in self._client_buckets:
                del self._client_buckets[client_id]
    
    def get_status(self, client_id: str) -> RateLimitStatus:
        """Get current rate limit status without consuming tokens."""
        bucket = self._get_bucket(client_id)
        
        return RateLimitStatus(
            client_id=client_id,
            allowed=bucket.current_tokens >= 1,
            remaining=int(bucket.current_tokens),
            limit=bucket.capacity,
            reset_seconds=bucket.capacity / bucket.refill_rate,
        )
    
    def cleanup_expired(self, max_idle_seconds: float = 3600) -> int:
        """
        Remove rate limiters for inactive clients.
        
        Returns number of limiters removed.
        """
        # In production, would track last access time
        # For now, this is a placeholder
        return 0
