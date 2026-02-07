"""
Streaming Module - Incremental text streaming with speculative synthesis.

v2.1 Feature (P0): True word-by-word streaming with rollback support.

Usage:
    from voice_soundboard.streaming import IncrementalSynthesizer
    
    synth = IncrementalSynthesizer(backend)
    
    for word in llm_stream():
        for chunk in synth.feed(word):
            play(chunk)
    
    for chunk in synth.finalize():
        play(chunk)
"""

from voice_soundboard.streaming.synthesizer import (
    IncrementalSynthesizer,
    StreamBuffer,
    SpeculativeGraph,
    CorrectionDetector,
)

__all__ = [
    "IncrementalSynthesizer",
    "StreamBuffer",
    "SpeculativeGraph",
    "CorrectionDetector",
]
