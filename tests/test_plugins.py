"""
Tests for v2.4 plugin system.
"""

import pytest
from unittest.mock import Mock

from voice_soundboard.plugins import (
    Plugin, 
    PluginRegistry, 
    plugin,
)


class TestPluginRegistry:
    """Tests for PluginRegistry."""
    
    def test_register_plugin(self):
        registry = PluginRegistry()
        
        @plugin
        class MyPlugin(Plugin):
            name = "p1"
            version = "1.0.0"
            def on_load(self, registry): pass
        
        # Must register INSTANCE
        registry.register(MyPlugin())
        assert "p1" in registry.plugins
        assert registry.plugins["p1"].version == "1.0.0"
        
    def test_duplicate_registration_raises(self):
        registry = PluginRegistry()
        
        @plugin
        class MyPlugin(Plugin):
            name = "p1"
            version = "1.0.0"
            def on_load(self, registry): pass
            
        registry.register(MyPlugin())
        
        with pytest.raises(ValueError):
            registry.register(MyPlugin())
            
    def test_get_plugin(self):
        registry = PluginRegistry()
        
        @plugin
        class MyPlugin(Plugin):
            name = "p1"
            version = "1.0.0"
            def on_load(self, registry): pass
            
        registry.register(MyPlugin())
        assert registry.get("p1") is not None
        assert registry.get("nonexistent") is None


class TestPluginDependencies:
    """Tests for plugin dependency handling."""
    
    def test_plugin_with_dependencies(self):
        registry = PluginRegistry()
        
        @plugin
        class BasePlugin(Plugin):
            name = "base"
            version = "1.0.0"
            def on_load(self, registry): pass
            
        @plugin
        class DependentPlugin(Plugin):
            name = "dependent"
            version = "1.0.0"
            def on_load(self, registry): pass
            
            def __init__(self, config=None):
                super().__init__(config)
                # Manually set dependency metadata as Plugin init doesn't
                self._meta.dependencies = ["base"]

        registry.register(BasePlugin())
        registry.register(DependentPlugin())
        
        assert "dependent" in registry.plugins

    def test_missing_dependency_raises(self):
        registry = PluginRegistry()
        
        @plugin
        class DependentPlugin(Plugin):
            name = "dependent"
            version = "1.0.0"
            def on_load(self, registry): pass
            
            def __init__(self, config=None):
                super().__init__(config)
                self._meta.dependencies = ["base"]

        with pytest.raises(ValueError):
            registry.register(DependentPlugin()) 

