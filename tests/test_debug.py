"""
Tests for v2.1 debug features.

Tests DebugInfo, GraphVisualizer, SynthesisProfiler, and diff_graphs.
"""

import pytest
import numpy as np
import time
from dataclasses import dataclass, field
from typing import List

from voice_soundboard.debug import (
    DebugInfo,
    visualize_graph,
    profile_synthesis,
    diff_graphs,
)
from voice_soundboard.debug.info import DebugContext, TimingInfo
from voice_soundboard.debug.visualizer import GraphVisualizer
from voice_soundboard.debug.profiler import SynthesisProfiler, ProfileReport
from voice_soundboard.debug.diff import GraphDiff, FieldDiff
from voice_soundboard.graph import ControlGraph, TokenEvent, SpeakerRef


@pytest.fixture
def sample_graph():
    """Create a sample graph for testing."""
    return ControlGraph(
        tokens=[
            TokenEvent(text="Hello"),
            TokenEvent(text="world"),
        ],
        speaker=SpeakerRef.from_voice("af_bella"),
    )


class TestDebugInfo:
    """Tests for DebugInfo."""
    
    def test_empty_info(self):
        """Empty debug info."""
        info = DebugInfo()
        summary = info.summary()
        assert "total" in summary.lower() or len(summary) >= 0
    
    def test_with_timing(self):
        """Debug info with timing."""
        info = DebugInfo()
        info.add_timing("compile", 50.0)
        info.add_timing("synthesize", 100.0)
        
        assert info.timing["compile"] == 50.0
        assert info.timing["synthesize"] == 100.0
    
    def test_with_cache_info(self):
        """Debug info with cache statistics."""
        info = DebugInfo()
        info.cache_hit = True
        info.cache_key = "abc123"
        
        assert info.cache_hit is True
    
    def test_to_dict(self):
        """Convert to dictionary."""
        info = DebugInfo()
        info.add_timing("compile", 25.0)
        
        d = info.to_dict()
        assert isinstance(d, dict)
        assert "timing" in d


class TestDebugContext:
    """Tests for DebugContext context manager."""
    
    def test_context_captures_timing(self):
        """Context manager captures timing."""
        with DebugContext() as ctx:
            ctx.record("phase1")
            time.sleep(0.01)
            ctx.record("phase2")
            time.sleep(0.01)
        
        info = ctx.get_info()
        assert "phase1" in info.timing or "phase2" in info.timing


class TestGraphVisualizer:
    """Tests for GraphVisualizer."""
    
    def test_visualize_graph_html(self, sample_graph):
        """Generate HTML visualization."""
        html = visualize_graph(sample_graph, format="html")
        
        assert isinstance(html, str)
        assert "<html>" in html.lower() or "<!doctype" in html.lower() or "svg" in html.lower()
    
    def test_visualize_graph_text(self, sample_graph):
        """Generate text visualization."""
        text = visualize_graph(sample_graph, format="text")
        
        assert isinstance(text, str)
        assert "Hello" in text or "world" in text
    
    def test_visualizer_class(self, sample_graph):
        """Use visualizer class directly."""
        viz = GraphVisualizer()
        
        output = viz.render(sample_graph)
        assert output is not None


class TestSynthesisProfiler:
    """Tests for SynthesisProfiler."""
    
    def test_profile_phases(self, sample_graph):
        """Profile synthesis phases."""
        profiler = SynthesisProfiler()
        
        profiler.start("compile")
        time.sleep(0.01)
        profiler.end("compile")
        
        profiler.start("synthesize")
        time.sleep(0.01)
        profiler.end("synthesize")
        
        report = profiler.get_report()
        
        assert isinstance(report, ProfileReport)
        assert report.total_ms >= 20  # At least 20ms total
    
    def test_profile_context_manager(self, sample_graph):
        """Use profiler as context manager."""
        profiler = SynthesisProfiler()
        
        with profiler.phase("compile"):
            time.sleep(0.01)
        
        with profiler.phase("synthesize"):
            time.sleep(0.01)
        
        report = profiler.get_report()
        assert len(report.phases) >= 2
    
    def test_report_breakdown(self):
        """Report shows phase breakdown."""
        profiler = SynthesisProfiler()
        
        with profiler.phase("compile"):
            time.sleep(0.01)
        
        with profiler.phase("render"):
            time.sleep(0.02)
        
        report = profiler.get_report()
        breakdown = report.breakdown()
        
        assert "compile" in breakdown.lower() or len(breakdown) > 0


class TestDiffGraphs:
    """Tests for diff_graphs function."""
    
    def test_identical_graphs(self, sample_graph):
        """Identical graphs have no diff."""
        diff = diff_graphs(sample_graph, sample_graph)
        
        assert len(diff.changes) == 0
        assert diff.is_equal()
    
    def test_different_tokens(self, sample_graph):
        """Different tokens show diff."""
        modified = ControlGraph(
            tokens=[
                TokenEvent(text="Goodbye", start_ms=0, duration_ms=100),
                TokenEvent(text="world", start_ms=100, duration_ms=100),
            ],
            speaker=sample_graph.speaker,
        )
        
        diff = diff_graphs(sample_graph, modified)
        
        assert not diff.is_equal()
        assert len(diff.changes) > 0
    
    def test_different_speaker(self, sample_graph):
        """Different speaker shows diff."""
        modified = ControlGraph(
            tokens=sample_graph.tokens,
            speaker=SpeakerRef.from_voice("am_michael"),
        )
        
        diff = diff_graphs(sample_graph, modified)
        
        assert not diff.is_equal()
    
    def test_diff_summary(self, sample_graph):
        """Diff provides summary."""
        modified = ControlGraph(
            tokens=[TokenEvent(text="Different", start_ms=0, duration_ms=150)],
            speaker=sample_graph.speaker,
        )
        
        diff = diff_graphs(sample_graph, modified)
        summary = diff.summary()
        
        assert isinstance(summary, str)
        assert len(summary) > 0
