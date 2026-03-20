"""
Tests for v2.4 plugin system.
"""

import pytest

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


class TestPluginLifecycle:
    """Tests for plugin load, unload, enable, disable."""

    def test_on_load_called_on_register(self):
        registry = PluginRegistry()
        loaded = []

        @plugin
        class TrackingPlugin(Plugin):
            name = "tracker"
            version = "1.0.0"
            def on_load(self, registry):
                loaded.append("loaded")

        # The @plugin decorator auto-registers with the global registry on __init__,
        # so on_load may be called once there. We then register with our local registry.
        loaded.clear()
        registry.register(TrackingPlugin())
        assert "loaded" in loaded

    def test_on_unload_called_on_unregister(self):
        registry = PluginRegistry()
        unloaded = []

        @plugin
        class TrackingPlugin(Plugin):
            name = "tracker"
            version = "1.0.0"
            def on_load(self, registry): pass
            def on_unload(self):
                unloaded.append("unloaded")

        registry.register(TrackingPlugin())
        result = registry.unregister("tracker")
        assert result is not None
        assert unloaded == ["unloaded"]

    def test_unregister_nonexistent_returns_none(self):
        registry = PluginRegistry()
        result = registry.unregister("nonexistent")
        assert result is None

    def test_unregister_removes_from_plugins(self):
        registry = PluginRegistry()

        @plugin
        class MyPlugin(Plugin):
            name = "p1"
            version = "1.0.0"
            def on_load(self, registry): pass

        registry.register(MyPlugin())
        assert "p1" in registry.plugins
        registry.unregister("p1")
        assert "p1" not in registry.plugins

    def test_clear_unregisters_all(self):
        registry = PluginRegistry()
        unloaded = []

        @plugin
        class PluginA(Plugin):
            name = "a"
            version = "1.0.0"
            def on_load(self, registry): pass
            def on_unload(self):
                unloaded.append("a")

        @plugin
        class PluginB(Plugin):
            name = "b"
            version = "1.0.0"
            def on_load(self, registry): pass
            def on_unload(self):
                unloaded.append("b")

        registry.register(PluginA())
        registry.register(PluginB())
        assert len(registry.plugins) == 2
        registry.clear()
        assert len(registry.plugins) == 0
        assert set(unloaded) == {"a", "b"}

    def test_plugin_meta_populated(self):
        registry = PluginRegistry()

        @plugin
        class MetaPlugin(Plugin):
            name = "meta_test"
            version = "2.0.0"
            description = "A test plugin"
            author = "tester"
            def on_load(self, registry): pass

        p = MetaPlugin()
        registry.register(p)
        assert p.meta.name == "meta_test"
        assert p.meta.version == "2.0.0"
        assert p.meta.description == "A test plugin"
        assert p.meta.author == "tester"
        assert p.meta.enabled is True

    def test_plugin_configure_updates_config(self):
        @plugin
        class ConfigPlugin(Plugin):
            name = "cfg"
            version = "1.0.0"
            def on_load(self, registry): pass

        p = ConfigPlugin(config={"key": "value"})
        assert p.config["key"] == "value"
        p.configure(key2="value2")
        assert p.config["key2"] == "value2"
        # configure returns self for chaining
        result = p.configure(a=1)
        assert result is p

    def test_plugin_repr(self):
        @plugin
        class ReprPlugin(Plugin):
            name = "repr_test"
            version = "3.0.0"
            def on_load(self, registry): pass

        p = ReprPlugin()
        assert "repr_test" in repr(p)
        assert "3.0.0" in repr(p)

    def test_validate_config_errors_prevent_registration(self):
        registry = PluginRegistry()

        @plugin
        class BadConfigPlugin(Plugin):
            name = "bad_config"
            version = "1.0.0"
            def on_load(self, registry): pass
            def validate_config(self):
                return ["missing required field: api_key"]

        with pytest.raises(ValueError, match="config invalid"):
            registry.register(BadConfigPlugin())


class TestPluginDecorator:
    """Tests for the @plugin decorator."""

    def test_plugin_without_name_raises(self):
        with pytest.raises(ValueError, match="must define 'name'"):
            @plugin
            class BadPlugin(Plugin):
                name = ""
                def on_load(self, registry): pass

    def test_plugin_sets_marker(self):
        @plugin
        class MarkedPlugin(Plugin):
            name = "marked"
            version = "1.0.0"
            def on_load(self, registry): pass

        assert hasattr(MarkedPlugin, "_is_voice_soundboard_plugin")
        assert MarkedPlugin._is_voice_soundboard_plugin is True


class TestRegistryListPlugins:
    """Tests for listing and filtering plugins."""

    def test_list_all_plugins(self):

        registry = PluginRegistry()

        @plugin
        class P1(Plugin):
            name = "p1"
            version = "1.0.0"
            def on_load(self, registry): pass

        @plugin
        class P2(Plugin):
            name = "p2"
            version = "2.0.0"
            def on_load(self, registry): pass

        registry.register(P1())
        registry.register(P2())

        metas = list(registry.list_plugins())
        names = {m.name for m in metas}
        assert names == {"p1", "p2"}

    def test_list_plugins_by_type(self):
        from voice_soundboard.plugins.base import PluginType

        registry = PluginRegistry()

        @plugin
        class RuntimePlugin(Plugin):
            name = "rt"
            version = "1.0.0"
            plugin_type = PluginType.RUNTIME
            def on_load(self, registry): pass

        @plugin
        class CompPlugin(Plugin):
            name = "comp"
            version = "1.0.0"
            plugin_type = PluginType.COMPILER
            def on_load(self, registry): pass

        registry.register(RuntimePlugin())
        registry.register(CompPlugin())

        runtime_metas = list(registry.list_plugins(PluginType.RUNTIME))
        assert len(runtime_metas) == 1
        assert runtime_metas[0].name == "rt"

        compiler_metas = list(registry.list_plugins(PluginType.COMPILER))
        assert len(compiler_metas) == 1
        assert compiler_metas[0].name == "comp"

    def test_list_plugins_empty_registry(self):
        registry = PluginRegistry()
        assert list(registry.list_plugins()) == []


class TestRegistryBackends:
    """Tests for backend registration on the registry."""

    def test_register_and_get_backend(self):
        registry = PluginRegistry()
        sentinel = object()
        registry.register_backend("my_backend", sentinel)
        assert registry.get_backend("my_backend") is sentinel
        assert registry.get_backend("nonexistent") is None

    def test_backends_property_returns_copy(self):
        registry = PluginRegistry()
        registry.register_backend("b1", "backend1")
        backends = registry.backends
        backends["b2"] = "injected"
        # Original should not be affected
        assert "b2" not in registry.backends

    def test_unregister_removes_backend(self):
        registry = PluginRegistry()

        @plugin
        class BPlugin(Plugin):
            name = "b_plug"
            version = "1.0.0"
            def on_load(self, reg):
                reg.register_backend("b_plug", self)

        registry.register(BPlugin())
        assert registry.get_backend("b_plug") is not None
        registry.unregister("b_plug")
        assert registry.get_backend("b_plug") is None


class TestRegistryCompilerAndAudio:
    """Tests for compiler and audio plugin sub-registries."""

    def test_register_compiler_plugin(self):
        registry = PluginRegistry()

        @plugin
        class CPlugin(Plugin):
            name = "cp"
            version = "1.0.0"
            priority = 50
            def on_load(self, reg):
                reg.register_compiler_plugin(self)

        registry.register(CPlugin())
        assert len(registry.get_compiler_plugins()) == 1

    def test_register_audio_plugin(self):
        registry = PluginRegistry()

        @plugin
        class APlugin(Plugin):
            name = "ap"
            version = "1.0.0"
            priority = 50
            def on_load(self, reg):
                reg.register_audio_plugin(self)

        registry.register(APlugin())
        assert len(registry.get_audio_plugins()) == 1

    def test_compiler_plugins_sorted_by_priority(self):
        registry = PluginRegistry()

        @plugin
        class LatePlug(Plugin):
            name = "late"
            version = "1.0.0"
            priority = 200
            def on_load(self, reg):
                reg.register_compiler_plugin(self)

        @plugin
        class EarlyPlug(Plugin):
            name = "early"
            version = "1.0.0"
            priority = 10
            def on_load(self, reg):
                reg.register_compiler_plugin(self)

        registry.register(LatePlug())
        registry.register(EarlyPlug())
        plugins = registry.get_compiler_plugins()
        assert plugins[0].name == "early"
        assert plugins[1].name == "late"

    def test_unregister_removes_compiler_and_audio(self):
        registry = PluginRegistry()

        @plugin
        class BothPlugin(Plugin):
            name = "both"
            version = "1.0.0"
            def on_load(self, reg):
                reg.register_compiler_plugin(self)
                reg.register_audio_plugin(self)

        registry.register(BothPlugin())
        assert len(registry.get_compiler_plugins()) == 1
        assert len(registry.get_audio_plugins()) == 1
        registry.unregister("both")
        assert len(registry.get_compiler_plugins()) == 0
        assert len(registry.get_audio_plugins()) == 0


class TestRegistryHooks:
    """Tests for hook registration and firing on the registry."""

    def test_register_and_fire_hook(self):
        registry = PluginRegistry()
        results = []

        def my_hook(value):
            results.append(value)

        registry.register_hook("on_graph", my_hook)
        registry.fire_hook("on_graph", "test_value")
        assert results == ["test_value"]

    def test_fire_hook_with_no_listeners(self):
        registry = PluginRegistry()
        # Should not raise
        registry.fire_hook("on_graph", "nothing")

    def test_hook_error_does_not_propagate(self):
        registry = PluginRegistry()
        called = []

        def bad_hook():
            raise RuntimeError("boom")

        def good_hook():
            called.append(True)

        registry.register_hook("evt", bad_hook)
        registry.register_hook("evt", good_hook)
        # bad_hook raises but good_hook should still run
        registry.fire_hook("evt")
        assert called == [True]


class TestHookManager:
    """Tests for the HookManager from hooks.py."""

    def test_register_string_event(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        hook = mgr.register("on_graph", lambda g: g)
        assert hook.event == "on_graph"

    def test_register_unknown_event_raises(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        with pytest.raises(ValueError, match="Unknown event"):
            mgr.register("nonexistent_event", lambda: None)

    def test_fire_calls_hooks_in_priority_order(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        order = []

        mgr.register("on_graph", lambda: order.append("second"), priority=200)
        mgr.register("on_graph", lambda: order.append("first"), priority=50)

        mgr.fire("on_graph")
        assert order == ["first", "second"]

    def test_fire_returns_results(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        mgr.register("on_audio", lambda: 42)
        mgr.register("on_audio", lambda: "hello")

        results = mgr.fire("on_audio")
        assert results == [42, "hello"]

    def test_fire_transform_chains_value(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        mgr.register("on_graph", lambda v: v + 10, priority=1)
        mgr.register("on_graph", lambda v: v * 2, priority=2)

        result = mgr.fire_transform("on_graph", 5)
        # 5 + 10 = 15, then 15 * 2 = 30
        assert result == 30

    def test_fire_transform_skips_none_returns(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        mgr.register("on_graph", lambda v: None, priority=1)
        mgr.register("on_graph", lambda v: v + 1, priority=2)

        result = mgr.fire_transform("on_graph", 10)
        assert result == 11

    def test_fire_error_in_hook_fires_on_error(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        errors = []

        def bad_hook():
            raise RuntimeError("hook failed")

        def error_catcher(error=None, source_event=None):
            errors.append((str(error), source_event))

        mgr.register("on_graph", bad_hook)
        mgr.register("on_error", error_catcher)
        mgr.fire("on_graph")
        assert len(errors) == 1
        assert "hook failed" in errors[0][0]
        assert errors[0][1] == "on_graph"

    def test_unregister_hook_object(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        results = []

        hook = mgr.register("on_graph", lambda: results.append("called"))
        assert mgr.unregister(hook) is True
        mgr.fire("on_graph")
        assert results == []

    def test_unregister_string_event_with_callback(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        results = []

        def my_cb():
            results.append("called")

        mgr.register("on_graph", my_cb)
        assert mgr.unregister("on_graph", my_cb) is True
        mgr.fire("on_graph")
        assert results == []

    def test_unregister_nonexistent_returns_false(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        assert mgr.unregister("on_graph", lambda: None) is False

    def test_unregister_plugin_removes_all_hooks(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        results = []

        mgr.register("on_graph", lambda: results.append("g"), plugin_name="plug_a")
        mgr.register("on_audio", lambda: results.append("a"), plugin_name="plug_a")
        mgr.register("on_graph", lambda: results.append("other"), plugin_name="plug_b")

        count = mgr.unregister_plugin("plug_a")
        assert count == 2

        mgr.fire("on_graph")
        mgr.fire("on_audio")
        assert results == ["other"]


class TestHookManagerTypedHooks:
    """Tests for HookType-based registration and triggering."""

    def test_register_hook_type(self):
        from voice_soundboard.plugins.hooks import HookManager, HookType

        mgr = HookManager()
        hook = mgr.register(HookType.ON_GRAPH, lambda data: data)
        assert hook.event == "ON_GRAPH"

    def test_trigger_hook_type(self):
        from voice_soundboard.plugins.hooks import HookManager, HookType

        mgr = HookManager()
        results = []
        mgr.register(HookType.POST_SYNTHESIS, lambda data: results.append(data))
        mgr.trigger(HookType.POST_SYNTHESIS, data="audio_done")
        assert results == ["audio_done"]

    def test_trigger_returns_results(self):
        from voice_soundboard.plugins.hooks import HookManager, HookType

        mgr = HookManager()
        mgr.register(HookType.ON_AUDIO, lambda data: data * 2)
        results = mgr.trigger(HookType.ON_AUDIO, data=5)
        assert results == [10]

    def test_trigger_ignores_errors(self):
        from voice_soundboard.plugins.hooks import HookManager, HookType

        mgr = HookManager()
        mgr.register(HookType.ON_ERROR, lambda data: 1 / 0)
        mgr.register(HookType.ON_ERROR, lambda data: "ok")
        results = mgr.trigger(HookType.ON_ERROR, data=None)
        assert results == ["ok"]

    def test_unregister_hook_type(self):
        from voice_soundboard.plugins.hooks import HookManager, HookType

        mgr = HookManager()
        def cb(data):
            return data
        mgr.register(HookType.ON_GRAPH, cb)
        assert mgr.unregister(HookType.ON_GRAPH, cb) is True
        assert mgr.trigger(HookType.ON_GRAPH, "test") == []

    def test_unregister_hook_type_not_found(self):
        from voice_soundboard.plugins.hooks import HookManager, HookType

        mgr = HookManager()
        assert mgr.unregister(HookType.ON_GRAPH, lambda: None) is False


class TestHookManagerDecorators:
    """Tests for decorator-style hook registration on HookManager."""

    def test_on_graph_decorator(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        results = []

        @mgr.on_graph()
        def handle_graph(graph):
            results.append(graph)

        mgr.fire("on_graph", "my_graph")
        assert results == ["my_graph"]

    def test_on_audio_decorator(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        results = []

        @mgr.on_audio()
        def handle_audio(audio, sample_rate):
            results.append((audio, sample_rate))

        mgr.fire("on_audio", "pcm_data", 44100)
        assert results == [("pcm_data", 44100)]

    def test_on_error_decorator(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        results = []

        @mgr.on_error()
        def handle_error(error, source_event=None):
            results.append(str(error))

        mgr.fire("on_error", error=RuntimeError("test"), source_event="on_graph")
        assert len(results) == 1

    def test_decorator_with_priority(self):
        from voice_soundboard.plugins.hooks import HookManager

        mgr = HookManager()
        order = []

        @mgr.on_graph(priority=200)
        def late_hook(graph):
            order.append("late")

        @mgr.on_graph(priority=10)
        def early_hook(graph):
            order.append("early")

        mgr.fire("on_graph", None)
        assert order == ["early", "late"]


class TestPluginDiscovery:
    """Tests for plugin discovery from directories."""

    def test_discover_nonexistent_directory(self):
        registry = PluginRegistry()
        result = registry.discover("/nonexistent/path/to/plugins")
        assert result == []

    def test_discover_empty_directory(self, tmp_path):
        registry = PluginRegistry()
        result = registry.discover(str(tmp_path))
        assert result == []

    def test_discover_skips_underscored_files(self, tmp_path):
        # Create a file starting with underscore
        (tmp_path / "_private.py").write_text("x = 1\n")
        registry = PluginRegistry()
        result = registry.discover(str(tmp_path))
        assert result == []


class TestRegistrySingleton:
    """Tests for the singleton instance pattern."""

    def test_instance_returns_same_object(self):
        # Reset the singleton for isolation
        PluginRegistry._instance = None
        a = PluginRegistry.instance()
        b = PluginRegistry.instance()
        assert a is b
        # Clean up
        PluginRegistry._instance = None

    def test_get_registry_returns_registry(self):
        from voice_soundboard.plugins.registry import get_registry
        import voice_soundboard.plugins.registry as reg_mod

        old = reg_mod._global_registry
        reg_mod._global_registry = None
        r = get_registry()
        assert isinstance(r, PluginRegistry)
        # Restore
        reg_mod._global_registry = old

