"""
Smart Silence - Semantic pause insertion.

Intelligently inserts silences based on:
    - Paragraph boundaries
    - List items
    - Sentence structure
    - Rhetorical questions
    - Dramatic effect

Language-aware heuristics for natural-sounding pauses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from enum import Enum, auto


class PauseType(Enum):
    """Types of pauses for different contexts."""
    
    MICRO = auto()       # 50-100ms - Between words
    SHORT = auto()       # 100-200ms - Comma, list item
    MEDIUM = auto()      # 200-400ms - Sentence end
    LONG = auto()        # 400-700ms - Paragraph
    DRAMATIC = auto()    # 700-1500ms - Dramatic effect
    CUSTOM = auto()      # User-specified


@dataclass
class SilenceConfig:
    """Configuration for smart silence insertion."""
    
    # Pause durations (milliseconds)
    paragraph_pause_ms: int = 500
    sentence_pause_ms: int = 250
    clause_pause_ms: int = 150
    list_item_pause_ms: int = 200
    dramatic_pause_ms: int = 800
    
    # Detection settings
    detect_paragraphs: bool = True
    detect_lists: bool = True
    detect_rhetorical_questions: bool = True
    detect_ellipsis: bool = True
    detect_em_dash: bool = True
    
    # Language settings
    language: str = "en"
    use_punctuation_rules: bool = True
    
    # Advanced settings
    max_consecutive_pauses: int = 2
    merge_close_pauses_ms: int = 100
    scale_factor: float = 1.0


@dataclass
class PauseMarker:
    """A pause marker in text."""
    
    position: int
    pause_type: PauseType
    duration_ms: int
    reason: str


@dataclass
class SilenceResult:
    """Result of smart silence analysis."""
    
    text: str
    markers: list[PauseMarker] = field(default_factory=list)
    total_pause_ms: int = 0
    
    def to_ssml(self) -> str:
        """Convert to SSML with break tags."""
        if not self.markers:
            return self.text
        
        result = []
        last_pos = 0
        
        for marker in sorted(self.markers, key=lambda m: m.position):
            # Add text before pause
            result.append(self.text[last_pos:marker.position])
            # Add break
            result.append(f'<break time="{marker.duration_ms}ms"/>')
            last_pos = marker.position
        
        # Add remaining text
        result.append(self.text[last_pos:])
        
        return "".join(result)
    
    def get_pauses_summary(self) -> dict[PauseType, int]:
        """Get count of each pause type."""
        summary: dict[PauseType, int] = {}
        for marker in self.markers:
            summary[marker.pause_type] = summary.get(marker.pause_type, 0) + 1
        return summary


class SmartSilence:
    """
    Intelligent silence insertion based on semantic boundaries.
    
    Example:
        silencer = SmartSilence(
            paragraph_pause_ms=500,
            list_item_pause_ms=200,
            dramatic_pause_ms=800,
            detect_rhetorical_questions=True,
        )
        
        text = '''
        First, we need to understand the problem.
        
        Second, we analyze the data. This includes:
        - User behavior
        - System metrics
        - Error rates
        
        Finally... we make our decision.
        '''
        
        result = silencer.analyze(text)
        ssml = result.to_ssml()
    """
    
    # Sentence endings
    SENTENCE_END = re.compile(r'[.!?]+(?:\s|$)')
    
    # Paragraph boundaries (double newline or blank line)
    PARAGRAPH_BREAK = re.compile(r'\n\s*\n')
    
    # List markers
    LIST_MARKER = re.compile(r'(?:^|\n)\s*(?:[-•*]|\d+[.)]|\w[.)])\s')
    
    # Clause boundaries
    CLAUSE_BOUNDARY = re.compile(r'[,;:]')
    
    # Ellipsis (dramatic pause)
    ELLIPSIS = re.compile(r'\.{3,}|…')
    
    # Em-dash (pause for emphasis)
    EM_DASH = re.compile(r'—|--')
    
    # Rhetorical question indicators
    RHETORICAL_PATTERNS = [
        re.compile(r'(?:^|\. )(?:Isn\'t it|Aren\'t we|Don\'t you|Wouldn\'t you|Couldn\'t we)[^?]*\?', re.I),
        re.compile(r'(?:^|\. )(?:Who knows|Who cares|Why bother)[^?]*\?', re.I),
        re.compile(r'(?:^|\. )What (?:is|are|was|were) (?:the point|the use)[^?]*\?', re.I),
    ]
    
    def __init__(
        self,
        paragraph_pause_ms: int = 500,
        list_item_pause_ms: int = 200,
        dramatic_pause_ms: int = 800,
        detect_rhetorical_questions: bool = True,
        config: SilenceConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = SilenceConfig(
                paragraph_pause_ms=paragraph_pause_ms,
                list_item_pause_ms=list_item_pause_ms,
                dramatic_pause_ms=dramatic_pause_ms,
                detect_rhetorical_questions=detect_rhetorical_questions,
            )
    
    def analyze(self, text: str) -> SilenceResult:
        """
        Analyze text for silence insertion points.
        
        Args:
            text: Input text to analyze
            
        Returns:
            SilenceResult with pause markers
        """
        markers: list[PauseMarker] = []
        
        # Detect paragraph breaks
        if self.config.detect_paragraphs:
            markers.extend(self._detect_paragraphs(text))
        
        # Detect list items
        if self.config.detect_lists:
            markers.extend(self._detect_lists(text))
        
        # Detect ellipsis
        if self.config.detect_ellipsis:
            markers.extend(self._detect_ellipsis(text))
        
        # Detect em-dashes
        if self.config.detect_em_dash:
            markers.extend(self._detect_em_dash(text))
        
        # Detect rhetorical questions
        if self.config.detect_rhetorical_questions:
            markers.extend(self._detect_rhetorical(text))
        
        # Detect sentence endings
        if self.config.use_punctuation_rules:
            markers.extend(self._detect_sentences(text))
            markers.extend(self._detect_clauses(text))
        
        # Merge close pauses and enforce limits
        markers = self._merge_and_limit(markers)
        
        # Apply scale factor
        for marker in markers:
            marker.duration_ms = int(marker.duration_ms * self.config.scale_factor)
        
        total_pause = sum(m.duration_ms for m in markers)
        
        return SilenceResult(
            text=text,
            markers=markers,
            total_pause_ms=total_pause,
        )
    
    def apply(self, text: str) -> str:
        """
        Apply smart silence and return SSML-annotated text.
        
        Args:
            text: Input text
            
        Returns:
            SSML-formatted text with break tags
        """
        result = self.analyze(text)
        return result.to_ssml()
    
    def _detect_paragraphs(self, text: str) -> list[PauseMarker]:
        """Detect paragraph boundaries."""
        markers = []
        
        for match in self.PARAGRAPH_BREAK.finditer(text):
            markers.append(PauseMarker(
                position=match.start(),
                pause_type=PauseType.LONG,
                duration_ms=self.config.paragraph_pause_ms,
                reason="paragraph_break",
            ))
        
        return markers
    
    def _detect_lists(self, text: str) -> list[PauseMarker]:
        """Detect list items."""
        markers = []
        
        for match in self.LIST_MARKER.finditer(text):
            markers.append(PauseMarker(
                position=match.start(),
                pause_type=PauseType.SHORT,
                duration_ms=self.config.list_item_pause_ms,
                reason="list_item",
            ))
        
        return markers
    
    def _detect_ellipsis(self, text: str) -> list[PauseMarker]:
        """Detect ellipsis for dramatic pauses."""
        markers = []
        
        for match in self.ELLIPSIS.finditer(text):
            markers.append(PauseMarker(
                position=match.end(),
                pause_type=PauseType.DRAMATIC,
                duration_ms=self.config.dramatic_pause_ms,
                reason="ellipsis",
            ))
        
        return markers
    
    def _detect_em_dash(self, text: str) -> list[PauseMarker]:
        """Detect em-dashes for emphasis pauses."""
        markers = []
        
        for match in self.EM_DASH.finditer(text):
            markers.append(PauseMarker(
                position=match.start(),
                pause_type=PauseType.SHORT,
                duration_ms=self.config.clause_pause_ms,
                reason="em_dash",
            ))
        
        return markers
    
    def _detect_rhetorical(self, text: str) -> list[PauseMarker]:
        """Detect rhetorical questions for dramatic pauses."""
        markers = []
        
        for pattern in self.RHETORICAL_PATTERNS:
            for match in pattern.finditer(text):
                markers.append(PauseMarker(
                    position=match.end(),
                    pause_type=PauseType.DRAMATIC,
                    duration_ms=self.config.dramatic_pause_ms,
                    reason="rhetorical_question",
                ))
        
        return markers
    
    def _detect_sentences(self, text: str) -> list[PauseMarker]:
        """Detect sentence endings."""
        markers = []
        
        for match in self.SENTENCE_END.finditer(text):
            markers.append(PauseMarker(
                position=match.end(),
                pause_type=PauseType.MEDIUM,
                duration_ms=self.config.sentence_pause_ms,
                reason="sentence_end",
            ))
        
        return markers
    
    def _detect_clauses(self, text: str) -> list[PauseMarker]:
        """Detect clause boundaries."""
        markers = []
        
        for match in self.CLAUSE_BOUNDARY.finditer(text):
            markers.append(PauseMarker(
                position=match.end(),
                pause_type=PauseType.SHORT,
                duration_ms=self.config.clause_pause_ms,
                reason="clause_boundary",
            ))
        
        return markers
    
    def _merge_and_limit(self, markers: list[PauseMarker]) -> list[PauseMarker]:
        """Merge close pauses and enforce limits."""
        if not markers:
            return markers
        
        # Sort by position
        markers.sort(key=lambda m: m.position)
        
        # Merge close pauses
        merged = []
        for marker in markers:
            if not merged:
                merged.append(marker)
                continue
            
            last = merged[-1]
            if marker.position - last.position < self.config.merge_close_pauses_ms:
                # Merge - keep the longer pause
                if marker.duration_ms > last.duration_ms:
                    merged[-1] = marker
            else:
                merged.append(marker)
        
        # Enforce max consecutive limit
        limited = []
        consecutive = 0
        last_pos = -999
        
        for marker in merged:
            if marker.position - last_pos < 50:  # Close proximity
                consecutive += 1
                if consecutive > self.config.max_consecutive_pauses:
                    continue
            else:
                consecutive = 1
            
            limited.append(marker)
            last_pos = marker.position
        
        return limited
