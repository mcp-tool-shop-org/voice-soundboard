"""
v3.1 Validation System - Actionable Errors for AudioGraph.

Provides early failure with clear, actionable error messages that help
humans, tools, and agents understand what went wrong and how to fix it.

Design principle: Every error should answer:
1. WHAT is wrong?
2. WHERE in the graph?
3. WHY is it a problem?
4. HOW to fix it?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""
    
    ERROR = "error"      # Graph cannot be rendered
    WARNING = "warning"  # Graph will render but may have issues
    INFO = "info"        # Suggestion for improvement


@dataclass
class ValidationError:
    """A single validation issue with actionable details.
    
    Every error provides:
    - location: Path to the problematic element (e.g., "tracks[0].effects[2]")
    - message: Human-readable description of the issue
    - severity: ERROR, WARNING, or INFO
    - suggestion: Actionable fix suggestion
    - docs_link: Optional link to relevant documentation
    """
    location: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    suggestion: str | None = None
    docs_link: str | None = None
    
    # Context for programmatic handling
    code: str = "UNKNOWN"  # e.g., "INVALID_SAMPLE_RATE"
    context: dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        parts = [f"{self.severity.value.upper()}: {self.location}: {self.message}"]
        if self.suggestion:
            parts.append(f"  Suggestion: {self.suggestion}")
        if self.docs_link:
            parts.append(f"  Docs: {self.docs_link}")
        return "\n".join(parts)
    
    @classmethod
    def invalid_sample_rate(cls, location: str, rate: int) -> ValidationError:
        """Factory for invalid sample rate errors."""
        return cls(
            location=location,
            message=f"Invalid sample rate: {rate} Hz",
            severity=ValidationSeverity.ERROR,
            suggestion="Use a standard sample rate: 22050, 24000, 44100, or 48000 Hz",
            code="INVALID_SAMPLE_RATE",
            context={"rate": rate, "valid_rates": [22050, 24000, 44100, 48000]},
        )
    
    @classmethod
    def empty_track(cls, location: str, track_name: str) -> ValidationError:
        """Factory for empty track warnings."""
        return cls(
            location=location,
            message=f"Track '{track_name}' has no content",
            severity=ValidationSeverity.WARNING,
            suggestion="Add audio content to the track or remove it",
            code="EMPTY_TRACK",
            context={"track_name": track_name},
        )
    
    @classmethod
    def orphaned_effect(cls, location: str, effect_name: str) -> ValidationError:
        """Factory for orphaned effect errors."""
        return cls(
            location=location,
            message=f"Effect '{effect_name}' has no input source",
            severity=ValidationSeverity.ERROR,
            suggestion="Connect the effect to a track or another effect",
            code="ORPHANED_EFFECT",
            context={"effect_name": effect_name},
        )
    
    @classmethod
    def cycle_detected(cls, location: str, path: list[str]) -> ValidationError:
        """Factory for cycle detection errors."""
        cycle_str = " -> ".join(path)
        return cls(
            location=location,
            message=f"Audio routing cycle detected: {cycle_str}",
            severity=ValidationSeverity.ERROR,
            suggestion="Remove the connection creating the cycle",
            code="CYCLE_DETECTED",
            context={"cycle_path": path},
        )
    
    @classmethod
    def invalid_parameter(cls, location: str, param: str, value: Any, 
                          valid_range: tuple[Any, Any] | None = None) -> ValidationError:
        """Factory for invalid parameter errors."""
        msg = f"Invalid value for '{param}': {value}"
        suggestion = None
        if valid_range:
            suggestion = f"Value must be between {valid_range[0]} and {valid_range[1]}"
        return cls(
            location=location,
            message=msg,
            severity=ValidationSeverity.ERROR,
            suggestion=suggestion,
            code="INVALID_PARAMETER",
            context={"param": param, "value": value, "valid_range": valid_range},
        )
    
    @classmethod
    def missing_speaker(cls, location: str) -> ValidationError:
        """Factory for missing speaker reference."""
        return cls(
            location=location,
            message="No speaker reference assigned",
            severity=ValidationSeverity.ERROR,
            suggestion="Set a speaker using set_speaker(SpeakerRef.from_voice('voice_id'))",
            code="MISSING_SPEAKER",
        )
    
    @classmethod
    def incompatible_sample_rates(cls, location: str, rates: list[int]) -> ValidationError:
        """Factory for mismatched sample rates across tracks."""
        return cls(
            location=location,
            message=f"Tracks have incompatible sample rates: {rates}",
            severity=ValidationSeverity.WARNING,
            suggestion="Consider using the same sample rate for all tracks to avoid resampling",
            code="INCOMPATIBLE_SAMPLE_RATES",
            context={"rates": rates},
        )
    
    @classmethod
    def effect_chain_too_deep(cls, location: str, depth: int, max_depth: int) -> ValidationError:
        """Factory for excessively deep effect chains."""
        return cls(
            location=location,
            message=f"Effect chain depth ({depth}) exceeds maximum ({max_depth})",
            severity=ValidationSeverity.ERROR,
            suggestion="Reduce effect chain depth or use parallel processing",
            code="EFFECT_CHAIN_TOO_DEEP",
            context={"depth": depth, "max_depth": max_depth},
        )
    
    @classmethod
    def plugin_violation(cls, location: str, plugin_name: str, violation: str) -> ValidationError:
        """Factory for plugin sandbox violations."""
        return cls(
            location=location,
            message=f"Plugin '{plugin_name}' violates sandbox rules: {violation}",
            severity=ValidationSeverity.ERROR,
            suggestion="Fix the plugin to comply with sandbox restrictions",
            code="PLUGIN_VIOLATION",
            context={"plugin_name": plugin_name, "violation": violation},
        )


@dataclass
class ValidationResult:
    """Result of graph validation.
    
    Contains all validation errors organized by severity.
    Provides helpers for quick checks.
    """
    errors: list[ValidationError] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """True if no ERROR-level issues."""
        return not any(e.severity == ValidationSeverity.ERROR for e in self.errors)
    
    @property
    def has_warnings(self) -> bool:
        """True if any WARNING-level issues."""
        return any(e.severity == ValidationSeverity.WARNING for e in self.errors)
    
    @property
    def error_count(self) -> int:
        """Number of ERROR-level issues."""
        return sum(1 for e in self.errors if e.severity == ValidationSeverity.ERROR)
    
    @property
    def warning_count(self) -> int:
        """Number of WARNING-level issues."""
        return sum(1 for e in self.errors if e.severity == ValidationSeverity.WARNING)
    
    def filter_by_severity(self, severity: ValidationSeverity) -> list[ValidationError]:
        """Get errors of a specific severity."""
        return [e for e in self.errors if e.severity == severity]
    
    def filter_by_code(self, code: str) -> list[ValidationError]:
        """Get errors with a specific error code."""
        return [e for e in self.errors if e.code == code]
    
    def add(self, error: ValidationError) -> None:
        """Add an error to the result."""
        self.errors.append(error)
    
    def merge(self, other: ValidationResult) -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
    
    def raise_if_invalid(self) -> None:
        """Raise ValidationException if any ERROR-level issues."""
        if not self.is_valid:
            raise GraphValidationException(self)
    
    def __str__(self) -> str:
        if not self.errors:
            return "Validation passed"
        
        lines = [f"Validation found {len(self.errors)} issue(s):"]
        for err in self.errors:
            lines.append(f"  {err}")
        return "\n".join(lines)
    
    def __bool__(self) -> bool:
        """False if any errors, True if clean."""
        return self.is_valid
    
    def __iter__(self):
        """Iterate over errors."""
        return iter(self.errors)
    
    def __len__(self) -> int:
        """Number of errors."""
        return len(self.errors)


class GraphValidationException(Exception):
    """Raised when graph validation fails with ERROR-level issues."""
    
    def __init__(self, result: ValidationResult):
        self.result = result
        super().__init__(str(result))
