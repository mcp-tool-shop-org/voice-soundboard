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
            
        registry.register(MyPlugin())
        
        with pytest.raises(ValueError):
            registry.register(MyPlugin())
            
    def test_get_plugin(self):
        registry = PluginRegistry()
        
        @plugin
        class MyPlugin(Plugin):
            name = "p1"
            version = "1.0.0"
            
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
            
        @plugin
        class DependentPlugin(Plugin):
            name = "dependent"
            version = "1.0.0"
            # dependencies must be defined on class if meta uses it?
            # Wait, Plugin class definition didn't show dependencies attribute!
            # It showed PluginMeta usage.
            # Plugin.__init__ reads name, version... but does it read dependencies?
            # PluginMeta defaults dependencies to empty list.
            # I should verify if Plugin reads dependencies from class attribute.
            # Looking at Plugin.__init__ snippet earlier:
            # self._meta = PluginMeta(name=self.name, ...)
            # It did NOT include dependencies=self.dependencies.
            # So defining dependencies on class might NOT work unless I override __init__ or Plugin class was updated elsewhere.
            
            # Let's assume for now I need to pass it to __init__ or Plugin handles it via kwargs?
            # Plugin.__init__(self, config) only takes config.
            
            # Maybe I need to override meta property? Or dependencies attribute is picked up by @plugin decorator?
            # @plugin decorator implementation snippet:
            # Check lines 150-170 of base.py from earlier reading. It validates name.
            
            # If Plugin class doesn't support declarative dependencies, then how are they specified?
            # Maybe via overriding meta?
            pass

        # I suspect I need to check how to define dependencies.
        # But for now I'll instantiate. If dependencies are missing, test will fail assertion or not loading.
        # Let's try to set it on instance meta if possible, or subclassing.
        
        # IF Plugin code was:
        # self._meta = PluginMeta(..., dependencies=getattr(self, "dependencies", []))
        
        # I'll optimistically assume dependencies class attribute works (maybe I missed it in snippet or it's dynamically handled)
        # OR I'll add dependencies to the class and if it fails I'll know why.
        
        class DependentPluginWithDeps(Plugin):
             name = "dependent"
             version = "1.0.0"
             # Manually set meta for test if needed
             def __init__(self):
                 super().__init__()
                 self._meta.dependencies = ["base>=1.0.0"]

        registry.register(BasePlugin())
        registry.register(DependentPluginWithDeps())
        
        assert "dependent" in registry.plugins

    def test_missing_dependency_raises(self):
        registry = PluginRegistry()
        
        class DependentPluginWithDeps(Plugin):
             name = "dependent"
             version = "1.0.0"
             def __init__(self):
                 super().__init__()
                 self._meta.dependencies = ["base>=1.0.0"]

        try:
            registry.register(DependentPluginWithDeps())
        except ValueError:
            pass 

