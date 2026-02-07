"""
Base plugin classes and decorators.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar, Type, TYPE_CHECKING
from enum import Enum
import time

if TYPE_CHECKING:
    from voice_soundboard.plugins.registry import PluginRegistry


class PluginType(Enum):
    """Types of plugins supported."""
    
    BACKEND = "backend"
    COMPILER = "compiler"
    AUDIO = "audio"
    RUNTIME = "runtime"


@dataclass
class PluginMeta:
    """Metadata about a plugin.
    
    Attributes:
        name: Unique identifier for the plugin.
        version: Plugin version string.
        description: Human-readable description.
        author: Plugin author.
        plugin_type: Type of plugin (backend, compiler, etc.).
        dependencies: List of required plugin names.
        config_schema: JSON schema for plugin configuration.
    """
    
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    plugin_type: PluginType = PluginType.RUNTIME
    dependencies: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] | None = None
    
    # Runtime metadata
    loaded_at: float = field(default_factory=time.time)
    enabled: bool = True


class Plugin(ABC):
    """Base class for all Voice Soundboard plugins.
    
    Plugins extend functionality without modifying core code.
    Each plugin must implement at minimum:
    - name: Unique identifier
    - on_load(): Called when plugin is loaded
    - on_unload(): Called when plugin is unloaded
    
    Example:
        class MyPlugin(Plugin):
            name = "my_plugin"
            version = "1.0.0"
            
            def on_load(self, registry):
                print("Plugin loaded!")
            
            def on_unload(self):
                print("Plugin unloaded!")
    """
    
    # Required class attributes
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    plugin_type: PluginType = PluginType.RUNTIME
    
    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize plugin with optional configuration.
        
        Args:
            config: Plugin-specific configuration dictionary.
        """
        self._config = config or {}
        self._meta = PluginMeta(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            plugin_type=self.plugin_type,
        )
    
    @property
    def meta(self) -> PluginMeta:
        """Plugin metadata."""
        return self._meta
    
    @property
    def config(self) -> dict[str, Any]:
        """Plugin configuration."""
        return self._config
    
    def configure(self, **kwargs: Any) -> "Plugin":
        """Update plugin configuration.
        
        Args:
            **kwargs: Configuration key-value pairs.
        
        Returns:
            Self for chaining.
        """
        self._config.update(kwargs)
        return self
    
    @abstractmethod
    def on_load(self, registry: "PluginRegistry") -> None:
        """Called when the plugin is loaded.
        
        Use this to register hooks, initialize resources, etc.
        
        Args:
            registry: The plugin registry for registering hooks.
        """
        ...
    
    def on_unload(self) -> None:
        """Called when the plugin is unloaded.
        
        Override to clean up resources.
        """
        pass
    
    def validate_config(self) -> list[str]:
        """Validate plugin configuration.
        
        Returns:
            List of validation error messages (empty if valid).
        """
        return []
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self.name}' v{self.version}>"


# Type variable for plugin decorator
P = TypeVar("P", bound=Plugin)


def plugin(cls: Type[P]) -> Type[P]:
    """Decorator to mark a class as a Voice Soundboard plugin.
    
    This decorator:
    - Validates the plugin class has required attributes
    - Registers the plugin with the global registry
    - Adds convenience methods
    
    Example:
        @plugin
        class MyPlugin(Plugin):
            name = "my_plugin"
            ...
    """
    # Validate required attributes
    if not hasattr(cls, "name") or not cls.name:
        raise ValueError(f"Plugin {cls.__name__} must define 'name' attribute")
    
    # Mark as plugin
    cls._is_voice_soundboard_plugin = True
    
    # Add convenience class method
    original_init = cls.__init__
    
    def new_init(self, config=None):
        original_init(self, config)
        # Auto-register with global registry if available
        try:
            from voice_soundboard.plugins.registry import get_registry
            registry = get_registry()
            if registry and self.name not in registry._plugins:
                registry.register(self)
        except ImportError:
            pass
    
    cls.__init__ = new_init
    
    return cls
