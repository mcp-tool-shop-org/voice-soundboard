"""
Compiler module - Transform requests into ControlGraphs.

All feature logic (emotion, style, SSML) lives here.
After compilation, those concepts are gone - only data remains.
"""

from voice_soundboard.compiler.compile import compile_request, compile_stream
from voice_soundboard.compiler.incremental import IncrementalCompiler, compile_incremental
from voice_soundboard.compiler.voices import VOICES, PRESETS, VoiceInfo, PresetConfig
from voice_soundboard.compiler.emotion import EMOTIONS, get_emotion, apply_emotion, list_emotions
from voice_soundboard.compiler.style import interpret_style, apply_style
from voice_soundboard.compiler.text import tokenize, normalize_text

__all__ = [
    # Main entry points
    "compile_request",
    "compile_stream",
    # Incremental compilation
    "IncrementalCompiler",
    "compile_incremental",
    # Voice data
    "VOICES",
    "PRESETS",
    "VoiceInfo",
    "PresetConfig",
    # Emotion
    "EMOTIONS",
    "get_emotion",
    "apply_emotion",
    "list_emotions",
    # Style
    "interpret_style",
    "apply_style",
    # Text
    "tokenize",
    "normalize_text",
]
