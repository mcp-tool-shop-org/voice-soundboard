"""
Pytest configuration for v2.9 soak tests.

Registers markers for:
    - slow: tests that take a long time (8 hours)
    - soak: soak tests
    - stress: stress tests
    - memory: memory leak tests
    - latency: latency tests
    - replay: replay tests
"""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (may run for hours)")
    config.addinivalue_line("markers", "soak: marks tests as soak tests")
    config.addinivalue_line("markers", "stress: marks tests as stress tests")
    config.addinivalue_line("markers", "memory: marks tests as memory tests")
    config.addinivalue_line("markers", "latency: marks tests as latency tests")
    config.addinivalue_line("markers", "replay: marks tests as replay tests")
