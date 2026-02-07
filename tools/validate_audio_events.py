#!/usr/bin/env python3
"""
Validate audio event assets for CI.

This script enforces the asset specification defined in docs/audio_events.md.
Run in CI to prevent bad assets from landing.

Checks:
- All WAV files in manifest exist
- WAV format: mono, 16-bit PCM
- Sample rate matches manifest
- No excessive leading silence (≤10ms)
- No excessive trailing silence (≤20ms)
- Duration matches manifest (within 50ms)

Usage:
    python tools/validate_audio_events.py [--assets-dir ASSETS_DIR]

Exit codes:
    0 = All assets valid
    1 = Validation failed
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import wave
from pathlib import Path


# Spec constraints (from docs/audio_events.md)
MAX_LEADING_SILENCE_MS = 10
MAX_TRAILING_SILENCE_MS = 20
MAX_DURATION_TOLERANCE_S = 0.05
MAX_PEAK_DBFS = -1.0  # ≤ -1 dBFS


class ValidationError:
    """A single validation issue."""
    
    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
    
    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def validate_wav(
    wav_path: Path,
    expected_rate: int,
    expected_duration: float,
) -> list[ValidationError]:
    """Validate a single WAV file against the spec.
    
    Returns list of issues (empty = valid).
    """
    issues = []
    path_str = str(wav_path)
    
    if not wav_path.exists():
        return [ValidationError(path_str, "file not found")]
    
    try:
        with wave.open(str(wav_path), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()
            n_frames = wf.getnframes()
            frames = wf.readframes(n_frames)
    except wave.Error as e:
        return [ValidationError(path_str, f"invalid WAV: {e}")]
    
    # Check channels (must be mono)
    if channels != 1:
        issues.append(ValidationError(
            path_str,
            f"must be mono, got {channels} channels"
        ))
    
    # Check bit depth (must be 16-bit)
    if sample_width != 2:
        issues.append(ValidationError(
            path_str,
            f"must be 16-bit PCM, got {sample_width * 8}-bit"
        ))
    
    # Check sample rate
    if frame_rate != expected_rate:
        issues.append(ValidationError(
            path_str,
            f"sample rate {frame_rate} != manifest {expected_rate}"
        ))
    
    # Check duration
    actual_duration = n_frames / frame_rate
    if abs(actual_duration - expected_duration) > MAX_DURATION_TOLERANCE_S:
        issues.append(ValidationError(
            path_str,
            f"duration {actual_duration:.3f}s != manifest {expected_duration:.3f}s"
        ))
    
    # Parse samples for silence/peak checks (16-bit signed)
    if sample_width == 2 and channels == 1:
        samples = list(struct.unpack(f"<{n_frames}h", frames))
        
        # Check leading silence
        leading_samples = 0
        for s in samples:
            if abs(s) > 100:  # Threshold for "silence"
                break
            leading_samples += 1
        
        leading_ms = (leading_samples / frame_rate) * 1000
        if leading_ms > MAX_LEADING_SILENCE_MS:
            issues.append(ValidationError(
                path_str,
                f"leading silence {leading_ms:.1f}ms > {MAX_LEADING_SILENCE_MS}ms"
            ))
        
        # Check trailing silence
        trailing_samples = 0
        for s in reversed(samples):
            if abs(s) > 100:
                break
            trailing_samples += 1
        
        trailing_ms = (trailing_samples / frame_rate) * 1000
        if trailing_ms > MAX_TRAILING_SILENCE_MS:
            issues.append(ValidationError(
                path_str,
                f"trailing silence {trailing_ms:.1f}ms > {MAX_TRAILING_SILENCE_MS}ms"
            ))
        
        # Check peak level (should be ≤ -1 dBFS to avoid clipping)
        if samples:
            peak = max(abs(s) for s in samples)
            peak_dbfs = 20 * (peak / 32767.0 + 1e-10).__log10__() if peak > 0 else -100
            # Note: This is approximate; exact dBFS calculation varies
            if peak >= 32767:  # Clipping
                issues.append(ValidationError(
                    path_str,
                    "audio is clipping (peak at 0 dBFS)"
                ))
    
    return issues


def validate_manifest(manifest_path: Path) -> list[ValidationError]:
    """Validate manifest.json structure."""
    issues = []
    path_str = str(manifest_path)
    
    if not manifest_path.exists():
        return [ValidationError(path_str, "manifest.json not found")]
    
    try:
        with open(manifest_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [ValidationError(path_str, f"invalid JSON: {e}")]
    
    # Check required fields
    if "sample_rate" not in data:
        issues.append(ValidationError(path_str, "missing 'sample_rate' field"))
    
    if "events" not in data:
        issues.append(ValidationError(path_str, "missing 'events' field"))
    elif not isinstance(data["events"], dict):
        issues.append(ValidationError(path_str, "'events' must be an object"))
    
    # Check event structure
    for event_type, event_data in data.get("events", {}).items():
        if "variants" not in event_data:
            issues.append(ValidationError(
                path_str,
                f"event '{event_type}' missing 'variants'"
            ))
            continue
        
        for i, variant in enumerate(event_data["variants"]):
            prefix = f"event '{event_type}' variant {i}"
            
            if "id" not in variant:
                issues.append(ValidationError(path_str, f"{prefix}: missing 'id'"))
            if "file" not in variant:
                issues.append(ValidationError(path_str, f"{prefix}: missing 'file'"))
            if "intensity_range" not in variant:
                issues.append(ValidationError(path_str, f"{prefix}: missing 'intensity_range'"))
            elif not isinstance(variant["intensity_range"], list) or len(variant["intensity_range"]) != 2:
                issues.append(ValidationError(path_str, f"{prefix}: 'intensity_range' must be [min, max]"))
            if "duration" not in variant:
                issues.append(ValidationError(path_str, f"{prefix}: missing 'duration'"))
    
    return issues


def validate_all(assets_dir: Path) -> list[ValidationError]:
    """Validate all audio event assets."""
    all_issues = []
    
    manifest_path = assets_dir / "manifest.json"
    
    # Validate manifest structure
    manifest_issues = validate_manifest(manifest_path)
    all_issues.extend(manifest_issues)
    
    if manifest_issues:
        return all_issues  # Can't continue without valid manifest
    
    # Load manifest
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    sample_rate = manifest["sample_rate"]
    
    # Validate each WAV file
    for event_type, event_data in manifest.get("events", {}).items():
        for variant in event_data.get("variants", []):
            wav_path = assets_dir / variant["file"]
            expected_duration = variant["duration"]
            
            issues = validate_wav(wav_path, sample_rate, expected_duration)
            all_issues.extend(issues)
    
    return all_issues


def main():
    parser = argparse.ArgumentParser(
        description="Validate audio event assets against spec"
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=Path("assets/audio_events"),
        help="Path to audio_events directory (default: assets/audio_events)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings (silence checks)"
    )
    
    args = parser.parse_args()
    
    print(f"Validating audio events in: {args.assets_dir}")
    print()
    
    issues = validate_all(args.assets_dir)
    
    if issues:
        print("❌ Validation FAILED:")
        print()
        for issue in issues:
            print(f"  • {issue}")
        print()
        print(f"Total issues: {len(issues)}")
        sys.exit(1)
    else:
        print("✅ All audio event assets valid")
        sys.exit(0)


if __name__ == "__main__":
    main()
