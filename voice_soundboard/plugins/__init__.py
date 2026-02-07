"""
Plugin Architecture for Voice Soundboard v2.3.

Allows extending Voice Soundboard without forking the core:
- Backend plugins (custom TTS engines)
- Compiler plugins (custom markup, transforms)
- Audio plugins (processing, normalization)
- Runtime plugins (scheduling, buffering)

Example:
    from voice_soundboard.plugins import plugin, BackendPlugin
    
    @plugin
    class MyCloudTTSPlugin(BackendPlugin):
        name = "my_cloud_tts"
        
        def synthesize(self, graph):
            ...
    
    # Register and use
    engine.register_plugin(MyCloudTTSPlugin())
    engine.speak("Hello!", backend="my_cloud_tts")
"""

from voice_soundboard.plugins.base import (
    Plugin,
    PluginMeta,
    plugin,
)
from voice_soundboard.plugins.backend import BackendPlugin
from voice_soundboard.plugins.compiler import CompilerPlugin
from voice_soundboard.plugins.audio import AudioPlugin
from voice_soundboard.plugins.registry import (
    PluginRegistry,
    get_registry,
    discover_plugins,
)
from voice_soundboard.plugins.hooks import (
    Hook,
    HookManager,
    HookType,
    on_graph,
    on_audio,
    on_error,
)

__all__ = [
    # Base
    "Plugin",
    "PluginMeta",
    "plugin",
    # Plugin types
    "BackendPlugin",
    "CompilerPlugin", 
    "AudioPlugin",
    # Registry
    "PluginRegistry",
    "get_registry",
    "discover_plugins",
    # Hooks
    "Hook",
    "HookManager",
    "HookType",
    "on_graph",
    "on_audio",
    "on_error",
]
