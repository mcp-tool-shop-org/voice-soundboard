"""
Hook system for plugin event handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any, TypeVar, ParamSpec, Union
from functools import wraps
from enum import Enum, auto
import threading

import numpy as np

from voice_soundboard.graph import ControlGraph


class HookType(Enum):
    """Types of hooks in the plugin system."""
    
    PRE_SYNTHESIS = auto()
    """Called before synthesis starts."""
    
    POST_SYNTHESIS = auto()
    """Called after synthesis completes."""
    
    ON_GRAPH = auto()
    """Called when a graph is produced."""
    
    ON_AUDIO = auto()
    """Called when audio is produced."""
    
    ON_ERROR = auto()
    """Called when an error occurs."""
    
    ON_STREAM_CHUNK = auto()
    """Called for each streaming chunk."""
    
    ON_INTERRUPT = auto()
    """Called when synthesis is interrupted."""


P = ParamSpec("P")
T = TypeVar("T")


@dataclass
class Hook:
    """Represents a registered hook callback.
    
    Attributes:
        event: Event name this hook responds to.
        callback: Function to call when event fires.
        priority: Execution priority (lower = earlier).
        plugin_name: Name of the plugin that registered this hook.
    """
    
    event: str
    callback: Callable[..., Any]
    priority: int = 100
    plugin_name: str = ""
    
    def __call__(self, *args, **kwargs) -> Any:
        """Execute the hook callback."""
        return self.callback(*args, **kwargs)


class HookManager:
    """Manages hook registration and execution.
    
    Provides a clean interface for plugins to register
    callbacks for various events in the synthesis pipeline.
    
    Events:
        on_compile_start: Before compilation starts
        on_compile_end: After compilation completes
        on_graph: When a graph is produced
        on_synth_start: Before synthesis starts
        on_synth_end: After synthesis completes
        on_audio: When audio is produced
        on_error: When an error occurs
        on_stream_chunk: When a streaming chunk is produced
    
    Example:
        manager = HookManager()
        
        @manager.on_graph
        def log_graph(graph):
            print(f"Graph has {len(graph.tokens)} tokens")
        
        # Or register directly
        manager.register("on_audio", my_callback)
    """
    
    # Standard events
    EVENTS = [
        "on_compile_start",
        "on_compile_end",
        "on_graph",
        "on_synth_start",
        "on_synth_end",
        "on_audio",
        "on_error",
        "on_stream_chunk",
        "on_session_start",
        "on_session_end",
        "on_interrupt",
    ]
    
    def __init__(self):
        self._hooks: dict[str, list[Hook]] = {event: [] for event in self.EVENTS}
        # Also support HookType enum
        self._typed_hooks: dict[HookType, list[Callable]] = {ht: [] for ht in HookType}
        self._lock = threading.Lock()
    
    def register(
        self,
        event: Union[str, HookType],
        callback: Callable[..., Any],
        priority: int = 100,
        plugin_name: str = "",
    ) -> Hook:
        """Register a hook callback.
        
        Args:
            event: Event name (string) or HookType enum.
            callback: Function to call.
            priority: Execution priority.
            plugin_name: Plugin that owns this hook.
        
        Returns:
            The created Hook object.
        
        Raises:
            ValueError: If event is unknown.
        """
        # Handle HookType enum
        if isinstance(event, HookType):
            with self._lock:
                self._typed_hooks[event].append(callback)
            return Hook(
                event=event.name,
                callback=callback,
                priority=priority,
                plugin_name=plugin_name,
            )
        
        if event not in self._hooks:
            raise ValueError(f"Unknown event: {event}")
        
        hook = Hook(
            event=event,
            callback=callback,
            priority=priority,
            plugin_name=plugin_name,
        )
        
        with self._lock:
            self._hooks[event].append(hook)
            self._hooks[event].sort(key=lambda h: h.priority)
        
        return hook
    
    def unregister(
        self,
        event_or_hook: Union[str, HookType, Hook],
        callback: Callable[..., Any] | None = None,
    ) -> bool:
        """Unregister a hook.
        
        Args:
            event_or_hook: Hook to unregister, or HookType/event name with callback.
            callback: Callback to unregister (if event_or_hook is HookType or str).
        
        Returns:
            True if hook was found and removed.
        """
        # Handle HookType enum with callback
        if isinstance(event_or_hook, HookType):
            with self._lock:
                if callback in self._typed_hooks.get(event_or_hook, []):
                    self._typed_hooks[event_or_hook].remove(callback)
                    return True
            return False
        
        # Handle Hook object
        if isinstance(event_or_hook, Hook):
            with self._lock:
                if event_or_hook in self._hooks.get(event_or_hook.event, []):
                    self._hooks[event_or_hook.event].remove(event_or_hook)
                    return True
            return False
        
        # Handle string event with callback
        if callback is not None:
            with self._lock:
                for hook in self._hooks.get(event_or_hook, []):
                    if hook.callback == callback:
                        self._hooks[event_or_hook].remove(hook)
                        return True
        return False
    
    def trigger(self, event: HookType, data: Any = None) -> list[Any]:
        """Trigger a hook type with data.
        
        Args:
            event: HookType to trigger.
            data: Data to pass to callbacks.
        
        Returns:
            List of return values from callbacks.
        """
        results = []
        with self._lock:
            callbacks = list(self._typed_hooks.get(event, []))
        
        for callback in callbacks:
            try:
                result = callback(data)
                results.append(result)
            except Exception:
                pass  # Ignore errors in hooks
        
        return results
    
    def _unregister_hook_object(self, hook: Hook) -> bool:
        """Internal: Unregister a Hook object.
        
        Args:
            hook: Hook to unregister.
        
        Returns:
            True if hook was found and removed.
        """
        with self._lock:
            if hook in self._hooks.get(hook.event, []):
                self._hooks[hook.event].remove(hook)
                return True
        return False
    
    def unregister_plugin(self, plugin_name: str) -> int:
        """Unregister all hooks from a plugin.
        
        Args:
            plugin_name: Plugin name.
        
        Returns:
            Number of hooks removed.
        """
        count = 0
        with self._lock:
            for event in self._hooks:
                original_len = len(self._hooks[event])
                self._hooks[event] = [
                    h for h in self._hooks[event]
                    if h.plugin_name != plugin_name
                ]
                count += original_len - len(self._hooks[event])
        return count
    
    def fire(self, event: str, *args, **kwargs) -> list[Any]:
        """Fire an event and call all registered hooks.
        
        Args:
            event: Event name.
            *args, **kwargs: Arguments to pass to hooks.
        
        Returns:
            List of return values from hooks.
        """
        results = []
        
        for hook in self._hooks.get(event, []):
            try:
                result = hook(*args, **kwargs)
                results.append(result)
            except Exception as e:
                # Fire error hook but don't recurse
                if event != "on_error":
                    self.fire("on_error", error=e, source_event=event)
        
        return results
    
    def fire_transform(
        self,
        event: str,
        value: T,
        *args,
        **kwargs,
    ) -> T:
        """Fire an event where hooks can transform a value.
        
        Each hook receives the value and returns a transformed version.
        The final transformed value is returned.
        
        Args:
            event: Event name.
            value: Initial value to transform.
            *args, **kwargs: Additional arguments.
        
        Returns:
            Transformed value.
        """
        for hook in self._hooks.get(event, []):
            try:
                result = hook(value, *args, **kwargs)
                if result is not None:
                    value = result
            except Exception as e:
                if event != "on_error":
                    self.fire("on_error", error=e, source_event=event)
        
        return value
    
    # Decorator methods for common events
    
    def on_graph(
        self,
        priority: int = 100,
    ) -> Callable[[Callable[[ControlGraph], Any]], Callable[[ControlGraph], Any]]:
        """Decorator to register an on_graph hook.
        
        Example:
            @hooks.on_graph()
            def log_graph(graph):
                print(f"Tokens: {len(graph.tokens)}")
        """
        def decorator(func: Callable[[ControlGraph], Any]) -> Callable[[ControlGraph], Any]:
            self.register("on_graph", func, priority)
            return func
        return decorator
    
    def on_audio(
        self,
        priority: int = 100,
    ) -> Callable[[Callable[[np.ndarray, int], Any]], Callable[[np.ndarray, int], Any]]:
        """Decorator to register an on_audio hook.
        
        Example:
            @hooks.on_audio()
            def log_audio(audio, sample_rate):
                print(f"Duration: {len(audio) / sample_rate:.2f}s")
        """
        def decorator(func: Callable[[np.ndarray, int], Any]) -> Callable[[np.ndarray, int], Any]:
            self.register("on_audio", func, priority)
            return func
        return decorator
    
    def on_error(
        self,
        priority: int = 100,
    ) -> Callable[[Callable[[Exception], Any]], Callable[[Exception], Any]]:
        """Decorator to register an on_error hook.
        
        Example:
            @hooks.on_error()
            def log_error(error, source_event=None):
                print(f"Error in {source_event}: {error}")
        """
        def decorator(func: Callable[[Exception], Any]) -> Callable[[Exception], Any]:
            self.register("on_error", func, priority)
            return func
        return decorator


# Module-level hook decorators for convenience
_default_manager: HookManager | None = None


def _get_default_manager() -> HookManager:
    """Get the default hook manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = HookManager()
    return _default_manager


def on_graph(
    func: Callable[[ControlGraph], Any] | None = None,
    priority: int = 100,
) -> Callable:
    """Register an on_graph hook.
    
    Can be used as decorator with or without arguments.
    
    Example:
        @on_graph
        def my_hook(graph):
            ...
        
        @on_graph(priority=50)
        def early_hook(graph):
            ...
    """
    manager = _get_default_manager()
    
    if func is not None:
        # Called without arguments
        manager.register("on_graph", func, priority)
        return func
    
    # Called with arguments
    def decorator(f: Callable[[ControlGraph], Any]) -> Callable[[ControlGraph], Any]:
        manager.register("on_graph", f, priority)
        return f
    return decorator


def on_audio(
    func: Callable[[np.ndarray, int], Any] | None = None,
    priority: int = 100,
) -> Callable:
    """Register an on_audio hook."""
    manager = _get_default_manager()
    
    if func is not None:
        manager.register("on_audio", func, priority)
        return func
    
    def decorator(f: Callable[[np.ndarray, int], Any]) -> Callable[[np.ndarray, int], Any]:
        manager.register("on_audio", f, priority)
        return f
    return decorator


def on_error(
    func: Callable[[Exception], Any] | None = None,
    priority: int = 100,
) -> Callable:
    """Register an on_error hook."""
    manager = _get_default_manager()
    
    if func is not None:
        manager.register("on_error", func, priority)
        return func
    
    def decorator(f: Callable[[Exception], Any]) -> Callable[[Exception], Any]:
        manager.register("on_error", f, priority)
        return f
    return decorator
