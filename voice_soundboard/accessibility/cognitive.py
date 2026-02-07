"""
Cognitive Accessibility - Plain language, reading assistance.

This module provides accessibility features for users with
cognitive disabilities, learning disabilities, or those who
benefit from simplified content.

Components:
    PlainLanguage      - Simplify complex text
    ReadingAssistant   - Reading support features
    ConsistencyGuard   - Predictable patterns
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional


class ReadingLevel(Enum):
    """Target reading level for simplification."""
    GRADE_3 = 3
    GRADE_6 = 6
    GRADE_8 = 8
    GRADE_10 = 10
    GRADE_12 = 12


@dataclass
class PlainLanguageConfig:
    """Configuration for plain language mode."""
    reading_level: ReadingLevel = ReadingLevel.GRADE_6
    avoid_jargon: bool = True
    short_sentences: bool = True
    max_sentence_words: int = 15
    define_terms: bool = True
    use_active_voice: bool = True


class PlainLanguage:
    """Transform text to plain, accessible language.
    
    Simplifies complex text to make it accessible for users
    with cognitive disabilities or reading difficulties.
    
    Example:
        simplifier = PlainLanguage(reading_level=ReadingLevel.GRADE_6)
        
        complex = "The API utilizes asynchronous paradigms for optimal throughput."
        simple = simplifier.transform(complex)
        # "The program works on multiple tasks at once to run faster."
    """
    
    def __init__(self, config: Optional[PlainLanguageConfig] = None) -> None:
        """Initialize plain language transformer.
        
        Args:
            config: Plain language configuration
        """
        self.config = config or PlainLanguageConfig()
    
    def transform(self, text: str) -> str:
        """Transform text to plain language.
        
        Args:
            text: Original text
            
        Returns:
            Simplified text
        """
        result = text
        
        if self.config.avoid_jargon:
            result = self._replace_jargon(result)
        
        if self.config.short_sentences:
            result = self._shorten_sentences(result)
        
        return result
    
    def _replace_jargon(self, text: str) -> str:
        """Replace jargon with simpler terms."""
        # Common jargon replacements
        replacements = {
            "utilize": "use",
            "implement": "do",
            "paradigm": "pattern",
            "optimize": "improve",
            "leverage": "use",
            "synergy": "teamwork",
            "actionable": "useful",
            "bandwidth": "time",
            "deliverable": "result",
            "functionality": "feature",
            "proactive": "active",
            "scalable": "can grow",
        }
        
        result = text
        for jargon, simple in replacements.items():
            result = result.replace(jargon, simple)
            result = result.replace(jargon.capitalize(), simple.capitalize())
        
        return result
    
    def _shorten_sentences(self, text: str) -> str:
        """Break long sentences into shorter ones."""
        # Simple implementation - would use NLP in production
        sentences = text.split(". ")
        result = []
        
        for sentence in sentences:
            words = sentence.split()
            if len(words) > self.config.max_sentence_words:
                # Try to split at conjunctions
                for conj in [", and ", ", but ", ", or ", "; "]:
                    if conj in sentence:
                        parts = sentence.split(conj, 1)
                        result.extend(parts)
                        break
                else:
                    result.append(sentence)
            else:
                result.append(sentence)
        
        return ". ".join(result)
    
    def get_definitions(self, text: str) -> dict[str, str]:
        """Get definitions for complex terms in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict mapping terms to definitions
        """
        # Placeholder for term extraction and definition
        return {}
    
    def assess_readability(self, text: str) -> dict[str, Any]:
        """Assess text readability.
        
        Args:
            text: Text to assess
            
        Returns:
            Readability metrics
        """
        words = text.split()
        sentences = text.split(".")
        
        avg_word_length = sum(len(w) for w in words) / max(len(words), 1)
        avg_sentence_length = len(words) / max(len(sentences), 1)
        
        return {
            "word_count": len(words),
            "sentence_count": len(sentences),
            "avg_word_length": round(avg_word_length, 1),
            "avg_sentence_length": round(avg_sentence_length, 1),
            "estimated_grade_level": self._estimate_grade(avg_word_length, avg_sentence_length),
        }
    
    def _estimate_grade(self, avg_word_len: float, avg_sent_len: float) -> int:
        """Estimate reading grade level."""
        # Simplified Flesch-Kincaid approximation
        score = (0.39 * avg_sent_len) + (11.8 * avg_word_len / 5) - 15.59
        return max(1, min(12, int(score)))


@dataclass
class ReadingAssistantConfig:
    """Configuration for reading assistant."""
    highlight_current_word: bool = True
    highlight_current_sentence: bool = True
    word_spacing: str = "normal"  # normal, wide, extra-wide
    line_spacing: float = 1.5
    font: str = "system"  # system, OpenDyslexic, sans-serif
    show_ruler: bool = False
    syllable_breaks: bool = False


class ReadingAssistant:
    """Reading support features for accessibility.
    
    Provides visual aids and formatting to help users with
    dyslexia, visual processing issues, or reading difficulties.
    
    Example:
        assistant = ReadingAssistant(
            highlight_current_word=True,
            font="OpenDyslexic",
        )
        
        display = assistant.create_display(text)
        display.sync_with(engine)
    """
    
    def __init__(self, config: Optional[ReadingAssistantConfig] = None) -> None:
        """Initialize reading assistant.
        
        Args:
            config: Reading assistant configuration
        """
        self.config = config or ReadingAssistantConfig()
        self._ruler_position: int = 0
    
    def create_display(self, text: str) -> "ReadingDisplay":
        """Create a reading display for text.
        
        Args:
            text: Text to display
            
        Returns:
            ReadingDisplay instance
        """
        return ReadingDisplay(text, self)
    
    def enable_ruler(self) -> None:
        """Enable the reading ruler."""
        self.config.show_ruler = True
    
    def disable_ruler(self) -> None:
        """Disable the reading ruler."""
        self.config.show_ruler = False
    
    def enable_syllable_breaks(self) -> None:
        """Enable syllable hyphenation."""
        self.config.syllable_breaks = True
    
    def disable_syllable_breaks(self) -> None:
        """Disable syllable hyphenation."""
        self.config.syllable_breaks = False
    
    def format_for_dyslexia(self, text: str) -> str:
        """Format text with dyslexia-friendly features.
        
        Args:
            text: Original text
            
        Returns:
            Formatted text
        """
        if self.config.syllable_breaks:
            text = self._add_syllable_breaks(text)
        
        return text
    
    def _add_syllable_breaks(self, text: str) -> str:
        """Add syllable breaks to words."""
        # Simplified - would use proper hyphenation library
        # like pyphen in production
        return text


class ReadingDisplay:
    """Display with reading assistance features.
    
    Manages synchronized text display with highlighting
    and other visual aids.
    """
    
    def __init__(self, text: str, assistant: ReadingAssistant) -> None:
        """Initialize reading display.
        
        Args:
            text: Text to display
            assistant: ReadingAssistant with config
        """
        self.text = text
        self.assistant = assistant
        self.words = text.split()
        self.current_word_index = 0
        self.current_sentence_index = 0
    
    def sync_with(self, engine: Any) -> None:
        """Synchronize display with engine playback.
        
        Args:
            engine: VoiceEngine to sync with
        """
        # Placeholder for sync implementation
        pass
    
    def set_word(self, index: int) -> None:
        """Set current word index.
        
        Args:
            index: Word index to highlight
        """
        self.current_word_index = max(0, min(index, len(self.words) - 1))
    
    def next_word(self) -> Optional[str]:
        """Advance to next word.
        
        Returns:
            Current word or None if at end
        """
        if self.current_word_index < len(self.words) - 1:
            self.current_word_index += 1
            return self.words[self.current_word_index]
        return None
    
    def get_highlighted_html(self) -> str:
        """Get HTML with current word highlighted.
        
        Returns:
            HTML string with highlighting
        """
        parts = []
        for i, word in enumerate(self.words):
            if i == self.current_word_index:
                parts.append(f'<mark class="current-word">{word}</mark>')
            else:
                parts.append(word)
        return " ".join(parts)


@dataclass
class ConsistencyConfig:
    """Configuration for consistency guard."""
    announce_changes: bool = True
    confirm_destructive: bool = True
    consistent_navigation: bool = True
    timeout_warnings: bool = True
    timeout_warning_seconds: int = 30


class ConsistencyGuard:
    """Ensure predictable patterns in interaction.
    
    Provides guardrails and notifications to ensure the
    interface behaves predictably, reducing cognitive load.
    
    Example:
        guard = ConsistencyGuard(
            announce_changes=True,
            confirm_destructive=True,
        )
        
        engine = VoiceEngine(Config(consistency=guard))
    """
    
    def __init__(self, config: Optional[ConsistencyConfig] = None) -> None:
        """Initialize consistency guard.
        
        Args:
            config: Consistency configuration
        """
        self.config = config or ConsistencyConfig()
        self._pending_changes: list[str] = []
    
    def announce_change(self, change: str) -> None:
        """Announce a change to the user.
        
        Args:
            change: Description of the change
        """
        if self.config.announce_changes:
            self._pending_changes.append(change)
    
    def get_pending_announcements(self) -> list[str]:
        """Get pending change announcements.
        
        Returns:
            List of change descriptions
        """
        changes = self._pending_changes.copy()
        self._pending_changes.clear()
        return changes
    
    def should_confirm(self, action: str) -> bool:
        """Check if action requires confirmation.
        
        Args:
            action: Action name
            
        Returns:
            True if confirmation needed
        """
        destructive = {"delete", "clear", "reset", "remove", "cancel"}
        return self.config.confirm_destructive and action.lower() in destructive
    
    def timeout_warning_needed(self, elapsed_seconds: float) -> bool:
        """Check if timeout warning should be shown.
        
        Args:
            elapsed_seconds: Time elapsed
            
        Returns:
            True if warning needed
        """
        if not self.config.timeout_warnings:
            return False
        
        threshold = self.config.timeout_warning_seconds
        return elapsed_seconds >= threshold
