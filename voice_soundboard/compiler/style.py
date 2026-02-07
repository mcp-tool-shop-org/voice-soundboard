"""
Style Interpreter - Natural language style hints to parameters.

Interprets phrases like "warmly and cheerfully" into prosody modifiers.
This is a compile-time transformation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from voice_soundboard.graph import TokenEvent
from voice_soundboard.compiler.voices import find_voice_by_style


@dataclass
class StyleResult:
    """Interpreted style parameters."""
    speed: float = 1.0
    pitch: float = 1.0
    energy: float = 1.0
    voice_styles: list[str] | None = None
    gender: str | None = None
    accent: str | None = None


# Style keywords → parameters
STYLE_KEYWORDS: dict[str, dict] = {
    # Speed modifiers
    "quickly": {"speed": 1.2},
    "fast": {"speed": 1.2},
    "rapidly": {"speed": 1.3},
    "slowly": {"speed": 0.8},
    "slow": {"speed": 0.85},
    "carefully": {"speed": 0.9},
    "deliberately": {"speed": 0.85},
    "urgently": {"speed": 1.25},
    
    # Energy/tone
    "excitedly": {"speed": 1.15, "energy": 1.2, "styles": ["bright", "energetic"]},
    "enthusiastically": {"speed": 1.1, "energy": 1.15, "styles": ["bright", "friendly"]},
    "calmly": {"speed": 0.9, "energy": 0.85, "styles": ["calm", "soft"]},
    "gently": {"speed": 0.9, "energy": 0.8, "styles": ["soft", "gentle", "warm"]},
    "warmly": {"speed": 0.95, "energy": 1.0, "styles": ["warm", "friendly", "caring"]},
    "coldly": {"speed": 1.0, "energy": 0.9, "styles": ["neutral", "clear"]},
    "seriously": {"speed": 0.95, "energy": 1.0, "styles": ["authoritative", "deep"]},
    "playfully": {"speed": 1.05, "energy": 1.1, "styles": ["playful", "bright", "youthful"]},
    "mysteriously": {"speed": 0.85, "energy": 0.85, "styles": ["soft", "deep"]},
    "dramatically": {"speed": 0.9, "energy": 1.2, "styles": ["powerful", "authoritative"]},
    "cheerfully": {"speed": 1.1, "energy": 1.15, "styles": ["bright", "friendly", "jolly"]},
    "sadly": {"speed": 0.85, "energy": 0.75, "styles": ["soft", "gentle"]},
    "angrily": {"speed": 1.1, "energy": 1.3, "styles": ["powerful", "confident"]},
    "nervously": {"speed": 1.15, "energy": 0.9, "styles": ["soft", "youthful"]},
    "confidently": {"speed": 1.0, "energy": 1.1, "styles": ["confident", "professional"]},
    "softly": {"speed": 0.9, "energy": 0.7, "styles": ["soft", "gentle"]},
    "loudly": {"speed": 1.05, "energy": 1.3, "styles": ["powerful", "bright"]},
    "quietly": {"speed": 0.9, "energy": 0.6, "styles": ["soft", "gentle"]},
    
    # Character descriptors
    "narratively": {"speed": 0.95, "styles": ["storytelling", "authoritative"]},
    "professionally": {"speed": 1.0, "styles": ["professional", "clear", "neutral"]},
    "casually": {"speed": 1.05, "styles": ["friendly", "playful"]},
    "formally": {"speed": 0.95, "styles": ["professional", "sophisticated"]},
    
    # Gender preferences
    "masculine": {"gender": "male"},
    "feminine": {"gender": "female"},
    
    # Accent preferences
    "british": {"accent": "british"},
    "american": {"accent": "american"},
}

# Multi-word patterns
PHRASE_PATTERNS: list[tuple[re.Pattern, dict]] = [
    (re.compile(r"like a narrator", re.I), {"styles": ["storytelling", "authoritative"]}),
    (re.compile(r"like an announcer", re.I), {"speed": 1.1, "styles": ["powerful", "bright"]}),
    (re.compile(r"like a storyteller", re.I), {"speed": 0.9, "styles": ["storytelling", "warm"]}),
    (re.compile(r"like whispering", re.I), {"speed": 0.85, "energy": 0.5, "styles": ["soft"]}),
    (re.compile(r"in a male voice", re.I), {"gender": "male"}),
    (re.compile(r"in a female voice", re.I), {"gender": "female"}),
    (re.compile(r"with a british accent", re.I), {"accent": "british"}),
    (re.compile(r"with an american accent", re.I), {"accent": "american"}),
]


def interpret_style(style: str) -> StyleResult:
    """Interpret a natural language style description.
    
    Args:
        style: Natural language style hint (e.g., "warmly and cheerfully")
    
    Returns:
        StyleResult with parsed parameters
    """
    result = StyleResult()
    style_lower = style.lower()
    
    # Check phrase patterns first
    for pattern, params in PHRASE_PATTERNS:
        if pattern.search(style_lower):
            _apply_params(result, params)
    
    # Check individual keywords
    for keyword, params in STYLE_KEYWORDS.items():
        if keyword in style_lower:
            _apply_params(result, params)
    
    return result


def _apply_params(result: StyleResult, params: dict) -> None:
    """Apply parameters to result, combining multiplicatively."""
    if "speed" in params:
        result.speed *= params["speed"]
    if "pitch" in params:
        result.pitch *= params["pitch"]
    if "energy" in params:
        result.energy *= params["energy"]
    if "styles" in params:
        if result.voice_styles is None:
            result.voice_styles = []
        result.voice_styles.extend(params["styles"])
    if "gender" in params:
        result.gender = params["gender"]
    if "accent" in params:
        result.accent = params["accent"]


def apply_style(tokens: list[TokenEvent], style: str) -> tuple[list[TokenEvent], StyleResult]:
    """Apply style interpretation to tokens.
    
    Returns both modified tokens and the interpreted style result
    (for voice selection).
    """
    interpretation = interpret_style(style)
    
    modified = []
    for token in tokens:
        modified.append(TokenEvent(
            text=token.text,
            phonemes=token.phonemes,
            pitch_scale=token.pitch_scale * interpretation.pitch,
            energy_scale=token.energy_scale * interpretation.energy,
            duration_scale=token.duration_scale / interpretation.speed,
            paralinguistic=token.paralinguistic,
            emphasis=token.emphasis,
            pause_after=token.pause_after,
        ))
    
    return modified, interpretation


def suggest_voice_from_style(style_result: StyleResult) -> str | None:
    """Suggest a voice based on interpreted style preferences."""
    return find_voice_by_style(
        style_prefer=style_result.voice_styles,
        gender=style_result.gender,
        accent=style_result.accent,
    )
