"""
Debug Module - Developer experience tools for v2.1.

v2.1 Features (P1):
    - Debug Mode: Timing and cache information
    - Graph Visualization: Interactive timeline view
    - Timing Profiler: Detailed performance breakdown
    - Graph Diff Tool: Compare graphs side-by-side

Usage:
    from voice_soundboard.debug import (
        visualize_graph,
        profile_synthesis,
        diff_graphs,
        DebugInfo,
    )
    
    # Visualize a graph
    visualize_graph(graph)  # Opens browser
    
    # Profile synthesis
    with profile_synthesis() as prof:
        engine.speak("Hello")
    prof.report()
    
    # Compare graphs
    diff_graphs(graph1, graph2)
"""

from voice_soundboard.debug.info import DebugInfo, DebugContext
from voice_soundboard.debug.visualizer import visualize_graph, GraphVisualizer
from voice_soundboard.debug.profiler import profile_synthesis, SynthesisProfiler, ProfileReport
from voice_soundboard.debug.diff import diff_graphs, GraphDiff

__all__ = [
    # Debug info
    "DebugInfo",
    "DebugContext",
    # Visualization
    "visualize_graph",
    "GraphVisualizer",
    # Profiling
    "profile_synthesis",
    "SynthesisProfiler",
    "ProfileReport",
    # Diff
    "diff_graphs",
    "GraphDiff",
]
