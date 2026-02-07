"""
Conversation container and synthesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Sequence

import numpy as np

from voice_soundboard.conversation.speaker import Speaker, SpeakerStyle
from voice_soundboard.conversation.turn import Turn, TurnType, Timeline


@dataclass
class ConversationResult:
    """Result of conversation synthesis.
    
    Attributes:
        audio: Combined audio for entire conversation.
        sample_rate: Audio sample rate.
        timeline: Timeline with timing for each turn.
        metadata: Additional synthesis metadata.
    """
    
    audio: np.ndarray
    sample_rate: int
    timeline: Timeline
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> float:
        """Audio duration in seconds."""
        return len(self.audio) / self.sample_rate
    
    @property
    def duration_ms(self) -> float:
        """Audio duration in milliseconds."""
        return self.duration_seconds * 1000


class Conversation:
    """Multi-speaker conversation container.
    
    Manages speakers, turns, and conversation synthesis.
    
    Example:
        conv = Conversation(
            speakers={
                "alice": Speaker(voice="af_bella", style="friendly"),
                "bob": Speaker(voice="am_michael", style="professional"),
            }
        )
        
        # Add turns
        conv.add("alice", "Hello Bob!")
        conv.add("bob", "Hi Alice, how are you?")
        conv.add("alice", "I'm great, thanks!")
        
        # Or from script
        result = conv.synthesize(engine)
        
        # Play result
        play(result.audio)
    """
    
    def __init__(
        self,
        speakers: dict[str, Speaker] | None = None,
        gap_ms: float = 100,
    ):
        """Initialize conversation.
        
        Args:
            speakers: Dictionary mapping speaker IDs to Speaker configs.
            gap_ms: Default gap between turns in milliseconds.
        """
        self._speakers: dict[str, Speaker] = speakers or {}
        self._turns: list[Turn] = []
        self._gap_ms = gap_ms
    
    @property
    def speakers(self) -> dict[str, Speaker]:
        """Get speakers dictionary."""
        return self._speakers.copy()
    
    @property
    def turns(self) -> list[Turn]:
        """Get list of turns."""
        return self._turns.copy()
    
    def add_speaker(
        self,
        speaker_id: str,
        speaker: Speaker,
    ) -> "Conversation":
        """Add a speaker to the conversation.
        
        Args:
            speaker_id: Unique identifier for speaker.
            speaker: Speaker configuration.
        
        Returns:
            Self for chaining.
        """
        self._speakers[speaker_id] = speaker
        return self
    
    def add(
        self,
        speaker_id: str,
        text: str,
        **metadata: Any,
    ) -> "Conversation":
        """Add a speech turn to the conversation.
        
        Args:
            speaker_id: Speaker identifier.
            text: Text to speak.
            **metadata: Additional metadata.
        
        Returns:
            Self for chaining.
        
        Raises:
            ValueError: If speaker not registered.
        """
        if speaker_id not in self._speakers:
            raise ValueError(f"Unknown speaker: {speaker_id}")
        
        self._turns.append(Turn.speech(speaker_id, text, **metadata))
        return self
    
    def add_pause(self, duration_ms: float) -> "Conversation":
        """Add a pause to the conversation.
        
        Args:
            duration_ms: Pause duration in milliseconds.
        
        Returns:
            Self for chaining.
        """
        self._turns.append(Turn.pause(duration_ms))
        return self
    
    def add_action(
        self,
        speaker_id: str,
        action: str,
        **metadata: Any,
    ) -> "Conversation":
        """Add an action turn to the conversation.
        
        Args:
            speaker_id: Speaker identifier.
            action: Action description.
            **metadata: Additional metadata.
        
        Returns:
            Self for chaining.
        """
        if speaker_id not in self._speakers:
            raise ValueError(f"Unknown speaker: {speaker_id}")
        
        self._turns.append(Turn.action(speaker_id, action, **metadata))
        return self
    
    def from_script(
        self,
        script: Sequence[tuple[str, str]],
    ) -> "Conversation":
        """Load turns from a script.
        
        Args:
            script: Sequence of (speaker_id, text) tuples.
        
        Returns:
            Self for chaining.
        """
        for speaker_id, text in script:
            self.add(speaker_id, text)
        return self
    
    def clear(self) -> "Conversation":
        """Clear all turns.
        
        Returns:
            Self for chaining.
        """
        self._turns.clear()
        return self
    
    def synthesize(
        self,
        engine: Any,
        normalize: bool = True,
    ) -> ConversationResult:
        """Synthesize the conversation to audio.
        
        Args:
            engine: VoiceEngine to use for synthesis.
            normalize: Normalize audio levels.
        
        Returns:
            ConversationResult with combined audio and timeline.
        """
        if not self._turns:
            # Return empty result
            return ConversationResult(
                audio=np.array([], dtype=np.float32),
                sample_rate=24000,
                timeline=Timeline(),
            )
        
        # Synthesize each turn
        audio_segments: list[np.ndarray] = []
        durations_ms: list[float] = []
        sample_rate = None
        
        for turn in self._turns:
            if turn.is_pause:
                # Generate silence for pause
                pause_samples = int(turn.duration_ms * 24000 / 1000)
                audio_segments.append(np.zeros(pause_samples, dtype=np.float32))
                durations_ms.append(turn.duration_ms)
            
            elif turn.is_speech:
                speaker = self._speakers[turn.speaker_id]
                params = speaker.to_compile_params()
                
                # Synthesize
                result = engine.speak(
                    turn.text,
                    **params,
                    return_array=True,
                )
                
                audio = result.audio if hasattr(result, "audio") else result
                if sample_rate is None:
                    sample_rate = getattr(result, "sample_rate", 24000)
                
                audio_segments.append(audio)
                durations_ms.append(len(audio) / sample_rate * 1000)
                
                # Add gap between turns
                gap_samples = int(self._gap_ms * sample_rate / 1000)
                audio_segments.append(np.zeros(gap_samples, dtype=np.float32))
            
            elif turn.is_action:
                # Actions could trigger sound effects
                # For now, add a short pause
                pause_samples = int(100 * 24000 / 1000)
                audio_segments.append(np.zeros(pause_samples, dtype=np.float32))
                durations_ms.append(100)
        
        sample_rate = sample_rate or 24000
        
        # Combine audio
        combined = np.concatenate(audio_segments)
        
        # Normalize if requested
        if normalize:
            peak = np.max(np.abs(combined))
            if peak > 0:
                combined = combined * (0.9 / peak)
        
        # Build timeline
        timeline = Timeline(turns=self._turns, gap_ms=self._gap_ms)
        timeline = timeline.compute_timing(durations_ms)
        
        return ConversationResult(
            audio=combined,
            sample_rate=sample_rate,
            timeline=timeline,
        )
    
    def synthesize_stream(
        self,
        engine: Any,
    ) -> Iterator[tuple[Turn, np.ndarray]]:
        """Stream conversation synthesis turn by turn.
        
        Args:
            engine: VoiceEngine for synthesis.
        
        Yields:
            Tuples of (Turn, audio_array).
        """
        for turn in self._turns:
            if turn.is_pause:
                pause_samples = int(turn.duration_ms * 24000 / 1000)
                yield turn, np.zeros(pause_samples, dtype=np.float32)
            
            elif turn.is_speech:
                speaker = self._speakers[turn.speaker_id]
                params = speaker.to_compile_params()
                
                result = engine.speak(
                    turn.text,
                    **params,
                    return_array=True,
                )
                
                audio = result.audio if hasattr(result, "audio") else result
                yield turn, audio
            
            elif turn.is_action:
                # Short pause for actions
                yield turn, np.zeros(2400, dtype=np.float32)  # 100ms at 24kHz
