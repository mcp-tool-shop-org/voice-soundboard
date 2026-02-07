"""
Registrum Integration Tests — Authoritative Spec for v2.8

This test suite is a release gate. If any test fails, v2.8 cannot ship.

Test Sections (4.8):
    4.8.1  Registrar Mediation Tests (Hard Gate)
    4.8.2  Lifecycle Ordering Tests
    4.8.3  Ownership & Authority Tests
    4.8.4  Accessibility Supremacy Tests (Critical)
    4.8.5  Hot-Path Latency Tests
    4.8.6  Attestation Completeness Tests
    4.8.7  Replay Determinism Tests
    4.8.8  MCP ↔ Registrar Integration Tests
    4.8.9  Plugin Containment Tests
    4.8.10 Failure & Recovery Tests
    4.8.11 Regression Guard (Permanent)

Acceptance Rule (Non-Negotiable):
    If any state-changing behavior cannot be explained by a registrar
    attestation, v2.8 is not complete.
"""
