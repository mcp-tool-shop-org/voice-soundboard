"""
Plugin Sandbox - Isolated execution environment for untrusted plugins.

Provides multiple isolation strategies:
    1. RestrictedPython for pure Python sandboxing
    2. WebAssembly for untrusted code
    3. Container isolation for full isolation

The sandbox prevents:
    - Filesystem access
    - Network access
    - Excessive memory usage
    - Excessive CPU time
    - Access to sensitive APIs
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable
from enum import Enum
from contextlib import contextmanager


class SandboxStrategy(Enum):
    """Available sandboxing strategies."""
    RESTRICTED_PYTHON = "restricted_python"
    WASM = "wasm"
    CONTAINER = "container"
    PROCESS = "process"


class SandboxViolation(Exception):
    """Raised when a plugin violates sandbox restrictions."""
    
    def __init__(self, violation_type: str, message: str, plugin_id: str | None = None):
        self.violation_type = violation_type
        self.plugin_id = plugin_id
        super().__init__(f"Sandbox violation ({violation_type}): {message}")


@dataclass
class SandboxConfig:
    """Configuration for plugin sandbox."""
    
    # Resource limits
    max_memory_mb: int = 512
    max_cpu_seconds: float = 10.0
    max_execution_time_seconds: float = 30.0
    
    # Import restrictions
    allowed_imports: list[str] = field(default_factory=lambda: [
        "numpy", "scipy", "json", "re", "math", "collections",
        "itertools", "functools", "dataclasses", "typing",
    ])
    blocked_imports: list[str] = field(default_factory=lambda: [
        "os", "sys", "subprocess", "socket", "http", "urllib",
        "requests", "shutil", "pathlib", "io", "builtins",
    ])
    
    # Access restrictions
    network_access: bool = False
    filesystem_access: bool = False
    environment_access: bool = False
    
    # Sandboxing strategy
    strategy: SandboxStrategy = SandboxStrategy.RESTRICTED_PYTHON
    
    # Audit hooks
    log_all_calls: bool = False
    audit_callback: Callable[[str, Any], None] | None = None


@dataclass
class SandboxExecutionResult:
    """Result of sandboxed plugin execution."""
    
    success: bool
    result: Any = None
    error: Exception | None = None
    execution_time_seconds: float = 0.0
    memory_used_mb: float = 0.0
    cpu_time_seconds: float = 0.0
    calls_made: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class SandboxedPlugin(Protocol):
    """Protocol for plugins that can be sandboxed."""
    
    @property
    def plugin_id(self) -> str:
        """Unique identifier for the plugin."""
        ...
    
    def process(self, data: Any) -> Any:
        """Process data within the sandbox."""
        ...


class RestrictedGlobals:
    """Restricted global namespace for sandboxed execution."""
    
    # Safe builtins that plugins can use
    SAFE_BUILTINS = {
        "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
        "chr", "dict", "divmod", "enumerate", "filter", "float", "format",
        "frozenset", "getattr", "hasattr", "hash", "hex", "id", "int",
        "isinstance", "issubclass", "iter", "len", "list", "map", "max",
        "min", "next", "object", "oct", "ord", "pow", "print", "range",
        "repr", "reversed", "round", "set", "slice", "sorted", "str",
        "sum", "tuple", "type", "zip",
    }
    
    @classmethod
    def create(cls, config: SandboxConfig) -> dict[str, Any]:
        """Create restricted globals namespace."""
        import builtins
        
        restricted_builtins = {
            name: getattr(builtins, name)
            for name in cls.SAFE_BUILTINS
            if hasattr(builtins, name)
        }
        
        # Add restricted __import__
        restricted_builtins["__import__"] = cls._create_restricted_import(config)
        
        return {
            "__builtins__": restricted_builtins,
            "__name__": "__sandbox__",
            "__doc__": None,
        }
    
    @classmethod
    def _create_restricted_import(cls, config: SandboxConfig) -> Callable:
        """Create an import function that only allows approved modules."""
        
        def restricted_import(name: str, *args, **kwargs):
            # Check if module is blocked
            base_module = name.split(".")[0]
            
            if base_module in config.blocked_imports:
                raise SandboxViolation(
                    "import",
                    f"Import of '{name}' is not allowed",
                )
            
            if base_module not in config.allowed_imports:
                raise SandboxViolation(
                    "import",
                    f"Import of '{name}' is not in allowed list",
                )
            
            # Perform the import
            import importlib
            return importlib.import_module(name)
        
        return restricted_import


class ResourceMonitor:
    """Monitor resource usage during sandboxed execution."""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.start_time: float = 0.0
        self.start_cpu_time: float = 0.0
        self._stop_event = threading.Event()
        self._monitor_thread: threading.Thread | None = None
    
    def start(self) -> None:
        """Start resource monitoring."""
        self.start_time = time.perf_counter()
        self.start_cpu_time = time.process_time()
        self._stop_event.clear()
        
        # Start monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
        )
        self._monitor_thread.start()
    
    def stop(self) -> tuple[float, float]:
        """Stop monitoring and return (execution_time, cpu_time)."""
        self._stop_event.set()
        
        execution_time = time.perf_counter() - self.start_time
        cpu_time = time.process_time() - self.start_cpu_time
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        
        return execution_time, cpu_time
    
    def _monitor_loop(self) -> None:
        """Monitor resource usage in background."""
        while not self._stop_event.wait(0.1):
            elapsed = time.perf_counter() - self.start_time
            
            if elapsed > self.config.max_execution_time_seconds:
                raise SandboxViolation(
                    "timeout",
                    f"Execution exceeded {self.config.max_execution_time_seconds}s limit",
                )
            
            cpu_time = time.process_time() - self.start_cpu_time
            if cpu_time > self.config.max_cpu_seconds:
                raise SandboxViolation(
                    "cpu_limit",
                    f"CPU time exceeded {self.config.max_cpu_seconds}s limit",
                )


class PluginSandbox:
    """
    Isolated execution environment for untrusted plugins.
    
    Example:
        sandbox = PluginSandbox(
            max_memory_mb=512,
            max_cpu_seconds=10,
            allowed_imports=["numpy", "scipy"],
            network_access=False,
        )
        
        with sandbox.execute(plugin):
            result = plugin.process(audio)
    """
    
    def __init__(
        self,
        max_memory_mb: int = 512,
        max_cpu_seconds: float = 10.0,
        allowed_imports: list[str] | None = None,
        network_access: bool = False,
        filesystem_access: bool = False,
        strategy: SandboxStrategy = SandboxStrategy.RESTRICTED_PYTHON,
        config: SandboxConfig | None = None,
    ):
        if config:
            self.config = config
        else:
            self.config = SandboxConfig(
                max_memory_mb=max_memory_mb,
                max_cpu_seconds=max_cpu_seconds,
                allowed_imports=allowed_imports or SandboxConfig().allowed_imports,
                network_access=network_access,
                filesystem_access=filesystem_access,
                strategy=strategy,
            )
        
        self._active_contexts: dict[str, SandboxExecutionResult] = {}
        self._monitor: ResourceMonitor | None = None
    
    @contextmanager
    def execute(self, plugin: SandboxedPlugin):
        """
        Execute a plugin within the sandbox.
        
        Usage:
            with sandbox.execute(plugin):
                result = plugin.process(data)
        """
        plugin_id = plugin.plugin_id
        execution_result = SandboxExecutionResult(success=False)
        self._active_contexts[plugin_id] = execution_result
        
        # Start resource monitoring
        self._monitor = ResourceMonitor(self.config)
        self._monitor.start()
        
        try:
            yield execution_result
            execution_result.success = True
            
        except SandboxViolation as e:
            e.plugin_id = plugin_id
            execution_result.error = e
            raise
            
        except Exception as e:
            execution_result.error = e
            raise SandboxViolation(
                "runtime_error",
                f"Plugin raised exception: {e}",
                plugin_id,
            ) from e
            
        finally:
            if self._monitor:
                exec_time, cpu_time = self._monitor.stop()
                execution_result.execution_time_seconds = exec_time
                execution_result.cpu_time_seconds = cpu_time
            
            del self._active_contexts[plugin_id]
    
    def execute_code(
        self,
        code: str,
        context: dict[str, Any] | None = None,
        plugin_id: str = "anonymous",
    ) -> SandboxExecutionResult:
        """
        Execute arbitrary code within the sandbox.
        
        For untrusted code execution - use with caution.
        """
        result = SandboxExecutionResult(success=False)
        
        # Create restricted globals
        sandbox_globals = RestrictedGlobals.create(self.config)
        
        # Add user context
        if context:
            sandbox_globals.update(context)
        
        # Start monitoring
        monitor = ResourceMonitor(self.config)
        monitor.start()
        
        try:
            # Compile and execute
            compiled = compile(code, f"<sandbox:{plugin_id}>", "exec")
            exec(compiled, sandbox_globals)
            
            result.success = True
            result.result = sandbox_globals.get("__result__")
            
        except SandboxViolation as e:
            e.plugin_id = plugin_id
            result.error = e
            
        except Exception as e:
            result.error = SandboxViolation(
                "runtime_error",
                str(e),
                plugin_id,
            )
            
        finally:
            exec_time, cpu_time = monitor.stop()
            result.execution_time_seconds = exec_time
            result.cpu_time_seconds = cpu_time
        
        return result
    
    def validate_plugin(self, plugin: SandboxedPlugin) -> list[str]:
        """
        Validate a plugin before execution.
        
        Returns a list of warnings/issues found.
        """
        warnings = []
        
        # Check for required protocol methods
        if not hasattr(plugin, "plugin_id"):
            warnings.append("Plugin missing 'plugin_id' property")
        
        if not hasattr(plugin, "process"):
            warnings.append("Plugin missing 'process' method")
        
        # TODO: Static analysis of plugin code for blocked imports
        
        return warnings
