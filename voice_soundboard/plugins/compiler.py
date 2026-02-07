"""
Compiler plugin for custom text transforms and markup.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from voice_soundboard.graph import ControlGraph
from voice_soundboard.plugins.base import Plugin, PluginType


class CompilerPlugin(Plugin):
    """Plugin for extending the compiler with custom transforms.
    
    Compiler plugins can:
    - Pre-process text before compilation
    - Post-process graphs after compilation
    - Add custom markup/syntax
    - Inject context (emotion detection, etc.)
    
    Pipeline:
        text → pre_compile() → compile → post_compile() → graph
    
    Example:
        @plugin
        class EmotionDetectorPlugin(CompilerPlugin):
            name = "emotion_detector"
            
            def pre_compile(self, text, context):
                sentiment = analyze_sentiment(text)
                context["emotion"] = sentiment_to_emotion(sentiment)
                return text, context
        
        # Automatically detects emotion from text sentiment
    """
    
    plugin_type = PluginType.COMPILER
    
    # Plugin priority (lower = runs earlier)
    priority: int = 100
    
    def pre_compile(
        self,
        text: str,
        context: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        """Pre-process text before compilation.
        
        Called before the compiler processes the text.
        Can modify text and/or add context.
        
        Args:
            text: Input text to be compiled.
            context: Compilation context (voice, emotion, etc.).
        
        Returns:
            Tuple of (modified_text, modified_context).
        """
        return text, context
    
    def post_compile(
        self,
        graph: ControlGraph,
        context: dict[str, Any],
    ) -> ControlGraph:
        """Post-process graph after compilation.
        
        Called after the compiler produces a graph.
        Can modify the graph structure.
        
        Args:
            graph: Compiled control graph.
            context: Compilation context.
        
        Returns:
            Modified control graph.
        """
        return graph
    
    def on_load(self, registry) -> None:
        """Register the compiler plugin."""
        registry.register_compiler_plugin(self)
    
    def on_unload(self) -> None:
        """Cleanup compiler plugin."""
        pass


class MarkupPlugin(CompilerPlugin):
    """Plugin for adding custom markup syntax.
    
    Extends the text markup language with custom tags.
    
    Example:
        @plugin
        class HighlightPlugin(MarkupPlugin):
            name = "highlight"
            tag = "hl"  # [hl]text[/hl]
            
            def process_tag(self, content, attrs):
                # Add emphasis to highlighted content
                return content, {"emphasis": 1.2}
    """
    
    tag: str = ""  # The tag name, e.g., "hl" for [hl]...[/hl]
    
    @abstractmethod
    def process_tag(
        self,
        content: str,
        attrs: dict[str, str],
    ) -> tuple[str, dict[str, Any]]:
        """Process a custom markup tag.
        
        Args:
            content: Text content inside the tag.
            attrs: Tag attributes, e.g., [tag attr=value].
        
        Returns:
            Tuple of (processed_content, token_modifiers).
        """
        ...
    
    def pre_compile(self, text: str, context: dict) -> tuple[str, dict]:
        """Process custom tags in text."""
        import re
        
        if not self.tag:
            return text, context
        
        # Simple tag pattern: [tag]content[/tag] or [tag attr=value]content[/tag]
        pattern = rf'\[{self.tag}(?:\s+([^\]]*))?\](.*?)\[/{self.tag}\]'
        
        def replace(match):
            attrs_str = match.group(1) or ""
            content = match.group(2)
            
            # Parse attributes
            attrs = {}
            if attrs_str:
                for attr in attrs_str.split():
                    if "=" in attr:
                        key, value = attr.split("=", 1)
                        attrs[key] = value.strip('"\'')
            
            processed, modifiers = self.process_tag(content, attrs)
            
            # Store modifiers in context for graph processing
            if "_tag_modifiers" not in context:
                context["_tag_modifiers"] = []
            context["_tag_modifiers"].append({
                "content": processed,
                "modifiers": modifiers,
            })
            
            return processed
        
        text = re.sub(pattern, replace, text, flags=re.DOTALL)
        return text, context


class TransformPlugin(CompilerPlugin):
    """Plugin for text transformations.
    
    Applies transformations to text before compilation.
    
    Example:
        @plugin
        class AbbreviationExpanderPlugin(TransformPlugin):
            name = "abbrev_expander"
            
            abbreviations = {
                "Dr.": "Doctor",
                "vs.": "versus",
            }
            
            def transform(self, text):
                for abbr, expansion in self.abbreviations.items():
                    text = text.replace(abbr, expansion)
                return text
    """
    
    @abstractmethod
    def transform(self, text: str) -> str:
        """Transform input text.
        
        Args:
            text: Input text.
        
        Returns:
            Transformed text.
        """
        ...
    
    def pre_compile(self, text: str, context: dict) -> tuple[str, dict]:
        """Apply text transformation."""
        return self.transform(text), context
