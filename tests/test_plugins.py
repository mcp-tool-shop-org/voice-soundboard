"""
Tests for v2.3 plugins module.
"""

import pytest
from unittest.mock import Mock, MagicMock
import numpy as np

from voice_soundboard.plugins import (
    Plugin,
    PluginMeta,
    plugin,
    BackendPlugin,
    CompilerPlugin,
    AudioPlugin,
    PluginRegistry,
    HookManager,
    HookType,
)


class TestPluginBase:
    """Tests for Plugin base class."""
    
    def test_plugin_metadata(self):
        @plugin(
            name="test-plugin",
            version="1.0.0",
            author="Test Author",
            description="A test plugin",
        )
        class TestPlugin(Plugin):
            pass
        
        p = TestPlugin()
        assert p.meta.name == "test-plugin"
        assert p.meta.version == "1.0.0"
        assert p.meta.author == "Test Author"
        
    def test_plugin_lifecycle(self):
        class LifecyclePlugin(Plugin):
            def __init__(self):
                super().__init__()
                self.initialized = False
                self.cleaned_up = False
                
            def on_load(self):
                self.initialized = True
                
            def on_unload(self):
                self.cleaned_up = True
        
        p = LifecyclePlugin()
        p.on_load()
        assert p.initialized
        
        p.on_unload()
        assert p.cleaned_up


class TestBackendPlugin:
    """Tests for BackendPlugin."""
    
    def test_backend_plugin_synthesize(self):
        class MockBackendPlugin(BackendPlugin):
            def synthesize(self, graph):
                return np.zeros(1000, dtype=np.int16)
                
            def get_voices(self):
                return ["voice1", "voice2"]
        
        plugin = MockBackendPlugin()
        
        # Test synthesis
        audio = plugin.synthesize(Mock())
        assert isinstance(audio, np.ndarray)
        assert len(audio) == 1000
        
        # Test voice listing
        voices = plugin.get_voices()
        assert len(voices) == 2


class TestCompilerPlugin:
    """Tests for CompilerPlugin."""
    
    def test_compiler_plugin_transform(self):
        class MockCompilerPlugin(CompilerPlugin):
            def transform(self, text, context=None):
                return text.upper()
        
        plugin = MockCompilerPlugin()
        result = plugin.transform("hello world")
        assert result == "HELLO WORLD"


class TestAudioPlugin:
    """Tests for AudioPlugin."""
    
    def test_audio_plugin_process(self):
        class GainPlugin(AudioPlugin):
            def __init__(self, gain: float = 2.0):
                super().__init__()
                self.gain = gain
                
            def process(self, audio, sample_rate=22050):
                return (audio * self.gain).astype(audio.dtype)
        
        plugin = GainPlugin(gain=2.0)
        
        input_audio = np.array([100, 200, 300], dtype=np.int16)
        output = plugin.process(input_audio)
        
        assert list(output) == [200, 400, 600]


class TestPluginRegistry:
    """Tests for PluginRegistry."""
    
    def test_register_plugin(self):
        registry = PluginRegistry()
        
        @plugin(name="test-plugin", version="1.0.0")
        class TestPlugin(Plugin):
            pass
        
        registry.register(TestPlugin)
        
        assert "test-plugin" in registry.plugins
        assert registry.get("test-plugin") is not None
        
    def test_unregister_plugin(self):
        registry = PluginRegistry()
        
        @plugin(name="removable", version="1.0.0")
        class RemovablePlugin(Plugin):
            pass
        
        registry.register(RemovablePlugin)
        assert "removable" in registry.plugins
        
        registry.unregister("removable")
        assert "removable" not in registry.plugins
        
    def test_list_plugins_by_type(self):
        registry = PluginRegistry()
        
        @plugin(name="backend1", version="1.0.0")
        class Backend1(BackendPlugin):
            def synthesize(self, graph):
                return np.zeros(100)
            def get_voices(self):
                return []
        
        @plugin(name="audio1", version="1.0.0")
        class Audio1(AudioPlugin):
            def process(self, audio, **kwargs):
                return audio
        
        registry.register(Backend1)
        registry.register(Audio1)
        
        backends = registry.list_by_type(BackendPlugin)
        assert len(backends) == 1
        assert backends[0].meta.name == "backend1"
        
        audio_plugins = registry.list_by_type(AudioPlugin)
        assert len(audio_plugins) == 1
        assert audio_plugins[0].meta.name == "audio1"


class TestHookManager:
    """Tests for HookManager."""
    
    def test_register_hook(self):
        manager = HookManager()
        
        calls = []
        def my_hook(data):
            calls.append(data)
        
        manager.register(HookType.PRE_SYNTHESIS, my_hook)
        manager.trigger(HookType.PRE_SYNTHESIS, {"text": "hello"})
        
        assert len(calls) == 1
        assert calls[0]["text"] == "hello"
        
    def test_multiple_hooks(self):
        manager = HookManager()
        
        results = []
        
        def hook1(data):
            results.append(f"hook1: {data}")
            
        def hook2(data):
            results.append(f"hook2: {data}")
        
        manager.register(HookType.POST_SYNTHESIS, hook1)
        manager.register(HookType.POST_SYNTHESIS, hook2)
        manager.trigger(HookType.POST_SYNTHESIS, "test")
        
        assert len(results) == 2
        assert "hook1: test" in results
        assert "hook2: test" in results
        
    def test_unregister_hook(self):
        manager = HookManager()
        
        calls = []
        def my_hook(data):
            calls.append(data)
        
        manager.register(HookType.PRE_SYNTHESIS, my_hook)
        manager.unregister(HookType.PRE_SYNTHESIS, my_hook)
        manager.trigger(HookType.PRE_SYNTHESIS, "test")
        
        assert len(calls) == 0


class TestPluginDependencies:
    """Tests for plugin dependency handling."""
    
    def test_plugin_with_dependencies(self):
        registry = PluginRegistry()
        
        @plugin(name="base", version="1.0.0")
        class BasePlugin(Plugin):
            pass
        
        @plugin(name="dependent", version="1.0.0", dependencies=["base>=1.0.0"])
        class DependentPlugin(Plugin):
            pass
        
        registry.register(BasePlugin)
        registry.register(DependentPlugin)
        
        # Both should be registered
        assert "base" in registry.plugins
        assert "dependent" in registry.plugins
