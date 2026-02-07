"""
v3.2 Spatial Audio Test Suite.

Test classes per Section 8 requirements:
- Golden spatial audio tests (left/right)
- Invariant regression tests
- Movement interpolation tests
- Stress tests (many sources)
- Performance benchmarks
"""

from .test_spatial_core import *
from .test_spatial_invariants import *
from .test_spatial_movement import *
from .test_spatial_stress import *
from .test_spatial_performance import *
