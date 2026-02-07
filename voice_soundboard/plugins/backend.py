"""
Backend plugin for custom TTS engines.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Iterator

import numpy as np

from voice_soundboard.graph import ControlGraph
from voice_soundboard.engine.base import TTSBackend, BaseTTSBackend
from voice_soundboard.plugins.base import Plugin, PluginType


class BackendPlugin(Plugin, BaseTTSBackend):
    """Plugin for adding custom TTS backends.
    
    Backend plugins implement the TTSBackend protocol and can be used
    like any built-in backend.
    
    Example:
        @plugin
        class MyCloudTTSPlugin(BackendPlugin):
            name = "my_cloud_tts"
            
            @property
            def sample_rate(self) -> int:
                return 24000
            
            def synthesize(self, graph: ControlGraph) -> np.ndarray:
                # Call your TTS service
                audio = my_tts_service(graph)
                return audio
        
        # Use it
        engine.register_plugin(MyCloudTTSPlugin())
        engine.speak("Hello!", backend="my_cloud_tts")
    """
    
    plugin_type = PluginType.BACKEND
    
    def __init__(self, config=None):
        Plugin.__init__(self, config)
    
    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Output sample rate in Hz."""
        ...
    
    @abstractmethod
    def synthesize(self, graph: ControlGraph) -> np.ndarray:
        """Synthesize audio from a ControlGraph.
        
        Args:
            graph: The compiled control graph.
        
        Returns:
            PCM audio as float32 numpy array.
        """
        ...
    
    def synthesize_stream(
        self,
        graph: ControlGraph,
        chunk_size: int = 4096,
    ) -> Iterator[np.ndarray]:
        """Streaming synthesis.
        
        Override for true streaming backends. Default chunks full synthesis.
        
        Args:
            graph: The compiled control graph.
            chunk_size: Size of each audio chunk.
        
        Yields:
            Audio chunks as numpy arrays.
        """
        audio = self.synthesize(graph)
        for i in range(0, len(audio), chunk_size):
            yield audio[i:i + chunk_size]
    
    def get_voices(self) -> list[str]:
        """Get available voices for this backend.
        
        Returns:
            List of voice identifiers.
        """
        return []
    
    def is_voice_available(self, voice: str) -> bool:
        """Check if a voice is available.
        
        Args:
            voice: Voice identifier.
        
        Returns:
            True if voice is available.
        """
        return voice in self.get_voices()
    
    def on_load(self, registry) -> None:
        """Register the backend with the engine."""
        registry.register_backend(self.name, self)
    
    def on_unload(self) -> None:
        """Cleanup backend resources."""
        pass


class CloudBackendPlugin(BackendPlugin):
    """Base class for cloud-based TTS backends.
    
    Provides common functionality for API-based backends:
    - API key management
    - Rate limiting
    - Retry logic
    - Response caching
    
    Example:
        class OpenAITTSPlugin(CloudBackendPlugin):
            name = "openai"
            api_base = "https://api.openai.com/v1"
            
            def _call_api(self, text: str, voice: str) -> bytes:
                response = requests.post(...)
                return response.content
    """
    
    api_base: str = ""
    api_key_env: str = ""  # Environment variable for API key
    
    def __init__(self, config=None, api_key: str | None = None):
        super().__init__(config)
        self._api_key = api_key
        
        if not self._api_key and self.api_key_env:
            import os
            self._api_key = os.environ.get(self.api_key_env)
    
    @property
    def api_key(self) -> str | None:
        """API key for authentication."""
        return self._api_key
    
    def set_api_key(self, key: str) -> None:
        """Set the API key."""
        self._api_key = key
    
    @abstractmethod
    def _call_api(self, text: str, voice: str, **kwargs) -> bytes:
        """Make API call to TTS service.
        
        Args:
            text: Text to synthesize.
            voice: Voice to use.
            **kwargs: Additional parameters.
        
        Returns:
            Raw audio bytes from API.
        """
        ...
    
    def _decode_audio(self, audio_bytes: bytes) -> np.ndarray:
        """Decode audio bytes to numpy array.
        
        Override for non-standard audio formats.
        
        Args:
            audio_bytes: Raw audio bytes.
        
        Returns:
            Audio as float32 numpy array.
        """
        import io
        import wave
        
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            audio = np.frombuffer(
                wf.readframes(wf.getnframes()),
                dtype=np.int16,
            ).astype(np.float32) / 32768.0
        
        return audio
