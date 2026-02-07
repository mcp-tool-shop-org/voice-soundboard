"""
Input Validation - SSML and markup injection prevention.

Protects against:
    - SSML injection attacks
    - Markup injection
    - Oversized inputs
    - Malicious character sequences
    - Script injection via audio parameters
"""

from __future__ import annotations

import re
import html
from dataclasses import dataclass, field
from typing import Any, Protocol
from enum import Enum, auto


class ValidationError(Exception):
    """Raised when input validation fails."""
    
    def __init__(self, error_type: str, message: str, position: int | None = None):
        self.error_type = error_type
        self.position = position
        super().__init__(f"Validation error ({error_type}): {message}")


class InjectionType(Enum):
    """Types of injection attacks detected."""
    SSML = auto()
    XML = auto()
    SCRIPT = auto()
    COMMAND = auto()
    PATH_TRAVERSAL = auto()


@dataclass
class ValidationConfig:
    """Configuration for input validation."""
    
    # Length limits
    max_length: int = 10000
    max_line_length: int = 1000
    
    # SSML handling
    allow_ssml: bool = True
    ssml_tags_allowed: list[str] = field(default_factory=lambda: [
        "speak", "voice", "prosody", "break", "emphasis",
        "say-as", "sub", "phoneme", "audio", "p", "s",
    ])
    ssml_attributes_allowed: dict[str, list[str]] = field(default_factory=lambda: {
        "voice": ["name", "language", "gender"],
        "prosody": ["rate", "pitch", "volume", "duration"],
        "break": ["time", "strength"],
        "emphasis": ["level"],
        "say-as": ["interpret-as", "format", "detail"],
        "sub": ["alias"],
        "phoneme": ["alphabet", "ph"],
        "audio": ["src"],
    })
    
    # Sanitization options
    sanitize_markup: bool = True
    escape_html: bool = True
    normalize_whitespace: bool = True
    strip_control_chars: bool = True
    
    # Security options
    block_script_patterns: bool = True
    block_command_injection: bool = True
    block_path_traversal: bool = True
    
    # Logging
    log_rejected_inputs: bool = True


@dataclass
class ValidationResult:
    """Result of input validation."""
    
    valid: bool
    sanitized_text: str
    original_length: int
    sanitized_length: int
    warnings: list[str] = field(default_factory=list)
    blocked_content: list[tuple[InjectionType, str]] = field(default_factory=list)


class SSMLSanitizer:
    """Sanitizes SSML content while preserving valid markup."""
    
    # Pattern for SSML tags
    TAG_PATTERN = re.compile(r"<(/?)(\w+)([^>]*)>")
    
    # Pattern for SSML attributes
    ATTR_PATTERN = re.compile(r'(\w+)\s*=\s*(?:"([^"]*?)"|\'([^\']*?)\')')
    
    def __init__(self, config: ValidationConfig):
        self.config = config
    
    def sanitize(self, text: str) -> tuple[str, list[str]]:
        """
        Sanitize SSML content.
        
        Returns (sanitized_text, list of removed elements).
        """
        removed = []
        
        def replace_tag(match: re.Match) -> str:
            closing = match.group(1) == "/"
            tag_name = match.group(2).lower()
            attributes = match.group(3)
            
            # Check if tag is allowed
            if tag_name not in self.config.ssml_tags_allowed:
                removed.append(f"tag:{tag_name}")
                return ""
            
            # Sanitize attributes
            if not closing and attributes:
                sanitized_attrs = self._sanitize_attributes(tag_name, attributes, removed)
                if sanitized_attrs:
                    return f"<{tag_name} {sanitized_attrs}>"
                return f"<{tag_name}>"
            
            return match.group(0)
        
        sanitized = self.TAG_PATTERN.sub(replace_tag, text)
        return sanitized, removed
    
    def _sanitize_attributes(
        self,
        tag_name: str,
        attributes: str,
        removed: list[str],
    ) -> str:
        """Sanitize tag attributes."""
        allowed_attrs = self.config.ssml_attributes_allowed.get(tag_name, [])
        sanitized_parts = []
        
        for match in self.ATTR_PATTERN.finditer(attributes):
            attr_name = match.group(1).lower()
            attr_value = match.group(2) or match.group(3) or ""
            
            if attr_name in allowed_attrs:
                # Escape attribute value
                safe_value = html.escape(attr_value, quote=True)
                sanitized_parts.append(f'{attr_name}="{safe_value}"')
            else:
                removed.append(f"attr:{tag_name}@{attr_name}")
        
        return " ".join(sanitized_parts)
    
    def is_balanced(self, text: str) -> bool:
        """Check if SSML tags are properly balanced."""
        stack = []
        
        for match in self.TAG_PATTERN.finditer(text):
            closing = match.group(1) == "/"
            tag_name = match.group(2).lower()
            
            if closing:
                if not stack or stack[-1] != tag_name:
                    return False
                stack.pop()
            else:
                stack.append(tag_name)
        
        return len(stack) == 0


class InputValidator:
    """
    Validates and sanitizes user input for TTS synthesis.
    
    Example:
        validator = InputValidator(
            max_length=10000,
            allow_ssml=True,
            sanitize_markup=True,
        )
        
        safe_text = validator.validate(user_input)
        engine.speak(safe_text)
    """
    
    # Dangerous patterns
    SCRIPT_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.I | re.S),
        re.compile(r"javascript:", re.I),
        re.compile(r"on\w+\s*=", re.I),
        re.compile(r"data:text/html", re.I),
    ]
    
    COMMAND_PATTERNS = [
        re.compile(r"\$\([^)]+\)"),  # $(command)
        re.compile(r"`[^`]+`"),  # `command`
        re.compile(r"\|\s*\w+"),  # | pipe
        re.compile(r";\s*\w+"),  # ; chain
        re.compile(r"&&\s*\w+"),  # && chain
    ]
    
    PATH_TRAVERSAL_PATTERNS = [
        re.compile(r"\.\.[\\/]"),  # ../
        re.compile(r"[\\/]etc[\\/]"),  # /etc/
        re.compile(r"[\\/]proc[\\/]"),  # /proc/
        re.compile(r"\\\\[\w]+\\"),  # \\server\
    ]
    
    # Control characters to strip
    CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    
    def __init__(
        self,
        max_length: int = 10000,
        allow_ssml: bool = True,
        sanitize_markup: bool = True,
        config: ValidationConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = ValidationConfig(
                max_length=max_length,
                allow_ssml=allow_ssml,
                sanitize_markup=sanitize_markup,
            )
        
        self._ssml_sanitizer = SSMLSanitizer(self.config) if allow_ssml else None
    
    def validate(self, text: str, raise_on_error: bool = True) -> str:
        """
        Validate and sanitize input text.
        
        Args:
            text: Input text to validate
            raise_on_error: If True, raise ValidationError on issues
            
        Returns:
            Sanitized text safe for TTS synthesis
        """
        result = self.validate_full(text)
        
        if not result.valid and raise_on_error:
            if result.blocked_content:
                injection_type, content = result.blocked_content[0]
                raise ValidationError(
                    injection_type.name.lower(),
                    f"Blocked potentially dangerous content: {content[:50]}...",
                )
        
        return result.sanitized_text
    
    def validate_full(self, text: str) -> ValidationResult:
        """
        Perform full validation with detailed results.
        
        Returns:
            ValidationResult with sanitized text and metadata
        """
        result = ValidationResult(
            valid=True,
            sanitized_text=text,
            original_length=len(text),
            sanitized_length=len(text),
        )
        
        # Check length
        if len(text) > self.config.max_length:
            result.warnings.append(f"Text truncated from {len(text)} to {self.config.max_length}")
            text = text[:self.config.max_length]
        
        # Strip control characters
        if self.config.strip_control_chars:
            text = self.CONTROL_CHARS.sub("", text)
        
        # Check for dangerous patterns
        if self.config.block_script_patterns:
            for pattern in self.SCRIPT_PATTERNS:
                match = pattern.search(text)
                if match:
                    result.valid = False
                    result.blocked_content.append((InjectionType.SCRIPT, match.group()))
                    text = pattern.sub("", text)
        
        if self.config.block_command_injection:
            for pattern in self.COMMAND_PATTERNS:
                match = pattern.search(text)
                if match:
                    result.valid = False
                    result.blocked_content.append((InjectionType.COMMAND, match.group()))
                    text = pattern.sub("", text)
        
        if self.config.block_path_traversal:
            for pattern in self.PATH_TRAVERSAL_PATTERNS:
                match = pattern.search(text)
                if match:
                    result.valid = False
                    result.blocked_content.append((InjectionType.PATH_TRAVERSAL, match.group()))
                    text = pattern.sub("", text)
        
        # Handle SSML
        if self.config.allow_ssml and self._ssml_sanitizer:
            text, removed = self._ssml_sanitizer.sanitize(text)
            if removed:
                result.warnings.extend(f"Removed {item}" for item in removed)
        elif self.config.sanitize_markup:
            # Escape all markup if SSML not allowed
            text = html.escape(text)
        
        # Normalize whitespace
        if self.config.normalize_whitespace:
            text = " ".join(text.split())
        
        result.sanitized_text = text
        result.sanitized_length = len(text)
        
        return result
    
    def is_safe(self, text: str) -> bool:
        """Quick check if text is safe without sanitization."""
        result = self.validate_full(text)
        return result.valid and not result.blocked_content
