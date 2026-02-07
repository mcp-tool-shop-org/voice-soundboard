"""
Graph Diff Tool - Compare ControlGraphs side-by-side.

Shows human-readable diffs of prosody and control changes
between two graphs.

Usage:
    from voice_soundboard.debug import diff_graphs
    
    g1 = compile_request("Hello", emotion="happy")
    g2 = compile_request("Hello", emotion="sad")
    
    diff = diff_graphs(g1, g2)
    print(diff)
    # Differences:
    #   tokens[0].pitch_scale: 1.1 → 0.9
    #   tokens[0].energy_scale: 1.2 → 0.8
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from voice_soundboard.graph import ControlGraph


@dataclass
class FieldDiff:
    """A single field difference."""
    path: str
    old_value: Any
    new_value: Any
    
    def __str__(self) -> str:
        old_str = self._format_value(self.old_value)
        new_str = self._format_value(self.new_value)
        return f"{self.path}: {old_str} → {new_str}"
    
    def _format_value(self, value: Any) -> str:
        if isinstance(value, float):
            return f"{value:.3f}"
        if isinstance(value, list) and len(value) > 5:
            return f"[{len(value)} items]"
        return str(value)


@dataclass
class GraphDiff:
    """Complete diff between two graphs."""
    diffs: list[FieldDiff] = field(default_factory=list)
    left_only: list[str] = field(default_factory=list)
    right_only: list[str] = field(default_factory=list)
    
    @property
    def has_differences(self) -> bool:
        return bool(self.diffs or self.left_only or self.right_only)
    
    @property
    def change_count(self) -> int:
        return len(self.diffs) + len(self.left_only) + len(self.right_only)
    
    def summary(self) -> str:
        """Short summary of changes."""
        if not self.has_differences:
            return "No differences"
        
        parts = []
        if self.diffs:
            parts.append(f"{len(self.diffs)} field changes")
        if self.left_only:
            parts.append(f"{len(self.left_only)} removed")
        if self.right_only:
            parts.append(f"{len(self.right_only)} added")
        
        return ", ".join(parts)
    
    def report(self) -> str:
        """Detailed diff report."""
        if not self.has_differences:
            return "Graphs are identical"
        
        lines = ["Differences:"]
        
        for diff in self.diffs:
            lines.append(f"  {diff}")
        
        if self.left_only:
            lines.append("")
            lines.append("Only in left graph:")
            for item in self.left_only:
                lines.append(f"  - {item}")
        
        if self.right_only:
            lines.append("")
            lines.append("Only in right graph:")
            for item in self.right_only:
                lines.append(f"  + {item}")
        
        return "\n".join(lines)
    
    def __str__(self) -> str:
        return self.report()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "has_differences": self.has_differences,
            "change_count": self.change_count,
            "diffs": [
                {"path": d.path, "old": d.old_value, "new": d.new_value}
                for d in self.diffs
            ],
            "left_only": self.left_only,
            "right_only": self.right_only,
        }


def diff_graphs(
    left: "ControlGraph",
    right: "ControlGraph",
    *,
    ignore_fields: list[str] | None = None,
    precision: int = 3,
) -> GraphDiff:
    """Compare two ControlGraphs and return differences.
    
    Args:
        left: First graph (baseline)
        right: Second graph (comparison)
        ignore_fields: Fields to ignore (e.g., ["source_text"])
        precision: Decimal precision for float comparison
    
    Returns:
        GraphDiff with all differences
    
    Example:
        g1 = compile_request("Hello", emotion="happy")
        g2 = compile_request("Hello", emotion="sad")
        
        diff = diff_graphs(g1, g2)
        print(diff)
    """
    ignore = set(ignore_fields or [])
    result = GraphDiff()
    
    # Helper for float comparison
    def floats_equal(a: float, b: float) -> bool:
        return round(a, precision) == round(b, precision)
    
    # Compare global properties
    global_fields = [
        ("global_speed", left.global_speed, right.global_speed),
        ("global_pitch", left.global_pitch, right.global_pitch),
        ("sample_rate", left.sample_rate, right.sample_rate),
    ]
    
    for name, left_val, right_val in global_fields:
        if name in ignore:
            continue
        
        if isinstance(left_val, float) and isinstance(right_val, float):
            if not floats_equal(left_val, right_val):
                result.diffs.append(FieldDiff(name, left_val, right_val))
        elif left_val != right_val:
            result.diffs.append(FieldDiff(name, left_val, right_val))
    
    # Compare speaker
    if "speaker" not in ignore:
        if left.speaker.type != right.speaker.type:
            result.diffs.append(FieldDiff(
                "speaker.type", left.speaker.type, right.speaker.type
            ))
        if left.speaker.value != right.speaker.value:
            result.diffs.append(FieldDiff(
                "speaker.value", left.speaker.value, right.speaker.value
            ))
    
    # Compare tokens
    if "tokens" not in ignore:
        _diff_tokens(left.tokens, right.tokens, result, floats_equal)
    
    # Compare events
    left_events = getattr(left, 'events', []) or []
    right_events = getattr(right, 'events', []) or []
    
    if "events" not in ignore:
        _diff_events(left_events, right_events, result)
    
    return result


def _diff_tokens(
    left_tokens: list,
    right_tokens: list,
    result: GraphDiff,
    floats_equal,
):
    """Compare token lists."""
    max_len = max(len(left_tokens), len(right_tokens))
    
    for i in range(max_len):
        prefix = f"tokens[{i}]"
        
        if i >= len(left_tokens):
            result.right_only.append(f"{prefix}: {right_tokens[i].text!r}")
            continue
        
        if i >= len(right_tokens):
            result.left_only.append(f"{prefix}: {left_tokens[i].text!r}")
            continue
        
        left_tok = left_tokens[i]
        right_tok = right_tokens[i]
        
        # Compare token fields
        if left_tok.text != right_tok.text:
            result.diffs.append(FieldDiff(
                f"{prefix}.text", left_tok.text, right_tok.text
            ))
        
        if not floats_equal(left_tok.pitch_scale, right_tok.pitch_scale):
            result.diffs.append(FieldDiff(
                f"{prefix}.pitch_scale", left_tok.pitch_scale, right_tok.pitch_scale
            ))
        
        if not floats_equal(left_tok.energy_scale, right_tok.energy_scale):
            result.diffs.append(FieldDiff(
                f"{prefix}.energy_scale", left_tok.energy_scale, right_tok.energy_scale
            ))
        
        if not floats_equal(left_tok.duration_scale, right_tok.duration_scale):
            result.diffs.append(FieldDiff(
                f"{prefix}.duration_scale", left_tok.duration_scale, right_tok.duration_scale
            ))
        
        if not floats_equal(left_tok.pause_after, right_tok.pause_after):
            result.diffs.append(FieldDiff(
                f"{prefix}.pause_after", left_tok.pause_after, right_tok.pause_after
            ))
        
        if not floats_equal(left_tok.emphasis, right_tok.emphasis):
            result.diffs.append(FieldDiff(
                f"{prefix}.emphasis", left_tok.emphasis, right_tok.emphasis
            ))


def _diff_events(
    left_events: list,
    right_events: list,
    result: GraphDiff,
):
    """Compare event lists."""
    max_len = max(len(left_events), len(right_events))
    
    for i in range(max_len):
        prefix = f"events[{i}]"
        
        if i >= len(left_events):
            result.right_only.append(f"{prefix}: {right_events[i].type.value}")
            continue
        
        if i >= len(right_events):
            result.left_only.append(f"{prefix}: {left_events[i].type.value}")
            continue
        
        left_evt = left_events[i]
        right_evt = right_events[i]
        
        if left_evt.type != right_evt.type:
            result.diffs.append(FieldDiff(
                f"{prefix}.type", left_evt.type.value, right_evt.type.value
            ))
        
        if left_evt.duration != right_evt.duration:
            result.diffs.append(FieldDiff(
                f"{prefix}.duration", left_evt.duration, right_evt.duration
            ))
        
        if left_evt.intensity != right_evt.intensity:
            result.diffs.append(FieldDiff(
                f"{prefix}.intensity", left_evt.intensity, right_evt.intensity
            ))


def diff_graphs_html(left: "ControlGraph", right: "ControlGraph") -> str:
    """Generate HTML diff view of two graphs.
    
    Returns an HTML string showing side-by-side comparison
    with highlighted differences.
    """
    diff = diff_graphs(left, right)
    
    # Simple HTML template
    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Graph Diff</title>
    <style>
        body {{ font-family: sans-serif; padding: 20px; background: #1a1a2e; color: #eee; }}
        h1 {{ color: #00d4ff; }}
        .diff {{ background: #16213e; padding: 20px; border-radius: 8px; }}
        .changed {{ color: #ffc107; }}
        .added {{ color: #4caf50; }}
        .removed {{ color: #e94560; }}
        pre {{ white-space: pre-wrap; }}
    </style>
</head>
<body>
    <h1>Graph Diff</h1>
    <div class="diff">
        <pre>{diff.report()}</pre>
    </div>
</body>
</html>'''
    
    return html
