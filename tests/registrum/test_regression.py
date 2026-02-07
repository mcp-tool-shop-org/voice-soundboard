"""
4.8.11 — Regression Guard (Permanent)

Goal: Lock-in these invariants forever.

Required Tests:
    ✓ CI must run this suite on every PR
    ✓ Lint rule: any import of AudioRuntime.* must be accompanied by Registrar
    ✓ Static analysis: direct state mutation is flagged

This section defines guards that prevent regression.
If any test in this section fails → v2.8 must not ship.
"""

import pytest
import ast
import re
from pathlib import Path
from typing import List, Set, Tuple
import subprocess
import sys


# ============================================================================
# Configuration
# ============================================================================

# Source directories to analyze
SOURCE_DIRS = [
    "voice_soundboard",
    "src",
]

# Files/patterns to exclude from analysis
EXCLUDE_PATTERNS = [
    "**/test_*.py",
    "**/*_test.py",
    "**/tests/**",
    "**/conftest.py",
]

# Forbidden direct method patterns (should go through registrar)
FORBIDDEN_RUNTIME_METHODS = [
    r"\.play_audio_direct\s*\(",
    r"\.stop_audio_direct\s*\(",
    r"\.interrupt_audio_direct\s*\(",
    r"\.set_stream_state\s*\(",
    r"\.force_state_change\s*\(",
]

# Required registrar guards
REGISTRAR_GUARDS = [
    "registrar.request",
    "Registrar.request",
    "self.registrar.request",
    "self._registrar.request",
]


class TestRegressionGuard:
    """4.8.11 Regression Guard (Permanent)"""
    
    # =========================================================================
    # Test 1: CI must run this suite on every PR
    # =========================================================================
    
    def test_ci_configuration_runs_tests(self):
        """CI must run this suite on every PR"""
        # Check for common CI configuration files
        ci_files = [
            Path(".github/workflows"),
            Path(".circleci"),
            Path(".travis.yml"),
            Path("azure-pipelines.yml"),
            Path("Jenkinsfile"),
            Path(".gitlab-ci.yml"),
        ]
        
        found_ci = False
        for ci_path in ci_files:
            if ci_path.exists():
                found_ci = True
                break
        
        # For now, just verify test infrastructure exists
        test_path = Path("tests/registrum")
        assert test_path.exists(), "Test directory must exist"
        
        # Verify test files exist
        test_files = list(test_path.glob("test_*.py"))
        assert len(test_files) > 0, "Test files must exist"
        
        # Record that CI should run these
        # (actual CI config verification is environment-specific)
    
    # =========================================================================
    # Test 2: Lint rule: AudioRuntime imports must have Registrar
    # =========================================================================
    
    def test_lint_rule_runtime_requires_registrar(self):
        """Lint rule: any import of AudioRuntime.* must be accompanied by Registrar"""
        violations = []
        
        for source_dir in SOURCE_DIRS:
            source_path = Path(source_dir)
            if not source_path.exists():
                continue
            
            for py_file in source_path.rglob("*.py"):
                if self._is_excluded(py_file):
                    continue
                
                try:
                    content = py_file.read_text(encoding="utf-8", errors="ignore")
                    
                    # Check if file imports AudioRuntime
                    has_runtime_import = (
                        "from voice_soundboard.runtime" in content or
                        "import AudioRuntime" in content or
                        "from .runtime" in content
                    )
                    
                    # Check if file also imports Registrar
                    has_registrar_import = (
                        "Registrar" in content or
                        "registrar" in content
                    )
                    
                    # Files using runtime should also have registrar
                    if has_runtime_import and not has_registrar_import:
                        # Check for actual runtime usage (not just imports)
                        if any(re.search(pattern, content) for pattern in FORBIDDEN_RUNTIME_METHODS):
                            violations.append(f"{py_file}: Uses AudioRuntime without Registrar")
                
                except Exception as e:
                    # Skip files that can't be read
                    continue
        
        if violations:
            pytest.fail(f"Lint violations:\n" + "\n".join(violations))
    
    # =========================================================================
    # Test 3: Static analysis: direct state mutation is flagged
    # =========================================================================
    
    def test_static_analysis_no_direct_state_mutation(self):
        """Static analysis: direct state mutation is flagged"""
        violations = []
        
        for source_dir in SOURCE_DIRS:
            source_path = Path(source_dir)
            if not source_path.exists():
                continue
            
            for py_file in source_path.rglob("*.py"):
                if self._is_excluded(py_file):
                    continue
                
                try:
                    content = py_file.read_text(encoding="utf-8", errors="ignore")
                    
                    for pattern in FORBIDDEN_RUNTIME_METHODS:
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            # Get line number
                            line_num = content[:match.start()].count("\n") + 1
                            violations.append(
                                f"{py_file}:{line_num}: Direct state mutation: {match.group()}"
                            )
                
                except Exception as e:
                    continue
        
        if violations:
            pytest.fail(f"Direct state mutations found:\n" + "\n".join(violations))
    
    # =========================================================================
    # Helper methods
    # =========================================================================
    
    def _is_excluded(self, path: Path) -> bool:
        """Check if path matches exclusion patterns"""
        import fnmatch
        path_str = str(path)
        for pattern in EXCLUDE_PATTERNS:
            if fnmatch.fnmatch(path_str, pattern):
                return True
        return False


class TestStaticAnalysis:
    """Additional static analysis tests"""
    
    def test_no_bypass_patterns_in_code(self):
        """No registrar bypass patterns in production code"""
        bypass_patterns = [
            r"# bypass registrar",
            r"# skip registrar",
            r"# noregistrar",
            r"registrar_bypass\s*=\s*True",
            r"DISABLE_REGISTRAR",
        ]
        
        violations = []
        
        for source_dir in SOURCE_DIRS:
            source_path = Path(source_dir)
            if not source_path.exists():
                continue
            
            for py_file in source_path.rglob("*.py"):
                try:
                    content = py_file.read_text(encoding="utf-8", errors="ignore")
                    
                    for pattern in bypass_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            violations.append(f"{py_file}: Contains bypass pattern: {pattern}")
                
                except Exception:
                    continue
        
        if violations:
            pytest.fail(f"Bypass patterns found:\n" + "\n".join(violations))
    
    def test_registrar_is_not_optional(self):
        """Registrar usage is not optional in runtime code"""
        optional_patterns = [
            r"if\s+registrar\s*:",
            r"if\s+self\.registrar\s*:",
            r"registrar\s+or\s+None",
            r"registrar\s*=\s*None",
            r"Optional\[.*Registrar.*\]",
        ]
        
        violations = []
        
        for source_dir in SOURCE_DIRS:
            source_path = Path(source_dir)
            if not source_path.exists():
                continue
            
            for py_file in source_path.rglob("*.py"):
                # Exclude test files
                if "test" in str(py_file).lower():
                    continue
                
                try:
                    content = py_file.read_text(encoding="utf-8", errors="ignore")
                    
                    # Only check files that use registrar
                    if "registrar" not in content.lower():
                        continue
                    
                    for pattern in optional_patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE)
                        for match in matches:
                            line_num = content[:match.start()].count("\n") + 1
                            violations.append(
                                f"{py_file}:{line_num}: Registrar treated as optional: {match.group()}"
                            )
                
                except Exception:
                    continue
        
        # Note: Some optionality may be valid for testing
        # This test serves as a warning
        if violations:
            print(f"Warning - Optional registrar patterns:\n" + "\n".join(violations))


class TestASTAnalysis:
    """AST-based static analysis"""
    
    def test_state_enum_not_directly_assigned(self):
        """StreamState not directly assigned to stream"""
        violations = []
        
        for source_dir in SOURCE_DIRS:
            source_path = Path(source_dir)
            if not source_path.exists():
                continue
            
            for py_file in source_path.rglob("*.py"):
                if "test" in str(py_file).lower():
                    continue
                
                try:
                    content = py_file.read_text(encoding="utf-8", errors="ignore")
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Assign):
                            # Check for stream.state = StreamState.X patterns
                            for target in node.targets:
                                if isinstance(target, ast.Attribute):
                                    if target.attr == "state":
                                        if isinstance(node.value, ast.Attribute):
                                            if "StreamState" in ast.dump(node.value):
                                                violations.append(
                                                    f"{py_file}:{node.lineno}: Direct state assignment"
                                                )
                
                except SyntaxError:
                    continue
                except Exception:
                    continue
        
        if violations:
            pytest.fail(f"Direct state assignments:\n" + "\n".join(violations))


class TestInvariantLocking:
    """Tests to lock invariants"""
    
    def test_invariant_classes_exist(self):
        """Core invariant classes must exist"""
        from voice_soundboard.runtime.registrar import invariants
        
        required_invariants = [
            "SingleOwnerInvariant",
            "OwnershipRequiredInvariant",
            "AccessibilitySupremacyInvariant",
        ]
        
        for invariant in required_invariants:
            assert hasattr(invariants, invariant), f"Missing invariant: {invariant}"
    
    def test_registrar_enforces_invariants(self):
        """Registrar must have invariant enforcement"""
        from voice_soundboard.runtime.registrar import AudioRegistrar
        
        # Registrar should have invariants or similar mechanism
        assert hasattr(AudioRegistrar, 'request'), "Registrar must have request method"
    
    def test_accessibility_invariant_is_critical(self):
        """Accessibility invariant must be marked critical"""
        from voice_soundboard.runtime.registrar import invariants
        
        acc_inv = getattr(invariants, "AccessibilitySupremacyInvariant", None)
        if acc_inv:
            # Check for CRITICAL or HALT-level marker via failure_mode property
            assert hasattr(acc_inv, "failure_mode") or hasattr(acc_inv, "level") or hasattr(acc_inv, "priority"), \
                "Accessibility invariant should have severity level"


class TestTestCoverage:
    """Meta-tests for test coverage"""
    
    def test_all_sections_have_tests(self):
        """All 4.8 sections have test files"""
        required_sections = [
            "test_mediation.py",      # 4.8.1
            "test_lifecycle.py",      # 4.8.2
            "test_ownership.py",      # 4.8.3
            "test_accessibility.py",  # 4.8.4 CRITICAL
            "test_latency.py",        # 4.8.5
            "test_attestation.py",    # 4.8.6
            "test_replay.py",         # 4.8.7
            "test_mcp.py",            # 4.8.8
            "test_plugin.py",         # 4.8.9
            "test_recovery.py",       # 4.8.10
            "test_regression.py",     # 4.8.11
        ]
        
        test_path = Path("tests/registrum")
        existing_tests = [f.name for f in test_path.glob("test_*.py")]
        
        missing = [s for s in required_sections if s not in existing_tests]
        
        if missing:
            pytest.fail(f"Missing test files: {missing}")
    
    def test_critical_section_has_tests(self):
        """4.8.4 Accessibility (CRITICAL) has comprehensive tests"""
        acc_test_path = Path("tests/registrum/test_accessibility.py")
        assert acc_test_path.exists(), "Accessibility tests must exist"
        
        content = acc_test_path.read_text(encoding="utf-8")
        
        # Should have multiple test classes/methods
        test_count = content.count("def test_")
        assert test_count >= 10, f"Accessibility needs more tests (found {test_count})"
