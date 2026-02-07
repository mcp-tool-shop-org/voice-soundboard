"""
Captions & Transcripts - Hearing accessibility features.

This module provides caption generation, live captions, and
transcript export for hearing-impaired users.

Components:
    CaptionGenerator   - Generate captions from synthesis
    CaptionFormat      - Supported caption formats
    LiveCaptions       - Real-time caption display
    TranscriptExporter - Export transcripts in various formats
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Iterator, Optional


class CaptionFormat(Enum):
    """Supported caption file formats."""
    WEBVTT = auto()  # Web Video Text Tracks
    SRT = auto()     # SubRip
    TTML = auto()    # Timed Text Markup Language
    SCC = auto()     # Scenarist Closed Captions
    SSA = auto()     # SubStation Alpha


@dataclass
class Caption:
    """A single caption entry.
    
    Attributes:
        text: Caption text (may include formatting)
        start_time: Start time in seconds
        end_time: End time in seconds
        speaker: Optional speaker label
        style: Optional style/positioning info
    """
    text: str
    start_time: float
    end_time: float
    speaker: Optional[str] = None
    style: Optional[dict[str, Any]] = None


@dataclass
class CaptionConfig:
    """Configuration for caption generation."""
    format: CaptionFormat = CaptionFormat.WEBVTT
    max_line_length: int = 42
    max_lines: int = 2
    min_duration_ms: int = 1000
    max_duration_ms: int = 7000
    position: str = "bottom"  # bottom, top
    alignment: str = "center"  # left, center, right
    include_speaker_labels: bool = True
    speaker_format: str = "{speaker}: "


class CaptionGenerator:
    """Generate captions from synthesized speech.
    
    Creates synchronized captions from Voice Soundboard output,
    automatically handling timing and formatting.
    
    Example:
        generator = CaptionGenerator(format=CaptionFormat.WEBVTT)
        
        result = engine.speak("Hello, world!")
        captions = generator.generate(result)
        
        with open("captions.vtt", "w") as f:
            f.write(captions)
    """
    
    def __init__(self, config: Optional[CaptionConfig] = None) -> None:
        """Initialize caption generator.
        
        Args:
            config: Caption configuration
        """
        self.config = config or CaptionConfig()
    
    def generate(self, result: Any) -> str:
        """Generate captions from a SpeechResult.
        
        Args:
            result: SpeechResult from synthesis
            
        Returns:
            Caption file content as string
        """
        captions = self._extract_captions(result)
        return self._format_captions(captions)
    
    def generate_from_text(
        self,
        text: str,
        duration_ms: float,
        speaker: Optional[str] = None,
    ) -> str:
        """Generate captions from text and timing.
        
        Args:
            text: Text content
            duration_ms: Total duration
            speaker: Optional speaker label
            
        Returns:
            Caption file content
        """
        captions = self._split_into_captions(text, duration_ms, speaker)
        return self._format_captions(captions)
    
    def _extract_captions(self, result: Any) -> list[Caption]:
        """Extract caption data from SpeechResult."""
        # Use word timings if available
        captions = []
        
        # Placeholder: would use result.word_timings or similar
        if hasattr(result, 'text'):
            captions.append(Caption(
                text=result.text,
                start_time=0.0,
                end_time=getattr(result, 'duration_ms', 1000) / 1000,
            ))
        
        return captions
    
    def _split_into_captions(
        self,
        text: str,
        duration_ms: float,
        speaker: Optional[str],
    ) -> list[Caption]:
        """Split text into properly timed captions."""
        captions = []
        words = text.split()
        
        if not words:
            return captions
        
        duration_sec = duration_ms / 1000
        words_per_caption = max(1, len(words) // max(1, int(duration_sec / 3)))
        
        current_words = []
        for i, word in enumerate(words):
            current_words.append(word)
            
            if len(current_words) >= words_per_caption or i == len(words) - 1:
                caption_text = " ".join(current_words)
                start = (i - len(current_words) + 1) / len(words) * duration_sec
                end = (i + 1) / len(words) * duration_sec
                
                captions.append(Caption(
                    text=caption_text,
                    start_time=start,
                    end_time=end,
                    speaker=speaker,
                ))
                current_words = []
        
        return captions
    
    def _format_captions(self, captions: list[Caption]) -> str:
        """Format captions in the configured format."""
        cfg = self.config
        
        if cfg.format == CaptionFormat.WEBVTT:
            return self._to_webvtt(captions)
        elif cfg.format == CaptionFormat.SRT:
            return self._to_srt(captions)
        elif cfg.format == CaptionFormat.TTML:
            return self._to_ttml(captions)
        else:
            return self._to_webvtt(captions)  # Default
    
    def _to_webvtt(self, captions: list[Caption]) -> str:
        """Format as WebVTT."""
        lines = ["WEBVTT", ""]
        
        for i, cap in enumerate(captions, 1):
            start = self._format_vtt_time(cap.start_time)
            end = self._format_vtt_time(cap.end_time)
            
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            
            text = cap.text
            if cap.speaker and self.config.include_speaker_labels:
                text = f"<v {cap.speaker}>{text}"
            
            lines.append(text)
            lines.append("")
        
        return "\n".join(lines)
    
    def _to_srt(self, captions: list[Caption]) -> str:
        """Format as SRT."""
        lines = []
        
        for i, cap in enumerate(captions, 1):
            start = self._format_srt_time(cap.start_time)
            end = self._format_srt_time(cap.end_time)
            
            lines.append(str(i))
            lines.append(f"{start} --> {end}")
            
            text = cap.text
            if cap.speaker and self.config.include_speaker_labels:
                text = f"{cap.speaker}: {text}"
            
            lines.append(text)
            lines.append("")
        
        return "\n".join(lines)
    
    def _to_ttml(self, captions: list[Caption]) -> str:
        """Format as TTML."""
        body_lines = []
        
        for cap in captions:
            start = f"{cap.start_time:.3f}s"
            end = f"{cap.end_time:.3f}s"
            text = cap.text.replace("&", "&amp;").replace("<", "&lt;")
            body_lines.append(f'    <p begin="{start}" end="{end}">{text}</p>')
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml">
  <body>
    <div>
{chr(10).join(body_lines)}
    </div>
  </body>
</tt>"""
    
    def _format_vtt_time(self, seconds: float) -> str:
        """Format time for WebVTT (HH:MM:SS.mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format time for SRT (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class LiveCaptions:
    """Real-time caption display during synthesis.
    
    Provides live captions synchronized with speech output,
    supporting various display modes.
    
    Example:
        captions = LiveCaptions(display="overlay")
        
        async for chunk in engine.stream(text):
            caption = captions.update(chunk)
            # Caption updates in real-time
    """
    
    def __init__(
        self,
        display: str = "overlay",
        font_size: str = "medium",
        background_opacity: float = 0.8,
        speaker_labels: bool = True,
    ) -> None:
        """Initialize live captions.
        
        Args:
            display: Display mode (overlay, sidebar, external)
            font_size: Font size (small, medium, large)
            background_opacity: Background opacity (0.0-1.0)
            speaker_labels: Whether to show speaker labels
        """
        self.display = display
        self.font_size = font_size
        self.background_opacity = background_opacity
        self.speaker_labels = speaker_labels
        self._current_text = ""
        self._current_speaker: Optional[str] = None
    
    def update(self, chunk: Any) -> str:
        """Update captions with new chunk.
        
        Args:
            chunk: Audio chunk with timing info
            
        Returns:
            Current caption text
        """
        if hasattr(chunk, 'text'):
            self._current_text = chunk.text
        return self._current_text
    
    def set_speaker(self, speaker: str) -> None:
        """Set current speaker for labeling."""
        self._current_speaker = speaker
    
    def clear(self) -> None:
        """Clear current caption."""
        self._current_text = ""
    
    def get_current(self) -> str:
        """Get current caption text."""
        if self._current_speaker and self.speaker_labels:
            return f"{self._current_speaker}: {self._current_text}"
        return self._current_text


class TranscriptExporter:
    """Export conversation transcripts in various formats.
    
    Creates accessible transcripts from conversations,
    suitable for documentation and accessibility.
    
    Example:
        exporter = TranscriptExporter(format="markdown")
        transcript = exporter.export(conversation)
        
        with open("transcript.md", "w") as f:
            f.write(transcript)
    """
    
    def __init__(
        self,
        include_timestamps: bool = True,
        include_speakers: bool = True,
        format: str = "markdown",
    ) -> None:
        """Initialize transcript exporter.
        
        Args:
            include_timestamps: Include timestamps
            include_speakers: Include speaker labels
            format: Output format (markdown, html, txt, docx)
        """
        self.include_timestamps = include_timestamps
        self.include_speakers = include_speakers
        self.format = format
    
    def export(self, conversation: Any) -> str:
        """Export a conversation to transcript.
        
        Args:
            conversation: Conversation object to export
            
        Returns:
            Formatted transcript string
        """
        if self.format == "markdown":
            return self._to_markdown(conversation)
        elif self.format == "html":
            return self._to_html(conversation)
        elif self.format == "txt":
            return self._to_text(conversation)
        else:
            return self._to_markdown(conversation)
    
    def _to_markdown(self, conversation: Any) -> str:
        """Export as Markdown."""
        lines = ["# Transcript", ""]
        
        # Placeholder: would iterate conversation turns
        if hasattr(conversation, 'turns'):
            for turn in conversation.turns:
                timestamp = ""
                if self.include_timestamps and hasattr(turn, 'timestamp'):
                    timestamp = f"**[{self._format_time(turn.timestamp)}]** "
                
                speaker = ""
                if self.include_speakers and hasattr(turn, 'speaker'):
                    speaker = f"**{turn.speaker}:** "
                
                text = getattr(turn, 'text', '')
                lines.append(f"{timestamp}{speaker}{text}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _to_html(self, conversation: Any) -> str:
        """Export as HTML."""
        lines = [
            "<!DOCTYPE html>",
            "<html><head><title>Transcript</title></head>",
            "<body>",
            "<h1>Transcript</h1>",
        ]
        
        if hasattr(conversation, 'turns'):
            lines.append("<dl>")
            for turn in conversation.turns:
                speaker = getattr(turn, 'speaker', 'Unknown')
                text = getattr(turn, 'text', '')
                lines.append(f"  <dt>{speaker}</dt>")
                lines.append(f"  <dd>{text}</dd>")
            lines.append("</dl>")
        
        lines.extend(["</body>", "</html>"])
        return "\n".join(lines)
    
    def _to_text(self, conversation: Any) -> str:
        """Export as plain text."""
        lines = ["TRANSCRIPT", "=" * 40, ""]
        
        if hasattr(conversation, 'turns'):
            for turn in conversation.turns:
                speaker = getattr(turn, 'speaker', '')
                text = getattr(turn, 'text', '')
                if self.include_speakers and speaker:
                    lines.append(f"{speaker}: {text}")
                else:
                    lines.append(text)
        
        return "\n".join(lines)
    
    def _format_time(self, seconds: float) -> str:
        """Format timestamp for display."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
