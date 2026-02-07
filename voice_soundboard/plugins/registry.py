"""
Plugin registry for discovering and managing plugins.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, Iterator
import threading

from voice_soundboard.plugins.base import Plugin, PluginMeta, PluginType


class PluginRegistry:
    """Central registry for Voice Soundboard plugins.
    
    Manages plugin lifecycle:
    - Discovery
    - Registration
    - Loading/unloading
    - Hook management
    
    Example:
        registry = PluginRegistry()
        
        # Register a plugin
        registry.register(MyPlugin())
        
        # Get a plugin
        plugin = registry.get("my_plugin")
        
        # Discover plugins from a directory
        registry.discover("./plugins")
    """
    
    _instance: "PluginRegistry | None" = None
    _lock = threading.Lock()
    
    def __init__(self):
        self._plugins: dict[str, Plugin] = {}
        self._backends: dict[str, Any] = {}
        self._compiler_plugins: list[Plugin] = []
        self._audio_plugins: list[Plugin] = []
        self._hooks: dict[str, list[Callable]] = {}
        self._load_order: list[str] = []
    
    @classmethod
    def instance(cls) -> "PluginRegistry":
        """Get the singleton registry instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    @property
    def plugins(self) -> dict[str, Plugin]:
        """All registered plugins."""
        return self._plugins.copy()
    
    @property
    def backends(self) -> dict[str, Any]:
        """Registered backend plugins."""
        return self._backends.copy()
    
    def register(self, plugin: Plugin) -> None:
        """Register a plugin.
        
        Args:
            plugin: Plugin instance to register.
        
        Raises:
            ValueError: If plugin with same name already exists.
        """
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.name}' already registered")
        
        # Validate dependencies
        for dep in plugin.meta.dependencies:
            if dep not in self._plugins:
                raise ValueError(
                    f"Plugin '{plugin.name}' requires '{dep}' which is not loaded"
                )
        
        # Validate config
        errors = plugin.validate_config()
        if errors:
            raise ValueError(f"Plugin config invalid: {errors}")
        
        self._plugins[plugin.name] = plugin
        self._load_order.append(plugin.name)
        
        # Call on_load
        plugin.on_load(self)
    
    def unregister(self, name: str) -> Plugin | None:
        """Unregister a plugin.
        
        Args:
            name: Plugin name to unregister.
        
        Returns:
            The unregistered plugin, or None if not found.
        """
        plugin = self._plugins.pop(name, None)
        
        if plugin:
            plugin.on_unload()
            self._load_order.remove(name)
            
            # Remove from type-specific registries
            if name in self._backends:
                del self._backends[name]
            self._compiler_plugins = [p for p in self._compiler_plugins if p.name != name]
            self._audio_plugins = [p for p in self._audio_plugins if p.name != name]
        
        return plugin
    
    def get(self, name: str) -> Plugin | None:
        """Get a plugin by name.
        
        Args:
            name: Plugin name.
        
        Returns:
            Plugin instance or None.
        """
        return self._plugins.get(name)
    
    def get_backend(self, name: str) -> Any | None:
        """Get a backend plugin by name.
        
        Args:
            name: Backend name.
        
        Returns:
            Backend instance or None.
        """
        return self._backends.get(name)
    
    def register_backend(self, name: str, backend: Any) -> None:
        """Register a TTS backend.
        
        Args:
            name: Backend identifier.
            backend: Backend instance.
        """
        self._backends[name] = backend
    
    def register_compiler_plugin(self, plugin: Plugin) -> None:
        """Register a compiler plugin.
        
        Args:
            plugin: Compiler plugin instance.
        """
        self._compiler_plugins.append(plugin)
        # Sort by priority
        self._compiler_plugins.sort(key=lambda p: getattr(p, "priority", 100))
    
    def register_audio_plugin(self, plugin: Plugin) -> None:
        """Register an audio plugin.
        
        Args:
            plugin: Audio plugin instance.
        """
        self._audio_plugins.append(plugin)
        # Sort by priority
        self._audio_plugins.sort(key=lambda p: getattr(p, "priority", 100))
    
    def get_compiler_plugins(self) -> list[Plugin]:
        """Get all compiler plugins in priority order."""
        return self._compiler_plugins.copy()
    
    def get_audio_plugins(self) -> list[Plugin]:
        """Get all audio plugins in priority order."""
        return self._audio_plugins.copy()
    
    def register_hook(self, event: str, callback: Callable) -> None:
        """Register a hook callback.
        
        Args:
            event: Event name (e.g., "on_graph", "on_audio").
            callback: Function to call when event fires.
        """
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)
    
    def fire_hook(self, event: str, *args, **kwargs) -> None:
        """Fire a hook event.
        
        Args:
            event: Event name.
            *args, **kwargs: Arguments to pass to callbacks.
        """
        for callback in self._hooks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                # Log but don't fail
                print(f"Hook {event} callback error: {e}")
    
    def discover(self, path: str | Path) -> list[str]:
        """Discover and load plugins from a directory.
        
        Plugins are Python files or packages with a class
        decorated with @plugin.
        
        Args:
            path: Directory path to search.
        
        Returns:
            List of discovered plugin names.
        """
        path = Path(path)
        discovered = []
        
        if not path.exists():
            return discovered
        
        for item in path.iterdir():
            if item.is_file() and item.suffix == ".py" and not item.name.startswith("_"):
                name = item.stem
                try:
                    spec = importlib.util.spec_from_file_location(name, item)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[name] = module
                        spec.loader.exec_module(module)
                        
                        # Find plugin classes
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, Plugin)
                                and attr is not Plugin
                                and hasattr(attr, "_is_voice_soundboard_plugin")
                            ):
                                plugin = attr()
                                if plugin.name not in self._plugins:
                                    self.register(plugin)
                                    discovered.append(plugin.name)
                except Exception as e:
                    print(f"Error loading plugin from {item}: {e}")
            
            elif item.is_dir() and (item / "__init__.py").exists():
                # Package plugin
                name = item.name
                try:
                    module = importlib.import_module(name)
                    
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, Plugin)
                            and attr is not Plugin
                            and hasattr(attr, "_is_voice_soundboard_plugin")
                        ):
                            plugin = attr()
                            if plugin.name not in self._plugins:
                                self.register(plugin)
                                discovered.append(plugin.name)
                except Exception as e:
                    print(f"Error loading plugin from {item}: {e}")
        
        return discovered
    
    def list_plugins(
        self,
        plugin_type: PluginType | None = None,
    ) -> Iterator[PluginMeta]:
        """List all registered plugins.
        
        Args:
            plugin_type: Filter by plugin type.
        
        Yields:
            Plugin metadata objects.
        """
        for plugin in self._plugins.values():
            if plugin_type is None or plugin.plugin_type == plugin_type:
                yield plugin.meta
    
    def clear(self) -> None:
        """Unregister all plugins."""
        for name in list(self._plugins.keys()):
            self.unregister(name)


# Global registry access
_global_registry: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry()
    return _global_registry


def discover_plugins(path: str | Path) -> list[str]:
    """Discover and load plugins from a directory.
    
    Args:
        path: Directory to search.
    
    Returns:
        List of discovered plugin names.
    """
    return get_registry().discover(path)
