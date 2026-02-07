"""
Screen Reader Detection - Auto-detect active assistive technology.

This module probes the system to detect which screen reader (if any)
is currently running, and returns the appropriate adapter.
"""

from __future__ import annotations

import sys
from typing import Optional, Type

from voice_soundboard.accessibility.screen_readers.base import (
    ScreenReaderAdapter,
    NullScreenReaderAdapter,
)


def detect_screen_reader() -> Optional[ScreenReaderAdapter]:
    """Auto-detect and return the active screen reader adapter.
    
    Detection order:
    1. NVDA (Windows) - most common open-source
    2. JAWS (Windows) - most common commercial
    3. Narrator (Windows) - built-in
    4. VoiceOver (macOS) - built-in
    5. Orca (Linux) - most common on Linux
    
    Returns:
        Appropriate adapter instance, or None if no screen reader detected
    """
    adapters = get_available_adapters()
    
    for adapter_class in adapters:
        try:
            adapter = adapter_class()
            if adapter.is_active:
                return adapter
        except Exception:
            continue  # Skip adapters that fail to initialize
    
    return None


def get_available_adapters() -> list[Type[ScreenReaderAdapter]]:
    """Get list of adapter classes available on this platform.
    
    Returns:
        List of adapter classes (not instances) for the current OS
    """
    adapters: list[Type[ScreenReaderAdapter]] = []
    
    if sys.platform == "win32":
        # Windows: NVDA, JAWS, Narrator
        try:
            from voice_soundboard.accessibility.screen_readers.nvda import NVDAAdapter
            adapters.append(NVDAAdapter)
        except ImportError:
            pass
        
        try:
            from voice_soundboard.accessibility.screen_readers.jaws import JAWSAdapter
            adapters.append(JAWSAdapter)
        except ImportError:
            pass
        
        try:
            from voice_soundboard.accessibility.screen_readers.narrator import NarratorAdapter
            adapters.append(NarratorAdapter)
        except ImportError:
            pass
    
    elif sys.platform == "darwin":
        # macOS: VoiceOver
        try:
            from voice_soundboard.accessibility.screen_readers.voiceover import VoiceOverAdapter
            adapters.append(VoiceOverAdapter)
        except ImportError:
            pass
    
    else:
        # Linux: Orca
        try:
            from voice_soundboard.accessibility.screen_readers.orca import OrcaAdapter
            adapters.append(OrcaAdapter)
        except ImportError:
            pass
    
    return adapters


def get_adapter_for_mode(mode: "ScreenReaderMode") -> Optional[ScreenReaderAdapter]:
    """Get a specific adapter by mode.
    
    Args:
        mode: The screen reader mode to use
        
    Returns:
        Adapter instance or None if not available
    """
    from voice_soundboard.accessibility.screen_readers.base import ScreenReaderMode
    
    if mode == ScreenReaderMode.AUTO:
        return detect_screen_reader()
    
    if mode == ScreenReaderMode.NONE:
        return NullScreenReaderAdapter()
    
    # Map modes to adapter imports
    mode_to_module = {
        ScreenReaderMode.NVDA: ("nvda", "NVDAAdapter"),
        ScreenReaderMode.JAWS: ("jaws", "JAWSAdapter"),
        ScreenReaderMode.VOICEOVER: ("voiceover", "VoiceOverAdapter"),
        ScreenReaderMode.NARRATOR: ("narrator", "NarratorAdapter"),
        ScreenReaderMode.ORCA: ("orca", "OrcaAdapter"),
    }
    
    if mode not in mode_to_module:
        return None
    
    module_name, class_name = mode_to_module[mode]
    
    try:
        import importlib
        module = importlib.import_module(
            f"voice_soundboard.accessibility.screen_readers.{module_name}"
        )
        adapter_class = getattr(module, class_name)
        return adapter_class()
    except (ImportError, AttributeError):
        return None
