"""
Incremental Compiler - Emit graph segments as text arrives.

This wraps the existing compiler for streaming input scenarios:
- LLM token-by-token output
- User typing
- WebSocket text streams

KEY CONSTRAINT:
    The compiler may only emit graph segments that will NOT change
    when more text arrives. Each emitted graph is FINAL.

COMMIT BOUNDARIES:
    A segment is committable when:
    - It ends in sentence punctuation (. ! ?)
    - It ends in clause punctuation (, ; :)
    - It exceeds max_buffer_tokens
    - It starts with a complete paralinguistic tag ([laugh])
    - finalize() is called

Usage:
    compiler = IncrementalCompiler()
    
    for text_chunk in llm_stream:
        for graph in compiler.feed(text_chunk):
            for frame in engine.stream(graph):
                output(frame)
    
    # Flush remainder
    for graph in compiler.finalize():
        output(engine.synthesize(graph))
"""

from __future__ import annotations

import re
from typing import Callable

from voice_soundboard.graph import ControlGraph, TokenEvent, SpeakerRef, Paralinguistic, ParalinguisticEvent
from voice_soundboard.compiler.compile import compile_request


# Patterns for commit boundaries
# Match punctuation followed by space or end of string
SENTENCE_END = re.compile(r'[.!?](?:\s|$)')
CLAUSE_END = re.compile(r'[,;:](?:\s|$)')

# Paralinguistic tags: [laugh], [sigh], etc.
PARA_TAG = re.compile(r'\[(\w+)\]')
PARA_TAG_FULL = re.compile(r'^\s*\[(\w+)\]\s*')


class IncrementalCompiler:
    """Wraps compile_request for incremental text input.
    
    Buffers text and emits complete ControlGraphs at commit boundaries.
    Each emitted graph is immutable - no future mutation.
    
    Paralinguistic events ([laugh], [sigh]) are detected and converted
    to ParalinguisticEvent timeline objects.
    """
    
    def __init__(
        self,
        voice: str | None = None,
        preset: str | None = None,
        emotion: str | None = None,
        speed: float | None = None,
        max_buffer_chars: int = 200,
        compile_fn: Callable[..., ControlGraph] | None = None,
    ):
        """Initialize incremental compiler.
        
        Args:
            voice: Voice ID for all segments
            preset: Preset name for all segments
            emotion: Emotion for all segments
            speed: Speed multiplier for all segments
            max_buffer_chars: Force commit after this many characters
            compile_fn: Override compile function (for testing)
        """
        self._voice = voice
        self._preset = preset
        self._emotion = emotion
        self._speed = speed
        self._max_buffer_chars = max_buffer_chars
        self._compile_fn = compile_fn or compile_request
        
        self._buffer = ""
        self._timeline_offset = 0.0  # Cumulative time for event positioning
    
    def feed(self, text_chunk: str) -> list[ControlGraph]:
        """Feed a text chunk and emit any complete graphs.
        
        Args:
            text_chunk: New text to process
        
        Returns:
            List of complete ControlGraphs (may be empty)
        """
        self._buffer += text_chunk
        return self._flush_ready()
    
    def finalize(self) -> list[ControlGraph]:
        """Flush all remaining buffer content.
        
        Call this when input stream ends.
        
        Returns:
            List of final ControlGraphs
        """
        return self._flush_all()
    
    def reset(self):
        """Clear buffer state for reuse."""
        self._buffer = ""
        self._timeline_offset = 0.0
    
    def _flush_ready(self) -> list[ControlGraph]:
        """Emit graphs for segments at commit boundaries."""
        graphs = []
        
        while True:
            boundary = self._find_commit_boundary()
            if boundary is None:
                break
            
            segment = self._buffer[:boundary]
            self._buffer = self._buffer[boundary:].lstrip()
            
            if segment.strip():
                graph = self._compile_segment(segment)
                if graph:
                    graphs.append(graph)
        
        return graphs
    
    def _flush_all(self) -> list[ControlGraph]:
        """Emit graphs for all remaining content."""
        graphs = []
        
        if self._buffer.strip():
            graph = self._compile_segment(self._buffer.strip())
            if graph:
                graphs.append(graph)
        
        self._buffer = ""
        return graphs
    
    def _find_commit_boundary(self) -> int | None:
        """Find the next commit boundary in the buffer.
        
        Returns character index, or None if no boundary found.
        """
        # Check for paralinguistic tag at start
        tag_match = PARA_TAG_FULL.match(self._buffer)
        if tag_match:
            return tag_match.end()
        
        # Check sentence boundaries
        for match in SENTENCE_END.finditer(self._buffer):
            return match.end()
        
        # Check clause boundaries (only if buffer is getting long)
        if len(self._buffer) > self._max_buffer_chars // 2:
            for match in CLAUSE_END.finditer(self._buffer):
                return match.end()
        
        # Force commit if buffer too long
        if len(self._buffer) > self._max_buffer_chars:
            # Find last space to avoid splitting words
            space_idx = self._buffer.rfind(' ', 0, self._max_buffer_chars)
            if space_idx > 0:
                return space_idx + 1
            return self._max_buffer_chars
        
        return None
    
    def _compile_segment(self, text: str) -> ControlGraph | None:
        """Compile a text segment, extracting paralinguistic events."""
        text = text.strip()
        if not text:
            return None
        
        # Extract paralinguistic events
        events, clean_text = self._extract_events(text)
        
        # Handle pure event segments (no speech)
        if not clean_text.strip():
            if events:
                # Return a minimal graph with just the event
                return ControlGraph(
                    tokens=[TokenEvent(text="", pause_after=events[0].duration)],
                    speaker=self._resolve_speaker(),
                    events=events,
                    source_text=text,
                )
            return None
        
        # Compile the clean text
        graph = self._compile_fn(
            clean_text,
            voice=self._voice,
            preset=self._preset,
            emotion=self._emotion,
            speed=self._speed,
        )
        
        # Attach events to the graph
        if events:
            # Use object.__setattr__ since ControlGraph is a dataclass
            graph = ControlGraph(
                tokens=graph.tokens,
                speaker=graph.speaker,
                events=events,
                global_speed=graph.global_speed,
                global_pitch=graph.global_pitch,
                sample_rate=graph.sample_rate,
                source_text=text,
            )
        
        return graph
    
    def _extract_events(self, text: str) -> tuple[list[ParalinguisticEvent], str]:
        """Extract paralinguistic tags from text.
        
        Args:
            text: Input text potentially containing [laugh], [sigh], etc.
        
        Returns:
            (list of events, cleaned text without tags)
        """
        events = []
        clean_text = text
        event_time = self._timeline_offset
        
        for match in PARA_TAG.finditer(text):
            tag = match.group(1).lower()
            
            # Map tag to Paralinguistic enum
            try:
                para_type = Paralinguistic(tag)
            except ValueError:
                continue  # Unknown tag, leave as text
            
            events.append(ParalinguisticEvent(
                type=para_type,
                start_time=event_time,
                duration=0.2,  # Default 200ms
                intensity=1.0,
            ))
            event_time += 0.2
            
            # Remove tag from text
            clean_text = clean_text.replace(match.group(0), '', 1)
        
        return events, clean_text.strip()
    
    def _resolve_speaker(self) -> SpeakerRef:
        """Resolve speaker for event-only graphs."""
        if self._voice:
            return SpeakerRef.from_voice(self._voice)
        return SpeakerRef.from_voice("af_bella")


def compile_incremental(
    text_chunks,
    **kwargs,
) -> list[ControlGraph]:
    """Convenience function for incremental compilation.
    
    Args:
        text_chunks: Iterable of text chunks
        **kwargs: Passed to IncrementalCompiler
    
    Returns:
        All compiled graphs
    """
    compiler = IncrementalCompiler(**kwargs)
    graphs = []
    
    for chunk in text_chunks:
        graphs.extend(compiler.feed(chunk))
    
    graphs.extend(compiler.finalize())
    return graphs
