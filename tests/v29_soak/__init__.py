"""
v2.9 Soak Tests — Long-Running Stability Tests

This package contains soak tests and stress tests that must pass
before v2.9 ships. These tests verify system stability under:

- Sustained load (8-hour soak)
- Concurrent access (stress tests)
- Memory pressure (leak detection)
- Latency degradation

Per v2.9 spec: "If a test flakes → v2.9 blocks"

Test Categories:
    - TestLongRunningSoak: 8-hour and 30-minute soak tests
    - TestConcurrencyStress: Race condition and deadlock tests
    - TestMemoryLeakDetection: Memory leak detection
    - TestLatencyDegradation: Latency degradation detection
    - TestReplayCorrectnessUnderLoad: Replay determinism under load

Usage:
    # Run all soak tests
    pytest tests/v29_soak/ -v
    
    # Run only quick tests (skip 8-hour soak)
    pytest tests/v29_soak/ -v --ignore-glob="*8_hour*"
    
    # Run stress tests
    pytest tests/v29_soak/ -v -m stress
    
    # Run memory tests
    pytest tests/v29_soak/ -v -m memory

FROZEN as of v2.9. See ROADMAP_v2.9.md for change process.
"""
