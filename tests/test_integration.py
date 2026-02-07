"""Integration tests - verify the full pipeline works."""

import pytest
from pathlib import Path
import tempfile

from voice_soundboard import VoiceEngine, Config
from voice_soundboard.compiler import compile_request
from voice_soundboard.engine import MockBackend


class TestFullPipeline:
    """Test the complete compiler → engine pipeline."""
    
    def test_compile_then_synthesize(self):
        """The core architecture: compile_request → engine.synthesize."""
        # Compile
        graph = compile_request(
            "Hello world!",
            voice="af_bella",
            speed=1.0,
        )
        
        # Synthesize
        backend = MockBackend()
        audio = backend.synthesize(graph)
        
        assert len(audio) > 0
    
    def test_emotion_affects_output(self):
        """Emotion modifies prosody at compile time."""
        graph_neutral = compile_request("Hello!", emotion="neutral")
        graph_excited = compile_request("Hello!", emotion="excited")
        
        backend = MockBackend()
        audio_neutral = backend.synthesize(graph_neutral)
        audio_excited = backend.synthesize(graph_excited)
        
        # Excited emotion should affect duration (through speed)
        # With mock backend, different speeds = different lengths
        assert len(audio_neutral) != len(audio_excited)
    
    def test_preset_affects_output(self):
        """Presets set voice and speed."""
        graph = compile_request("Hello!", preset="narrator")
        
        # Narrator preset uses bm_george at 0.95 speed
        assert graph.speaker.value == "bm_george"
        assert graph.global_speed == 0.95


class TestVoiceEngineAPI:
    """Test the public VoiceEngine API."""
    
    def test_speak_basic(self):
        """Basic speak() call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                output_dir=Path(tmpdir),
                backend="mock",
            )
            engine = VoiceEngine(config)
            
            result = engine.speak("Hello world!")
            
            assert result.audio_path.exists()
            assert result.duration_seconds > 0
    
    def test_speak_with_voice(self):
        """speak() with explicit voice."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(output_dir=Path(tmpdir), backend="mock")
            engine = VoiceEngine(config)
            
            result = engine.speak("Hello!", voice="bm_george")
            
            assert result.voice_used == "bm_george"
    
    def test_speak_with_preset(self):
        """speak() with preset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(output_dir=Path(tmpdir), backend="mock")
            engine = VoiceEngine(config)
            
            result = engine.speak("Hello!", preset="narrator")
            
            # Narrator uses bm_george
            assert result.voice_used == "bm_george"
    
    def test_speak_with_emotion(self):
        """speak() with emotion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(output_dir=Path(tmpdir), backend="mock")
            engine = VoiceEngine(config)
            
            result = engine.speak("I'm excited!", emotion="excited")
            
            assert result.audio_path.exists()
    
    def test_speak_returns_graph(self):
        """SpeechResult includes the compiled graph."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(output_dir=Path(tmpdir), backend="mock")
            engine = VoiceEngine(config)
            
            result = engine.speak("Hello!")
            
            assert result.graph is not None
            assert result.graph.tokens


class TestArchitectureInvariants:
    """Test that architecture invariants are maintained."""
    
    def test_engine_does_not_import_compiler(self):
        """Engine module must not import from compiler."""
        import voice_soundboard.engine.base as base_module
        import voice_soundboard.engine.backends.mock as mock_module
        
        # Check that compiler is not in the module's namespace
        base_source = open(base_module.__file__).read()
        mock_source = open(mock_module.__file__).read()
        
        assert "from voice_soundboard.compiler" not in base_source
        assert "import voice_soundboard.compiler" not in base_source
        assert "from voice_soundboard.compiler" not in mock_source
        assert "import voice_soundboard.compiler" not in mock_source
    
    def test_graph_is_pure_data(self):
        """ControlGraph should be pure data, no methods that call engine."""
        from voice_soundboard.graph import ControlGraph
        
        # ControlGraph should not have any synthesis methods
        assert not hasattr(ControlGraph, "synthesize")
        assert not hasattr(ControlGraph, "speak")
        assert not hasattr(ControlGraph, "generate")
