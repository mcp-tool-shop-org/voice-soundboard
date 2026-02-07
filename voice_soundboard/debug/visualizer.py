"""
Graph Visualizer - Interactive timeline view for ControlGraphs.

Opens a browser with an interactive visualization showing:
- Tokens with prosody curves
- Paralinguistic events
- Timing information

Usage:
    from voice_soundboard.debug import visualize_graph
    
    graph = compile_request("Hello, [laugh] world!")
    visualize_graph(graph)  # Opens browser with timeline view
"""

from __future__ import annotations

import html
import json
import tempfile
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from voice_soundboard.graph import ControlGraph


# HTML template for visualization
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Soundboard - Graph Visualization</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #1a1a2e; 
            color: #eee; 
            padding: 20px;
            min-height: 100vh;
        }
        h1 { 
            color: #00d4ff; 
            margin-bottom: 10px;
            font-weight: 500;
        }
        .subtitle { 
            color: #888; 
            margin-bottom: 30px; 
            font-size: 14px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        
        .timeline {
            background: #16213e;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            overflow-x: auto;
        }
        .timeline-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #333;
        }
        .timeline-title { color: #00d4ff; font-size: 14px; font-weight: 500; }
        .timeline-meta { color: #666; font-size: 12px; }
        
        .tokens-track {
            display: flex;
            gap: 4px;
            min-height: 80px;
            align-items: flex-end;
            padding-bottom: 10px;
        }
        .token {
            background: linear-gradient(135deg, #0f3460 0%, #16213e 100%);
            border: 1px solid #00d4ff33;
            border-radius: 6px;
            padding: 10px 14px;
            min-width: 60px;
            text-align: center;
            position: relative;
            transition: all 0.2s;
        }
        .token:hover {
            border-color: #00d4ff;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 212, 255, 0.2);
        }
        .token-text { 
            font-size: 14px; 
            margin-bottom: 6px;
            word-break: break-word;
        }
        .token-prosody {
            display: flex;
            gap: 6px;
            justify-content: center;
            flex-wrap: wrap;
        }
        .prosody-badge {
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 10px;
            background: #0f3460;
        }
        .prosody-badge.pitch { background: #e94560; }
        .prosody-badge.energy { background: #00d4ff; color: #000; }
        .prosody-badge.duration { background: #ffc107; color: #000; }
        
        .event {
            background: linear-gradient(135deg, #e94560 0%, #c73659 100%);
            border-radius: 6px;
            padding: 10px 14px;
            min-width: 60px;
            text-align: center;
        }
        .event-type { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }
        .event-meta { font-size: 10px; color: rgba(255,255,255,0.7); margin-top: 4px; }
        
        .info-section {
            background: #16213e;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .info-section h3 {
            color: #00d4ff;
            font-size: 14px;
            margin-bottom: 15px;
            font-weight: 500;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
        }
        .info-item {
            background: #0f3460;
            padding: 12px;
            border-radius: 6px;
        }
        .info-label { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
        .info-value { font-size: 16px; margin-top: 4px; }
        
        .source-text {
            background: #0f3460;
            padding: 15px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 14px;
            white-space: pre-wrap;
            word-break: break-word;
        }
        
        .legend {
            display: flex;
            gap: 20px;
            margin-top: 10px;
            font-size: 12px;
            color: #888;
        }
        .legend-item { display: flex; align-items: center; gap: 6px; }
        .legend-color {
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Voice Soundboard Graph Visualization</h1>
        <p class="subtitle">v2.1 Debug Tooling</p>
        
        <div class="timeline">
            <div class="timeline-header">
                <span class="timeline-title">Token Timeline</span>
                <span class="timeline-meta">{token_count} tokens, {event_count} events</span>
            </div>
            <div class="tokens-track">
                {tokens_html}
            </div>
            <div class="legend">
                <div class="legend-item"><div class="legend-color" style="background:#e94560"></div>Pitch</div>
                <div class="legend-item"><div class="legend-color" style="background:#00d4ff"></div>Energy</div>
                <div class="legend-item"><div class="legend-color" style="background:#ffc107"></div>Duration</div>
            </div>
        </div>
        
        <div class="info-section">
            <h3>Graph Properties</h3>
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">Speaker</div>
                    <div class="info-value">{speaker}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Speed</div>
                    <div class="info-value">{speed}x</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Pitch</div>
                    <div class="info-value">{pitch}x</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Sample Rate</div>
                    <div class="info-value">{sample_rate} Hz</div>
                </div>
            </div>
        </div>
        
        <div class="info-section">
            <h3>Source Text</h3>
            <div class="source-text">{source_text}</div>
        </div>
    </div>
    
    <script>
        // Graph data for interactive features
        const graphData = {graph_json};
        console.log('Graph data:', graphData);
    </script>
</body>
</html>'''


@dataclass
class GraphVisualizer:
    """Generates HTML visualizations for ControlGraphs."""
    
    def render(self, graph: "ControlGraph") -> str:
        """Render a ControlGraph to HTML string."""
        # Build tokens HTML
        tokens_html = []
        for i, token in enumerate(graph.tokens):
            prosody_badges = []
            if token.pitch_scale != 1.0:
                prosody_badges.append(
                    f'<span class="prosody-badge pitch">{token.pitch_scale:.2f}p</span>'
                )
            if token.energy_scale != 1.0:
                prosody_badges.append(
                    f'<span class="prosody-badge energy">{token.energy_scale:.2f}e</span>'
                )
            if token.duration_scale != 1.0:
                prosody_badges.append(
                    f'<span class="prosody-badge duration">{token.duration_scale:.2f}d</span>'
                )
            
            token_html = f'''
            <div class="token" title="Token {i}">
                <div class="token-text">{html.escape(token.text)}</div>
                <div class="token-prosody">
                    {"".join(prosody_badges) if prosody_badges else '<span style="color:#666;font-size:10px">neutral</span>'}
                </div>
            </div>
            '''
            tokens_html.append(token_html)
            
            # Add pause indicator if present
            if token.pause_after > 0:
                tokens_html.append(
                    f'<div style="width:2px;background:#333;height:60px;margin:0 2px" '
                    f'title="Pause: {token.pause_after:.2f}s"></div>'
                )
        
        # Add events
        events = getattr(graph, 'events', []) or []
        for event in events:
            tokens_html.append(f'''
            <div class="event" title="{event.type.value}">
                <div class="event-type">{event.type.value}</div>
                <div class="event-meta">{event.duration:.2f}s @ {event.intensity:.1f}</div>
            </div>
            ''')
        
        # Build graph JSON for JS
        graph_data = {
            "tokens": [
                {
                    "text": t.text,
                    "pitch_scale": t.pitch_scale,
                    "energy_scale": t.energy_scale,
                    "duration_scale": t.duration_scale,
                    "pause_after": t.pause_after,
                }
                for t in graph.tokens
            ],
            "events": [
                {
                    "type": e.type.value,
                    "start_time": e.start_time,
                    "duration": e.duration,
                    "intensity": e.intensity,
                }
                for e in events
            ],
            "speaker": graph.speaker.value if isinstance(graph.speaker.value, str) else "custom",
            "global_speed": graph.global_speed,
            "global_pitch": graph.global_pitch,
        }
        
        # Format HTML
        speaker_val = graph.speaker.value if isinstance(graph.speaker.value, str) else "custom embedding"
        source = getattr(graph, 'source_text', '') or "[no source text]"
        
        return HTML_TEMPLATE.format(
            tokens_html="\n".join(tokens_html),
            token_count=len(graph.tokens),
            event_count=len(events),
            speaker=html.escape(str(speaker_val)),
            speed=graph.global_speed,
            pitch=graph.global_pitch,
            sample_rate=graph.sample_rate or "auto",
            source_text=html.escape(source),
            graph_json=json.dumps(graph_data, indent=2),
        )


def visualize_graph(
    graph: "ControlGraph",
    *,
    open_browser: bool = True,
    output_path: Path | str | None = None,
) -> Path:
    """Visualize a ControlGraph in the browser.
    
    Opens an interactive HTML visualization showing:
    - Token timeline with prosody
    - Paralinguistic events
    - Graph metadata
    
    Args:
        graph: The ControlGraph to visualize
        open_browser: Whether to open the browser automatically
        output_path: Optional path to save the HTML file
    
    Returns:
        Path to the generated HTML file
    
    Example:
        graph = compile_request("Hello, [laugh] world!", emotion="happy")
        visualize_graph(graph)  # Opens browser
    """
    visualizer = GraphVisualizer()
    html_content = visualizer.render(graph)
    
    if output_path:
        path = Path(output_path)
    else:
        # Create temp file
        fd = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.html',
            delete=False,
            encoding='utf-8',
        )
        path = Path(fd.name)
        fd.write(html_content)
        fd.close()
    
    if output_path:
        path.write_text(html_content, encoding='utf-8')
    
    if open_browser:
        webbrowser.open(f'file://{path.absolute()}')
    
    return path
