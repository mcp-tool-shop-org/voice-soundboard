"""
Compiler - Central compilation point.

Transforms a speech request into a ControlGraph.
All feature logic happens here. After compile_request(), 
SSML/emotion/style concepts are gone - only data remains.

Usage:
    graph = compile_request("Hello world!", voice="af_bella", emotion="happy")
    pcm = engine.synthesize(graph)
"""

from __future__ import annotations

from typing import Iterator

from voice_soundboard.graph import ControlGraph, TokenEvent, SpeakerRef
from voice_soundboard.compiler.text import tokenize, tokenize_streaming
from voice_soundboard.compiler.emotion import apply_emotion, get_emotion
from voice_soundboard.compiler.style import apply_style, suggest_voice_from_style
from voice_soundboard.compiler.voices import PRESETS, VOICES


def compile_request(
    text: str,
    *,
    voice: str | None = None,
    preset: str | None = None,
    emotion: str | None = None,
    style: str | None = None,
    speed: float | None = None,
    normalize: bool = True,
) -> ControlGraph:
    """Compile a speech request into a ControlGraph.
    
    All feature logic is resolved here:
    - Text is tokenized and normalized
    - Emotion modifies prosody
    - Style is interpreted to prosody + voice hints
    - Voice/preset is resolved to a SpeakerRef
    
    After this function returns, emotion/style/preset names are gone.
    Only numeric prosody values and voice IDs remain.
    
    Args:
        text: The text to speak
        voice: Explicit voice ID (e.g., "af_bella")
        preset: Voice preset name (e.g., "assistant", "narrator")
        emotion: Emotion name (e.g., "happy", "calm")
        style: Natural language style (e.g., "warmly and cheerfully")
        speed: Global speed multiplier (default 1.0)
        normalize: Expand numbers/abbreviations (default True)
    
    Returns:
        ControlGraph ready for engine synthesis
    
    Example:
        graph = compile_request(
            "I'm so excited!",
            emotion="excited",
            voice="af_bella",
        )
    """
    # 1. Tokenize
    tokens = tokenize(text, normalize=normalize)
    
    # 2. Apply emotion (modifies prosody)
    if emotion:
        tokens = apply_emotion(tokens, emotion)
    
    # 3. Apply style (modifies prosody, may suggest voice)
    style_voice_hint = None
    if style:
        tokens, style_result = apply_style(tokens, style)
        style_voice_hint = suggest_voice_from_style(style_result)
    
    # 4. Resolve speaker (priority: explicit > style > preset > emotion > default)
    speaker = _resolve_speaker(
        voice=voice,
        preset=preset,
        emotion=emotion,
        style_voice_hint=style_voice_hint,
    )
    
    # 5. Resolve speed (priority: explicit > preset > emotion > default)
    final_speed = _resolve_speed(
        speed=speed,
        preset=preset,
        emotion=emotion,
    )
    
    return ControlGraph(
        tokens=tokens,
        speaker=speaker,
        global_speed=final_speed,
        source_text=text,
    )


def compile_stream(
    text_iterator: Iterator[str],
    *,
    voice: str | None = None,
    preset: str | None = None,
    emotion: str | None = None,
    speed: float | None = None,
) -> Iterator[ControlGraph]:
    """Compile incrementally for streaming synthesis.
    
    Yields ControlGraphs as sentences/clauses become complete.
    Use this when text arrives in chunks (e.g., from LLM output).
    
    Args:
        text_iterator: Iterator yielding text chunks
        voice, preset, emotion, speed: Same as compile_request
    
    Yields:
        ControlGraphs for each complete segment
    """
    # Resolve speaker and speed once (they don't change mid-stream)
    speaker = _resolve_speaker(voice=voice, preset=preset, emotion=emotion)
    final_speed = _resolve_speed(speed=speed, preset=preset, emotion=emotion)
    
    for token_batch in tokenize_streaming(text_iterator):
        # Apply emotion if specified
        if emotion:
            token_batch = apply_emotion(token_batch, emotion)
        
        yield ControlGraph(
            tokens=token_batch,
            speaker=speaker,
            global_speed=final_speed,
        )


def _resolve_speaker(
    voice: str | None = None,
    preset: str | None = None,
    emotion: str | None = None,
    style_voice_hint: str | None = None,
) -> SpeakerRef:
    """Resolve speaker identity from various inputs.
    
    Priority: explicit voice > style hint > preset > emotion preference > default
    """
    # Explicit voice wins
    if voice:
        return SpeakerRef.from_voice(voice)
    
    # Style interpretation suggested a voice
    if style_voice_hint:
        return SpeakerRef.from_voice(style_voice_hint)
    
    # Preset specifies a voice
    if preset and preset in PRESETS:
        return SpeakerRef.from_voice(PRESETS[preset].voice)
    
    # Emotion has a voice preference
    if emotion:
        emo_profile = get_emotion(emotion)
        if emo_profile.voice_style_prefer:
            # Find a voice matching the emotion's style preference
            from voice_soundboard.compiler.voices import find_voice_by_style
            suggested = find_voice_by_style(style_prefer=list(emo_profile.voice_style_prefer))
            if suggested:
                return SpeakerRef.from_voice(suggested)
    
    # Default
    return SpeakerRef.from_voice("af_bella")


def _resolve_speed(
    speed: float | None = None,
    preset: str | None = None,
    emotion: str | None = None,
) -> float:
    """Resolve global speed from various inputs.
    
    Priority: explicit > preset > emotion > default
    """
    if speed is not None:
        return speed
    
    if preset and preset in PRESETS:
        return PRESETS[preset].speed
    
    if emotion:
        emo_profile = get_emotion(emotion)
        return emo_profile.speed
    
    return 1.0
