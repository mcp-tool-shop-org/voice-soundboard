"""
Script parsing for conversations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterator

from voice_soundboard.conversation.speaker import Speaker
from voice_soundboard.conversation.turn import Turn


@dataclass
class ParsedLine:
    """A parsed line from a script."""
    
    speaker_id: str
    text: str
    is_action: bool = False
    line_number: int = 0


class ScriptParser:
    """Parse dialogue scripts into conversation turns.
    
    Supports multiple formats:
    - Simple: "SPEAKER: text"
    - Bracketed: "[SPEAKER] text"
    - JSON-like: {"speaker": "...", "text": "..."}
    
    Example:
        parser = ScriptParser()
        
        script = '''
        ALICE: Hello everyone!
        BOB: Welcome to the show.
        ALICE: Today we'll discuss voice synthesis.
        '''
        
        turns = parser.parse(script)
        for turn in turns:
            print(f"{turn.speaker_id}: {turn.text}")
    """
    
    # Regex patterns for different formats
    PATTERNS = {
        "colon": re.compile(r"^([A-Z][A-Z0-9_]*)\s*:\s*(.+)$", re.MULTILINE),
        "bracket": re.compile(r"^\[([^\]]+)\]\s*(.+)$", re.MULTILINE),
        "action": re.compile(r"\*([^*]+)\*"),
        "stage_direction": re.compile(r"\(([^)]+)\)"),
    }
    
    def __init__(
        self,
        normalize_speakers: bool = True,
        infer_speakers: bool = True,
    ):
        """Initialize parser.
        
        Args:
            normalize_speakers: Normalize speaker names to lowercase.
            infer_speakers: Create speakers from script if not defined.
        """
        self.normalize_speakers = normalize_speakers
        self.infer_speakers = infer_speakers
        self._speakers: dict[str, Speaker] = {}
    
    def register_speaker(
        self,
        name: str,
        speaker: Speaker,
    ) -> "ScriptParser":
        """Register a speaker for the parser.
        
        Args:
            name: Speaker name as it appears in script.
            speaker: Speaker configuration.
        
        Returns:
            Self for chaining.
        """
        key = name.lower() if self.normalize_speakers else name
        self._speakers[key] = speaker
        return self
    
    def parse(
        self,
        script: str,
        format: str = "auto",
    ) -> list[Turn]:
        """Parse a script into turns.
        
        Args:
            script: Script text to parse.
            format: Format hint ("colon", "bracket", "auto").
        
        Returns:
            List of Turn objects.
        """
        lines = self._split_lines(script)
        parsed = list(self._parse_lines(lines, format))
        
        turns = []
        for p in parsed:
            if p.is_action:
                turns.append(Turn.action(p.speaker_id, p.text))
            else:
                turns.append(Turn.speech(p.speaker_id, p.text))
        
        return turns
    
    def get_speakers(self) -> dict[str, Speaker]:
        """Get all speakers found or registered.
        
        Returns:
            Dictionary of speaker_id to Speaker.
        """
        return self._speakers.copy()
    
    def _split_lines(self, script: str) -> list[str]:
        """Split script into non-empty lines."""
        return [
            line.strip()
            for line in script.strip().split("\n")
            if line.strip()
        ]
    
    def _parse_lines(
        self,
        lines: list[str],
        format: str,
    ) -> Iterator[ParsedLine]:
        """Parse lines into ParsedLine objects."""
        for i, line in enumerate(lines, 1):
            parsed = self._parse_line(line, format)
            if parsed:
                parsed.line_number = i
                
                # Register speaker if not known
                speaker_key = (
                    parsed.speaker_id.lower()
                    if self.normalize_speakers
                    else parsed.speaker_id
                )
                
                if speaker_key not in self._speakers and self.infer_speakers:
                    # Create default speaker
                    self._speakers[speaker_key] = Speaker(
                        voice="af_bella",  # Default voice
                        name=parsed.speaker_id,
                    )
                
                # Use normalized speaker ID
                parsed.speaker_id = speaker_key
                yield parsed
    
    def _parse_line(self, line: str, format: str) -> ParsedLine | None:
        """Parse a single line."""
        # Try colon format: SPEAKER: text
        if format in ("auto", "colon"):
            match = self.PATTERNS["colon"].match(line)
            if match:
                speaker = match.group(1)
                text = match.group(2).strip()
                is_action = self._is_action(text)
                return ParsedLine(speaker, text, is_action)
        
        # Try bracket format: [SPEAKER] text
        if format in ("auto", "bracket"):
            match = self.PATTERNS["bracket"].match(line)
            if match:
                speaker = match.group(1)
                text = match.group(2).strip()
                is_action = self._is_action(text)
                return ParsedLine(speaker, text, is_action)
        
        return None
    
    def _is_action(self, text: str) -> bool:
        """Check if text is an action/stage direction."""
        # Actions are *italicized* or (in parentheses)
        return bool(
            self.PATTERNS["action"].fullmatch(text)
            or self.PATTERNS["stage_direction"].fullmatch(text)
        )


def parse_script(script: str, **kwargs: Any) -> list[Turn]:
    """Convenience function to parse a script.
    
    Args:
        script: Script text.
        **kwargs: Parser options.
    
    Returns:
        List of Turn objects.
    """
    parser = ScriptParser(**kwargs)
    return parser.parse(script)
