"""Tests for the incremental compiler."""

import pytest
from voice_soundboard.compiler import IncrementalCompiler, compile_incremental
from voice_soundboard.graph import ControlGraph, Paralinguistic


class TestIncrementalCompiler:
    """Tests for IncrementalCompiler."""
    
    def test_basic_feed(self):
        """Single complete sentence emits one graph."""
        compiler = IncrementalCompiler()
        graphs = compiler.feed("Hello world.")
        
        assert len(graphs) == 1
        assert "Hello world" in graphs[0].text
    
    def test_sentence_boundary(self):
        """Sentence punctuation triggers commit."""
        compiler = IncrementalCompiler()
        
        # Feed partial sentence
        graphs = compiler.feed("Hello")
        assert len(graphs) == 0  # No boundary yet
        
        # Complete sentence
        graphs = compiler.feed(" world.")
        assert len(graphs) == 1
    
    def test_multiple_sentences(self):
        """Multiple sentences emit multiple graphs."""
        compiler = IncrementalCompiler()
        graphs = compiler.feed("Hello. World. Test.")
        
        assert len(graphs) == 3
    
    def test_finalize_flushes_remainder(self):
        """Finalize emits incomplete buffer."""
        compiler = IncrementalCompiler()
        
        # Feed incomplete sentence
        graphs = compiler.feed("Hello world")
        assert len(graphs) == 0
        
        # Finalize
        graphs = compiler.finalize()
        assert len(graphs) == 1
        assert "Hello world" in graphs[0].text
    
    def test_clause_boundary_long_text(self):
        """Clause punctuation triggers commit when buffer is long."""
        compiler = IncrementalCompiler(max_buffer_chars=50)
        
        # Feed long text with comma
        text = "This is a somewhat longer sentence with multiple clauses, and this continues."
        graphs = compiler.feed(text)
        
        # Should have committed at least at the period
        assert len(graphs) >= 1
    
    def test_max_buffer_forces_commit(self):
        """Very long text without punctuation gets force-committed."""
        compiler = IncrementalCompiler(max_buffer_chars=20)
        
        graphs = compiler.feed("hello world this is a very long text without punctuation")
        
        # Should have force-committed
        assert len(graphs) >= 1
    
    def test_paralinguistic_tag_extraction(self):
        """[laugh] tags become ParalinguisticEvents."""
        compiler = IncrementalCompiler()
        graphs = compiler.feed("[laugh] Ha ha!")
        
        # Finalize to get all content
        graphs.extend(compiler.finalize())
        
        # Should have at least one graph with event
        all_events = [e for g in graphs for e in g.events]
        assert len(all_events) >= 1
        assert any(e.type == Paralinguistic.LAUGH for e in all_events)
    
    def test_pure_event_segment(self):
        """Segment with only paralinguistic tag still works."""
        compiler = IncrementalCompiler()
        graphs = compiler.feed("[sigh]")
        
        # Pure event should emit immediately
        assert len(graphs) == 1
        assert len(graphs[0].events) == 1
        assert graphs[0].events[0].type == Paralinguistic.SIGH
    
    def test_multiple_events(self):
        """Multiple tags in text become multiple events."""
        compiler = IncrementalCompiler()
        graphs = compiler.feed("[laugh] Oh wow [sigh] that's funny.")
        
        graphs.extend(compiler.finalize())
        
        all_events = [e for g in graphs for e in g.events]
        event_types = {e.type for e in all_events}
        
        assert Paralinguistic.LAUGH in event_types
        assert Paralinguistic.SIGH in event_types
    
    def test_unknown_tag_preserved(self):
        """Unknown tags [foo] are left as text, not events."""
        compiler = IncrementalCompiler()
        graphs = compiler.feed("[foo] Hello.")
        
        # Should have no events for unknown tag
        assert len(graphs[0].events) == 0
        # Tag should be in text
        assert "[foo]" in graphs[0].text or "foo" in graphs[0].text
    
    def test_voice_setting_preserved(self):
        """Voice setting is preserved across segments."""
        compiler = IncrementalCompiler(voice="am_michael")
        
        graphs = compiler.feed("Hello. World.")
        
        for graph in graphs:
            assert graph.speaker.value == "am_michael"
    
    def test_emotion_applied(self):
        """Emotion is applied to all segments."""
        compiler = IncrementalCompiler(emotion="happy")
        
        graphs = compiler.feed("Hello world.")
        
        # Happy emotion should affect prosody (speed > 1.0)
        assert graphs[0].global_speed >= 1.0
    
    def test_reset_clears_buffer(self):
        """Reset allows reuse of compiler."""
        compiler = IncrementalCompiler()
        
        compiler.feed("Hello")  # Partial
        compiler.reset()
        
        graphs = compiler.feed("World.")
        assert len(graphs) == 1
        assert "Hello" not in graphs[0].text


class TestCompileIncremental:
    """Tests for compile_incremental convenience function."""
    
    def test_basic_usage(self):
        """Compile multiple chunks."""
        chunks = ["Hello ", "world. ", "How are ", "you?"]
        graphs = compile_incremental(chunks)
        
        assert len(graphs) == 2  # "Hello world." and "How are you?"
    
    def test_with_options(self):
        """Options are passed through."""
        chunks = ["Hello."]
        graphs = compile_incremental(chunks, voice="am_michael")
        
        assert graphs[0].speaker.value == "am_michael"


class TestIncrementalCompilerEdgeCases:
    """Edge case tests for incremental compiler."""
    
    def test_empty_feed(self):
        """Empty string produces nothing."""
        compiler = IncrementalCompiler()
        graphs = compiler.feed("")
        
        assert len(graphs) == 0
    
    def test_whitespace_only(self):
        """Whitespace-only produces nothing."""
        compiler = IncrementalCompiler()
        graphs = compiler.feed("   \n\t  ")
        graphs.extend(compiler.finalize())
        
        assert len(graphs) == 0
    
    def test_streaming_simulation(self):
        """Simulate LLM streaming output."""
        compiler = IncrementalCompiler()
        all_graphs = []
        
        # Simulate character-by-character streaming
        for char in "Hello world. How are you?":
            graphs = compiler.feed(char)
            all_graphs.extend(graphs)
        
        all_graphs.extend(compiler.finalize())
        
        # Should have 2 complete segments
        assert len(all_graphs) == 2
    
    def test_exclamation_triggers_commit(self):
        """Exclamation mark triggers commit."""
        compiler = IncrementalCompiler()
        graphs = compiler.feed("Wow!")
        
        assert len(graphs) == 1
    
    def test_question_triggers_commit(self):
        """Question mark triggers commit."""
        compiler = IncrementalCompiler()
        graphs = compiler.feed("Really?")
        
        assert len(graphs) == 1
