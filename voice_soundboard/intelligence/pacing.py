"""
Adaptive Pacing - Content-aware speech rate adjustment.

Automatically adjusts speech rate based on content complexity:
    - Slow down for numbers and technical content
    - Speed up for conversational phrases
    - Add micro-pauses between list items
    - Emphasize important terms

Operates at the graph level, not inside the engine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from enum import Enum, auto


class ContentType(Enum):
    """Types of content that affect pacing."""
    
    CONVERSATIONAL = auto()  # Normal speech
    TECHNICAL = auto()       # Technical terms, APIs
    NUMBERS = auto()         # Numbers, dates, times
    LIST = auto()            # List items
    QUOTATION = auto()       # Quoted text
    EMPHASIS = auto()        # Emphasized text
    ABBREVIATION = auto()    # Acronyms, abbreviations
    FOREIGN = auto()         # Foreign words/phrases


@dataclass
class PacingConfig:
    """Configuration for adaptive pacing."""
    
    # Base rate
    base_wpm: int = 150  # Words per minute
    
    # Content-specific adjustments
    slow_for_numbers: bool = True
    number_speed_factor: float = 0.8
    
    slow_for_technical: bool = True
    technical_speed_factor: float = 0.85
    
    slow_for_abbreviations: bool = True
    abbreviation_speed_factor: float = 0.7
    
    # Pauses
    pause_at_lists: bool = True
    list_pause_ms: int = 200
    
    pause_between_digits: bool = True
    digit_pause_ms: int = 100
    
    # Emphasis
    emphasize_important: bool = True
    emphasis_speed_factor: float = 0.9
    
    # Detection settings
    technical_word_min_length: int = 8
    detect_camelcase: bool = True
    detect_code_patterns: bool = True


@dataclass
class PacingSegment:
    """A segment of text with pacing information."""
    
    text: str
    content_type: ContentType
    speed_factor: float = 1.0
    pause_before_ms: int = 0
    pause_after_ms: int = 0
    emphasis: bool = False


@dataclass
class PacingResult:
    """Result of adaptive pacing analysis."""
    
    segments: list[PacingSegment] = field(default_factory=list)
    original_text: str = ""
    average_speed_factor: float = 1.0
    total_pause_ms: int = 0
    
    def get_effective_wpm(self, base_wpm: int = 150) -> float:
        """Calculate effective words per minute."""
        return base_wpm * self.average_speed_factor
    
    def to_ssml(self) -> str:
        """Convert to SSML markup for TTS engines."""
        parts = []
        
        for segment in self.segments:
            if segment.pause_before_ms > 0:
                parts.append(f'<break time="{segment.pause_before_ms}ms"/>')
            
            if segment.speed_factor != 1.0:
                rate_percent = int(segment.speed_factor * 100)
                parts.append(f'<prosody rate="{rate_percent}%">{segment.text}</prosody>')
            else:
                parts.append(segment.text)
            
            if segment.pause_after_ms > 0:
                parts.append(f'<break time="{segment.pause_after_ms}ms"/>')
        
        return "".join(parts)


class AdaptivePacer:
    """
    Automatically adjust speech rate based on content complexity.
    
    Example:
        pacer = AdaptivePacer(
            base_wpm=150,
            slow_for_numbers=True,
            slow_for_technical=True,
            pause_at_lists=True,
        )
        
        # Complex technical content slows down
        text = "The API returns a JSON object with fields: id (integer), name (string)."
        result = pacer.analyze(text)
        
        # Numbers read more clearly
        text = "Your confirmation number is 7 4 2 9 1 8 3."
        result = pacer.analyze(text)
        # Automatically adds micro-pauses between digits
    """
    
    # Patterns for content detection
    NUMBER_PATTERN = re.compile(r'\b\d+(?:[,\.]\d+)*\b')
    PHONE_PATTERN = re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b')
    DATE_PATTERN = re.compile(r'\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b')
    TIME_PATTERN = re.compile(r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b')
    
    CAMELCASE_PATTERN = re.compile(r'\b[a-z]+(?:[A-Z][a-z]+)+\b')
    SNAKE_CASE_PATTERN = re.compile(r'\b[a-z]+(?:_[a-z]+)+\b')
    
    ABBREVIATION_PATTERN = re.compile(r'\b[A-Z]{2,}(?:\.[A-Z]+)*\b')
    
    LIST_MARKERS = re.compile(r'(?:^|\n)\s*(?:[-•*]|\d+[.)]\s|\w[.)]\s)')
    
    TECHNICAL_TERMS = {
        "api", "json", "xml", "html", "css", "http", "https", "url", "uri",
        "sql", "nosql", "database", "server", "client", "frontend", "backend",
        "algorithm", "function", "parameter", "variable", "method", "class",
        "object", "array", "string", "integer", "boolean", "float", "double",
        "async", "await", "promise", "callback", "middleware", "endpoint",
        "timestamp", "iso", "utf", "ascii", "unicode", "regex", "schema",
    }
    
    def __init__(
        self,
        base_wpm: int = 150,
        slow_for_numbers: bool = True,
        slow_for_technical: bool = True,
        pause_at_lists: bool = True,
        config: PacingConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = PacingConfig(
                base_wpm=base_wpm,
                slow_for_numbers=slow_for_numbers,
                slow_for_technical=slow_for_technical,
                pause_at_lists=pause_at_lists,
            )
    
    def analyze(self, text: str) -> PacingResult:
        """
        Analyze text and create pacing segments.
        
        Args:
            text: Input text to analyze
            
        Returns:
            PacingResult with segments and timing info
        """
        segments = []
        
        # Tokenize and analyze
        tokens = self._tokenize(text)
        
        for i, (token, content_type) in enumerate(tokens):
            speed_factor = self._get_speed_factor(content_type, token)
            pause_before = 0
            pause_after = 0
            
            # Add pauses based on content type
            if content_type == ContentType.LIST:
                pause_before = self.config.list_pause_ms
            
            if content_type == ContentType.NUMBERS and self.config.pause_between_digits:
                # Add pause after number
                pause_after = self.config.digit_pause_ms
            
            segments.append(PacingSegment(
                text=token,
                content_type=content_type,
                speed_factor=speed_factor,
                pause_before_ms=pause_before,
                pause_after_ms=pause_after,
            ))
        
        # Calculate averages
        if segments:
            avg_speed = sum(s.speed_factor for s in segments) / len(segments)
            total_pause = sum(s.pause_before_ms + s.pause_after_ms for s in segments)
        else:
            avg_speed = 1.0
            total_pause = 0
        
        return PacingResult(
            segments=segments,
            original_text=text,
            average_speed_factor=avg_speed,
            total_pause_ms=total_pause,
        )
    
    def apply(self, text: str) -> str:
        """
        Apply adaptive pacing and return SSML-annotated text.
        
        Args:
            text: Input text
            
        Returns:
            SSML-formatted text with pacing annotations
        """
        result = self.analyze(text)
        return result.to_ssml()
    
    def _tokenize(self, text: str) -> list[tuple[str, ContentType]]:
        """Tokenize text and classify content types."""
        tokens = []
        remaining = text
        
        while remaining:
            # Try to match special patterns first
            match, content_type, consumed = self._match_special(remaining)
            
            if match:
                tokens.append((match, content_type))
                remaining = remaining[consumed:]
            else:
                # Find next special pattern or end
                next_special = self._find_next_special(remaining)
                
                if next_special > 0:
                    # Process regular text before special pattern
                    regular_text = remaining[:next_special]
                    tokens.extend(self._process_regular(regular_text))
                    remaining = remaining[next_special:]
                else:
                    # Process all remaining text
                    tokens.extend(self._process_regular(remaining))
                    remaining = ""
        
        return tokens
    
    def _match_special(self, text: str) -> tuple[str | None, ContentType | None, int]:
        """Try to match special content patterns at start of text."""
        # Phone numbers
        match = self.PHONE_PATTERN.match(text)
        if match:
            return match.group(), ContentType.NUMBERS, match.end()
        
        # Dates
        match = self.DATE_PATTERN.match(text)
        if match:
            return match.group(), ContentType.NUMBERS, match.end()
        
        # Times
        match = self.TIME_PATTERN.match(text)
        if match:
            return match.group(), ContentType.NUMBERS, match.end()
        
        # Numbers
        match = self.NUMBER_PATTERN.match(text)
        if match:
            return match.group(), ContentType.NUMBERS, match.end()
        
        # Abbreviations
        match = self.ABBREVIATION_PATTERN.match(text)
        if match:
            return match.group(), ContentType.ABBREVIATION, match.end()
        
        # CamelCase
        if self.config.detect_camelcase:
            match = self.CAMELCASE_PATTERN.match(text)
            if match:
                return match.group(), ContentType.TECHNICAL, match.end()
        
        # snake_case
        if self.config.detect_code_patterns:
            match = self.SNAKE_CASE_PATTERN.match(text)
            if match:
                return match.group(), ContentType.TECHNICAL, match.end()
        
        return None, None, 0
    
    def _find_next_special(self, text: str) -> int:
        """Find position of next special pattern."""
        patterns = [
            self.NUMBER_PATTERN,
            self.PHONE_PATTERN,
            self.DATE_PATTERN,
            self.TIME_PATTERN,
            self.ABBREVIATION_PATTERN,
        ]
        
        if self.config.detect_camelcase:
            patterns.append(self.CAMELCASE_PATTERN)
        if self.config.detect_code_patterns:
            patterns.append(self.SNAKE_CASE_PATTERN)
        
        earliest = len(text)
        
        for pattern in patterns:
            match = pattern.search(text)
            if match and match.start() < earliest:
                earliest = match.start()
        
        return earliest if earliest < len(text) else 0
    
    def _process_regular(self, text: str) -> list[tuple[str, ContentType]]:
        """Process regular text and detect content types."""
        tokens = []
        words = text.split()
        
        for word in words:
            content_type = self._classify_word(word)
            tokens.append((word + " ", content_type))
        
        return tokens
    
    def _classify_word(self, word: str) -> ContentType:
        """Classify a word's content type."""
        word_lower = word.lower().strip(".,!?\"'()[]{}:;")
        
        # Check for technical terms
        if word_lower in self.TECHNICAL_TERMS:
            return ContentType.TECHNICAL
        
        # Check word length (long words may be technical)
        if len(word_lower) >= self.config.technical_word_min_length:
            return ContentType.TECHNICAL
        
        # Check for list markers
        if self.LIST_MARKERS.match(word):
            return ContentType.LIST
        
        return ContentType.CONVERSATIONAL
    
    def _get_speed_factor(self, content_type: ContentType, text: str) -> float:
        """Get speed factor for content type."""
        factors = {
            ContentType.CONVERSATIONAL: 1.0,
            ContentType.TECHNICAL: self.config.technical_speed_factor if self.config.slow_for_technical else 1.0,
            ContentType.NUMBERS: self.config.number_speed_factor if self.config.slow_for_numbers else 1.0,
            ContentType.LIST: 1.0,
            ContentType.QUOTATION: 0.95,
            ContentType.EMPHASIS: self.config.emphasis_speed_factor if self.config.emphasize_important else 1.0,
            ContentType.ABBREVIATION: self.config.abbreviation_speed_factor if self.config.slow_for_abbreviations else 1.0,
            ContentType.FOREIGN: 0.85,
        }
        
        return factors.get(content_type, 1.0)
