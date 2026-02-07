"""
Cost Tracker - Backend cost attribution and reporting.

Features:
    - Per-backend pricing
    - Client cost attribution
    - Usage forecasting
    - Cost-aware routing
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict
from datetime import datetime, timezone


@dataclass
class PricingTier:
    """Pricing tier for a backend."""
    
    name: str
    cost_per_1k_chars: float
    min_chars: int = 0
    max_chars: int | None = None
    
    def calculate_cost(self, characters: int) -> float:
        """Calculate cost for given characters."""
        applicable_chars = characters
        
        if self.min_chars > 0:
            if characters < self.min_chars:
                return 0.0
            applicable_chars = characters - self.min_chars
        
        if self.max_chars is not None:
            applicable_chars = min(applicable_chars, self.max_chars - self.min_chars)
        
        return (applicable_chars / 1000) * self.cost_per_1k_chars


@dataclass
class CostConfig:
    """Configuration for cost tracking."""
    
    # Default pricing per 1K characters
    pricing: dict[str, float] = field(default_factory=lambda: {
        "kokoro": 0.0,       # Free (local)
        "piper": 0.0,        # Free (local)
        "coqui": 0.0,        # Free (local)
        "openai": 0.015,     # $15 per 1M characters
        "elevenlabs": 0.018, # ~$18 per 1M characters
        "azure": 0.016,      # ~$16 per 1M characters
        "google": 0.016,     # ~$16 per 1M characters
    })
    
    # Tiered pricing
    tiers: dict[str, list[PricingTier]] = field(default_factory=dict)
    
    # Tracking
    track_by_client: bool = True
    track_by_voice: bool = True
    
    # Retention
    retention_days: int = 90


@dataclass
class CostReport:
    """Cost report for a period."""
    
    period_start: datetime
    period_end: datetime
    
    total_cost: float = 0.0
    total_characters: int = 0
    total_requests: int = 0
    
    by_backend: dict[str, float] = field(default_factory=dict)
    by_client: dict[str, float] = field(default_factory=dict)
    by_voice: dict[str, float] = field(default_factory=dict)
    by_day: dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_cost": self.total_cost,
            "total_characters": self.total_characters,
            "total_requests": self.total_requests,
            "by_backend": self.by_backend,
            "by_client": self.by_client,
            "by_voice": self.by_voice,
            "by_day": self.by_day,
        }


class CostTracker:
    """
    Track and attribute costs for TTS backends.
    
    Example:
        tracker = CostTracker(
            pricing={
                "kokoro": 0.0,
                "openai": 0.015,
                "elevenlabs": 0.018,
            }
        )
        
        # Track costs
        tracker.attribute("client_123", result)
        
        # Monthly report
        report = tracker.report("2026-10")
    """
    
    def __init__(
        self,
        pricing: dict[str, float] | None = None,
        config: CostConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = CostConfig()
            if pricing:
                self.config.pricing.update(pricing)
        
        # Storage
        self._records: list[dict[str, Any]] = []
    
    def calculate_cost(
        self,
        backend: str,
        characters: int,
    ) -> float:
        """
        Calculate cost for a synthesis request.
        
        Args:
            backend: Backend name
            characters: Number of characters
            
        Returns:
            Cost in dollars
        """
        # Check for tiered pricing
        if backend in self.config.tiers:
            total_cost = 0.0
            for tier in self.config.tiers[backend]:
                total_cost += tier.calculate_cost(characters)
            return total_cost
        
        # Simple pricing
        cost_per_1k = self.config.pricing.get(backend, 0.0)
        return (characters / 1000) * cost_per_1k
    
    def attribute(
        self,
        client_id: str,
        characters: int,
        backend: str,
        voice: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> float:
        """
        Attribute cost to a client.
        
        Args:
            client_id: Client identifier
            characters: Characters synthesized
            backend: Backend used
            voice: Voice used
            metadata: Additional metadata
            
        Returns:
            Calculated cost
        """
        cost = self.calculate_cost(backend, characters)
        
        record = {
            "timestamp": time.time(),
            "client_id": client_id,
            "backend": backend,
            "voice": voice,
            "characters": characters,
            "cost": cost,
            "metadata": metadata or {},
        }
        
        self._records.append(record)
        
        # Cleanup old records
        self._cleanup()
        
        return cost
    
    def _cleanup(self) -> None:
        """Remove old records."""
        cutoff = time.time() - (self.config.retention_days * 86400)
        self._records = [r for r in self._records if r["timestamp"] > cutoff]
    
    def report(
        self,
        period: str,
        client_id: str | None = None,
    ) -> CostReport:
        """
        Generate a cost report.
        
        Args:
            period: Period string (YYYY-MM for month, YYYY for year)
            client_id: Optional client filter
            
        Returns:
            CostReport
        """
        # Parse period
        if len(period) == 7:  # YYYY-MM
            year, month = int(period[:4]), int(period[5:])
            start = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        elif len(period) == 4:  # YYYY
            year = int(period)
            start = datetime(year, 1, 1, tzinfo=timezone.utc)
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            raise ValueError(f"Invalid period format: {period}")
        
        start_ts = start.timestamp()
        end_ts = end.timestamp()
        
        # Filter records
        records = [
            r for r in self._records
            if start_ts <= r["timestamp"] < end_ts
            and (client_id is None or r["client_id"] == client_id)
        ]
        
        # Aggregate
        report = CostReport(
            period_start=start,
            period_end=end,
        )
        
        by_backend: dict[str, float] = defaultdict(float)
        by_client: dict[str, float] = defaultdict(float)
        by_voice: dict[str, float] = defaultdict(float)
        by_day: dict[str, float] = defaultdict(float)
        
        for record in records:
            cost = record["cost"]
            chars = record["characters"]
            
            report.total_cost += cost
            report.total_characters += chars
            report.total_requests += 1
            
            by_backend[record["backend"]] += cost
            
            if self.config.track_by_client:
                by_client[record["client_id"]] += cost
            
            if self.config.track_by_voice and record["voice"]:
                by_voice[record["voice"]] += cost
            
            # Group by day
            day = datetime.fromtimestamp(record["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d")
            by_day[day] += cost
        
        report.by_backend = dict(by_backend)
        report.by_client = dict(by_client)
        report.by_voice = dict(by_voice)
        report.by_day = dict(by_day)
        
        return report
    
    def get_client_usage(
        self,
        client_id: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Get usage summary for a client.
        
        Args:
            client_id: Client identifier
            days: Number of days to include
            
        Returns:
            Usage summary
        """
        cutoff = time.time() - (days * 86400)
        
        records = [
            r for r in self._records
            if r["timestamp"] > cutoff and r["client_id"] == client_id
        ]
        
        if not records:
            return {
                "client_id": client_id,
                "total_cost": 0.0,
                "total_characters": 0,
                "total_requests": 0,
                "daily_average": 0.0,
            }
        
        total_cost = sum(r["cost"] for r in records)
        total_chars = sum(r["characters"] for r in records)
        
        return {
            "client_id": client_id,
            "total_cost": total_cost,
            "total_characters": total_chars,
            "total_requests": len(records),
            "daily_average": total_cost / min(days, (time.time() - records[0]["timestamp"]) / 86400 + 1),
        }
    
    def forecast(
        self,
        days: int = 30,
    ) -> dict[str, float]:
        """
        Forecast costs for next period.
        
        Args:
            days: Number of days to forecast
            
        Returns:
            Forecast summary
        """
        # Use recent data to forecast
        recent_days = 7
        cutoff = time.time() - (recent_days * 86400)
        
        recent_records = [r for r in self._records if r["timestamp"] > cutoff]
        
        if not recent_records:
            return {
                "forecast_days": days,
                "estimated_cost": 0.0,
                "estimated_characters": 0,
                "estimated_requests": 0,
            }
        
        # Daily averages
        daily_cost = sum(r["cost"] for r in recent_records) / recent_days
        daily_chars = sum(r["characters"] for r in recent_records) / recent_days
        daily_requests = len(recent_records) / recent_days
        
        return {
            "forecast_days": days,
            "estimated_cost": daily_cost * days,
            "estimated_characters": int(daily_chars * days),
            "estimated_requests": int(daily_requests * days),
            "daily_average_cost": daily_cost,
        }
    
    def get_cheapest_backend(
        self,
        characters: int,
        exclude: list[str] | None = None,
    ) -> str:
        """
        Get the cheapest backend for given character count.
        
        Args:
            characters: Number of characters
            exclude: Backends to exclude
            
        Returns:
            Backend name
        """
        exclude = exclude or []
        
        cheapest = None
        cheapest_cost = float('inf')
        
        for backend, cost_per_1k in self.config.pricing.items():
            if backend in exclude:
                continue
            
            cost = self.calculate_cost(backend, characters)
            
            if cost < cheapest_cost:
                cheapest_cost = cost
                cheapest = backend
        
        return cheapest or "kokoro"
