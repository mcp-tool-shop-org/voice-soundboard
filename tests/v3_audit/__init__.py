"""
v3 Compatibility Audit Test Suite

This package contains tests that prove v2.9 is ready for v3.

The question this suite answers:
    "If we add mixing, DSP, spatial audio, and cloning tomorrow — 
     will anything break structurally?"

Audit Coverage:
    1. Engine boundary audit (pure PCM + metadata)
    2. Graph extensibility audit (DSP annotations safe)
    3. Scene/multi-speaker readiness confirmed
    4. Registrar supports multi-track futures
    5. No assumptions of "single voice, single stream"

If any audit fails → v2.9 is not ready for v3.
"""

__version__ = "2.9.0"
