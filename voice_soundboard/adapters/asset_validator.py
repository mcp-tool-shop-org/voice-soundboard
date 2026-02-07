"""
Asset Validator - Validate audio event assets.

v2.1 Feature (P3): CLI tool to validate audio assets.

Validates:
- File format (WAV only)
- Channel count (mono required)
- Bit depth (16-bit recommended)
- Sample rate (24kHz or 22kHz for backend compatibility)
- Duration (reasonable length for events)

Usage:
    voice-soundboard validate-assets ./my-assets/
    # ✅ laugh/soft.wav: mono, 16-bit, 24000Hz, 0.23s
    # ✅ laugh/medium.wav: mono, 16-bit, 24000Hz, 0.31s  
    # ❌ sigh/long.wav: stereo (must be mono)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


# Supported sample rates
VALID_SAMPLE_RATES = {22050, 24000, 44100, 48000}

# Recommended sample rates for event assets
RECOMMENDED_SAMPLE_RATES = {22050, 24000}

# Max duration for event assets (seconds)
MAX_EVENT_DURATION = 5.0


@dataclass
class ValidationResult:
    """Result of validating a single asset file."""
    path: Path
    relative_path: str
    valid: bool
    issues: list[str] = field(default_factory=list)
    fixed: bool = False
    
    # Audio properties (if readable)
    channels: int = 0
    sample_rate: int = 0
    bit_depth: int = 0
    duration: float = 0.0
    format_type: str = ""


def validate_asset(
    path: Path,
    *,
    expected_sample_rate: int = 24000,
    fix_issues: bool = False,
) -> ValidationResult:
    """Validate a single audio asset file.
    
    Args:
        path: Path to audio file
        expected_sample_rate: Expected sample rate
        fix_issues: Attempt to fix issues
    
    Returns:
        ValidationResult with issues list
    """
    result = ValidationResult(
        path=path,
        relative_path=str(path),
        valid=True,
        issues=[],
    )
    
    # Check extension
    if path.suffix.lower() not in ('.wav', '.wave'):
        result.valid = False
        result.issues.append(f"Invalid format: {path.suffix} (must be .wav)")
        return result
    
    try:
        # Read audio info
        info = sf.info(str(path))
        
        result.channels = info.channels
        result.sample_rate = int(info.samplerate)
        result.duration = info.duration
        result.format_type = info.format
        
        # Determine bit depth from subtype
        subtype = info.subtype
        if 'PCM_16' in subtype:
            result.bit_depth = 16
        elif 'PCM_24' in subtype:
            result.bit_depth = 24
        elif 'PCM_32' in subtype or 'FLOAT' in subtype:
            result.bit_depth = 32
        elif 'PCM_S8' in subtype or 'PCM_U8' in subtype:
            result.bit_depth = 8
        else:
            result.bit_depth = 16  # Assume 16 if unknown
        
        # Validate channels
        if result.channels != 1:
            result.valid = False
            result.issues.append(f"stereo ({result.channels} channels) - must be mono")
            
            if fix_issues:
                _fix_stereo_to_mono(path)
                result.fixed = True
                result.issues[-1] += " [FIXED]"
        
        # Validate sample rate
        if result.sample_rate != expected_sample_rate:
            if result.sample_rate not in RECOMMENDED_SAMPLE_RATES:
                result.issues.append(
                    f"sample rate {result.sample_rate}Hz (recommended: {expected_sample_rate}Hz)"
                )
                if fix_issues:
                    _fix_sample_rate(path, expected_sample_rate)
                    result.fixed = True
                    result.issues[-1] += " [FIXED]"
            else:
                # Info only - still valid if it's a known good rate
                result.issues.append(
                    f"sample rate {result.sample_rate}Hz (expected {expected_sample_rate}Hz)"
                )
        
        # Validate duration
        if result.duration > MAX_EVENT_DURATION:
            result.issues.append(
                f"duration {result.duration:.1f}s exceeds {MAX_EVENT_DURATION}s max"
            )
        
        if result.duration < 0.01:
            result.valid = False
            result.issues.append("duration too short (< 10ms)")
        
        # Validate bit depth
        if result.bit_depth not in (16, 24, 32):
            result.issues.append(f"bit depth {result.bit_depth} (16-bit recommended)")
        
    except Exception as e:
        result.valid = False
        result.issues.append(f"Failed to read: {e}")
    
    return result


def validate_assets_directory(
    directory: Path | str,
    *,
    expected_sample_rate: int = 24000,
    fix_issues: bool = False,
    recursive: bool = True,
) -> list[ValidationResult]:
    """Validate all audio assets in a directory.
    
    Args:
        directory: Directory to scan
        expected_sample_rate: Expected sample rate for all files
        fix_issues: Attempt to fix issues
        recursive: Scan subdirectories
    
    Returns:
        List of ValidationResults
    """
    directory = Path(directory)
    results = []
    
    # Find all wav files
    pattern = "**/*.wav" if recursive else "*.wav"
    files = sorted(directory.glob(pattern))
    
    for file_path in files:
        result = validate_asset(
            file_path,
            expected_sample_rate=expected_sample_rate,
            fix_issues=fix_issues,
        )
        result.relative_path = str(file_path.relative_to(directory))
        results.append(result)
    
    return results


def _fix_stereo_to_mono(path: Path):
    """Convert stereo audio to mono."""
    try:
        data, sr = sf.read(str(path))
        
        if len(data.shape) > 1:
            # Average channels
            data = data.mean(axis=1)
        
        sf.write(str(path), data, sr)
        logger.info(f"Fixed stereo to mono: {path}")
        
    except Exception as e:
        logger.error(f"Failed to fix stereo: {path}: {e}")


def _fix_sample_rate(path: Path, target_sr: int):
    """Resample audio to target sample rate."""
    try:
        data, sr = sf.read(str(path))
        
        if sr == target_sr:
            return
        
        # Simple resampling via interpolation
        duration = len(data) / sr
        target_length = int(duration * target_sr)
        
        x_original = np.linspace(0, 1, len(data))
        x_target = np.linspace(0, 1, target_length)
        
        if len(data.shape) > 1:
            # Multi-channel
            resampled = np.zeros((target_length, data.shape[1]))
            for ch in range(data.shape[1]):
                resampled[:, ch] = np.interp(x_target, x_original, data[:, ch])
        else:
            resampled = np.interp(x_target, x_original, data)
        
        sf.write(str(path), resampled.astype(np.float32), target_sr)
        logger.info(f"Resampled {sr}Hz -> {target_sr}Hz: {path}")
        
    except Exception as e:
        logger.error(f"Failed to resample: {path}: {e}")


def generate_asset_report(results: list[ValidationResult]) -> str:
    """Generate a detailed validation report.
    
    Args:
        results: List of ValidationResults
    
    Returns:
        Formatted report string
    """
    lines = ["# Asset Validation Report", ""]
    
    # Summary
    valid_count = sum(1 for r in results if r.valid)
    invalid_count = len(results) - valid_count
    fixed_count = sum(1 for r in results if r.fixed)
    
    lines.extend([
        "## Summary",
        f"- Total files: {len(results)}",
        f"- Valid: {valid_count}",
        f"- Invalid: {invalid_count}",
        f"- Fixed: {fixed_count}",
        "",
    ])
    
    # Issues by type
    all_issues = [issue for r in results for issue in r.issues]
    if all_issues:
        lines.extend([
            "## Issues",
            "",
        ])
        
        from collections import Counter
        issue_counts = Counter(all_issues)
        for issue, count in issue_counts.most_common():
            lines.append(f"- {issue}: {count} files")
        lines.append("")
    
    # File details
    lines.extend([
        "## File Details",
        "",
    ])
    
    for result in results:
        status = "✅" if result.valid else "❌"
        if result.fixed:
            status = "🔧"
        
        lines.append(f"### {status} {result.relative_path}")
        
        if result.channels > 0:
            lines.append(f"- Channels: {result.channels}")
            lines.append(f"- Sample rate: {result.sample_rate} Hz")
            lines.append(f"- Bit depth: {result.bit_depth}")
            lines.append(f"- Duration: {result.duration:.2f}s")
        
        if result.issues:
            lines.append("- Issues:")
            for issue in result.issues:
                lines.append(f"  - {issue}")
        
        lines.append("")
    
    return "\n".join(lines)
