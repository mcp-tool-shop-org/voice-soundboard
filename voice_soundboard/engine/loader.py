"""
Engine Loader - Auto-detect and load best available backend.
"""

from __future__ import annotations

import logging
from pathlib import Path

from voice_soundboard.engine.base import TTSBackend

logger = logging.getLogger(__name__)


def load_backend(
    backend: str = "auto",
    model_dir: Path | str | None = None,
    device: str = "auto",
    **kwargs,
) -> TTSBackend:
    """Load a TTS backend.

    Args:
        backend: Backend name or "auto" to auto-detect.
                 Options: "kokoro", "piper", "openai", "coqui",
                          "elevenlabs", "azure", "mock", "auto"
        model_dir: Directory containing model files
        device: "cuda", "cpu", or "auto"
        **kwargs: Additional backend-specific options

    Returns:
        Initialized TTSBackend

    Raises:
        ValueError: If backend name is unknown
        ImportError: If requested backend's dependencies are not installed
    """
    if backend == "auto":
        return _auto_load(model_dir, device)

    if backend == "kokoro":
        from voice_soundboard.engine.backends.kokoro import KokoroBackend
        return KokoroBackend(model_dir=model_dir, device=device)

    if backend == "piper":
        from voice_soundboard.engine.backends.piper import PiperBackend
        use_cuda = device == "cuda"
        return PiperBackend(model_dir=model_dir, use_cuda=use_cuda)

    if backend == "openai":
        from voice_soundboard.engine.backends.openai import OpenAITTSBackend
        return OpenAITTSBackend(**kwargs)

    if backend == "coqui":
        from voice_soundboard.engine.backends.coqui import CoquiTTSBackend
        gpu = device == "cuda"
        return CoquiTTSBackend(gpu=gpu, **kwargs)

    if backend == "elevenlabs":
        from voice_soundboard.engine.backends.elevenlabs import ElevenLabsBackend
        return ElevenLabsBackend(**kwargs)

    if backend == "azure":
        from voice_soundboard.engine.backends.azure import AzureTTSBackend
        return AzureTTSBackend(**kwargs)

    if backend == "mock":
        from voice_soundboard.engine.backends.mock import MockBackend
        return MockBackend()

    raise ValueError(f"Unknown backend: {backend}")


def _auto_load(model_dir: Path | str | None, device: str) -> TTSBackend:
    """Auto-detect best available backend.

    Priority: Kokoro (best quality) > Piper (CPU-friendly) > Mock (testing).
    Cloud backends (OpenAI, ElevenLabs, Azure) are never auto-selected
    because they require API keys and incur costs.
    """
    # Try Kokoro first (best quality)
    try:
        from voice_soundboard.engine.backends.kokoro import KokoroBackend, is_available
        if is_available():
            logger.info("Auto-detected Kokoro backend")
            return KokoroBackend(model_dir=model_dir, device=device)
    except ImportError:
        pass

    # Try Piper second (fast, lightweight)
    try:
        from voice_soundboard.engine.backends.piper import PiperBackend, is_available as piper_available
        if piper_available():
            logger.info("Auto-detected Piper backend")
            use_cuda = device == "cuda"
            return PiperBackend(model_dir=model_dir, use_cuda=use_cuda)
    except ImportError:
        pass

    # Fall back to mock
    logger.warning("No TTS backend available, using mock")
    from voice_soundboard.engine.backends.mock import MockBackend
    return MockBackend()


def list_backends() -> list[str]:
    """List available backends (installed and ready to use)."""
    available = ["mock"]  # Always available

    try:
        from voice_soundboard.engine.backends.kokoro import is_available
        if is_available():
            available.append("kokoro")
    except ImportError:
        pass

    try:
        from voice_soundboard.engine.backends.piper import is_available as piper_available
        if piper_available():
            available.append("piper")
    except ImportError:
        pass

    try:
        from voice_soundboard.engine.backends.openai import OpenAITTSBackend  # noqa: F401
        available.append("openai")
    except ImportError:
        pass

    try:
        from voice_soundboard.engine.backends.coqui import CoquiTTSBackend  # noqa: F401
        available.append("coqui")
    except ImportError:
        pass

    try:
        from voice_soundboard.engine.backends.elevenlabs import ELEVENLABS_AVAILABLE
        if ELEVENLABS_AVAILABLE:
            available.append("elevenlabs")
    except ImportError:
        pass

    try:
        from voice_soundboard.engine.backends.azure import AZURE_AVAILABLE
        if AZURE_AVAILABLE:
            available.append("azure")
    except ImportError:
        pass

    return available
