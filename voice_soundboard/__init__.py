"""
Voice Soundboard v2.5 - Text-to-speech for AI agents and developers.

Architecture:
    Compiler → ControlGraph → Engine → PCM

Public API (stable):
    VoiceEngine     - Main interface. Call .speak() to generate audio.
    SpeechResult    - Returned by .speak(). Contains .audio_path and metadata.
    Config          - Engine configuration.
    quick_speak     - One-liner: quick_speak("Hello") -> Path

v2.5 Features (new - MCP Integration & Agent Interoperability):
    mcp             - Model Context Protocol integration
                    - MCPServer, create_mcp_server: Embedded MCP server
                    - Tools: voice.speak, voice.stream, voice.interrupt, etc.
                    - MCPSession, SessionManager: Agent-aware sessions
                    - InterruptHandler, InterruptReason: Explicit interrupt semantics
                    - SynthesisMetadata, MetadataCollector: Agent observability
                    - MCPPolicy, PolicyEnforcer: Permissions & safety
                    - MCPMock, MCPTestHarness: Testing utilities

v2.4 Features (Production Scale & Audio Intelligence):
    security        - Plugin sandbox, input validation, audit logging, rate limiting
    intelligence    - Emotion detection, adaptive pacing, smart silence
    serverless      - AWS Lambda, GCP Functions, Azure Functions handlers
    distributed     - Cluster management, model sharding, job queuing
    analytics       - Usage tracking, quality monitoring, cost attribution
    scenes          - Multi-layer audio scene composition
    ambiance        - Procedural background audio generation
    spatial         - 3D spatial audio positioning and mixing
    testing         - VoiceMock, AudioAssertions, test fixtures
    backends        - ElevenLabs and Azure Neural TTS support

v2.3 Features:
    realtime        - Real-time streaming engine with <20ms buffering
    plugins         - Plugin architecture for backends, audio effects, compilers
    monitoring      - Production observability: health checks, metrics, logging
    conversation    - Multi-speaker dialogue support with turn management
    quality         - Voice quality metrics and A/B comparison tools
    formats         - Audio format conversion, sample rate, LUFS normalization

v2.1 Features:
    streaming       - IncrementalSynthesizer for word-by-word streaming
    debug           - Debug mode, visualization, profiler, diff tools
    cloning         - Speaker embedding extraction
    speakers        - SpeakerDB for managing speaker identities
    batch_synthesize- Parallel batch synthesis

Internals (for advanced users):
    voice_soundboard.graph      - ControlGraph, TokenEvent, SpeakerRef
    voice_soundboard.compiler   - compile_request()
    voice_soundboard.engine     - TTSBackend protocol, backends

Example:
    from voice_soundboard import VoiceEngine
    
    engine = VoiceEngine()
    result = engine.speak("Hello world!", voice="af_bella")
    print(result.audio_path)
    
    # v2.5: MCP Integration - Expose as agent tool
    from voice_soundboard.mcp import create_mcp_server
    server = create_mcp_server(engine)
    await server.run()
    
    # v2.5: Agent calls
    result = await server.call("voice.speak", {"text": "Hello!"})
    
    # v2.5: Agent sessions
    from voice_soundboard.mcp import SessionManager
    manager = SessionManager()
    session = manager.create_session(agent_id="planner")
    
    # v2.5: Interruption
    result = await server.call("voice.interrupt", {"reason": "user_spoke"})
    
    # v2.5: Policy enforcement
    from voice_soundboard.mcp import MCPPolicy, PolicyEnforcer
    policy = MCPPolicy(allow_tools=["voice.speak"], max_text_length=5000)
    enforcer = PolicyEnforcer(policy)
    
    # v2.4: Security - Plugin sandboxing
    from voice_soundboard.security import PluginSandbox
    sandbox = PluginSandbox()
    sandbox.execute_safe(plugin_code)
    
    # v2.4: Intelligence - Emotion detection
    from voice_soundboard.intelligence import EmotionDetector
    detector = EmotionDetector()
    emotion = detector.detect("I am so happy!")
    
    # v2.4: Serverless deployment
    from voice_soundboard.serverless import create_lambda_handler
    handler = create_lambda_handler(engine)
    
    # v2.4: Distributed synthesis
    from voice_soundboard.distributed import SynthesisCluster
    cluster = SynthesisCluster(nodes=["node1:8080", "node2:8080"])
    result = await cluster.synthesize(text)
    
    # v2.4: Analytics
    from voice_soundboard.analytics import UsageTracker, CostTracker
    tracker = UsageTracker(backend="prometheus")
    
    # v2.4: Scene composition
    from voice_soundboard.scenes import SceneBuilder
    scene = SceneBuilder("Podcast").set_music(music).add_speech(speech).build()
    
    # v2.4: Spatial audio
    from voice_soundboard.spatial import SpatialMixer, SpatialPosition
    mixer = SpatialMixer()
    stereo = mixer.position(mono, SpatialPosition.left(2.0))
    
    # v2.4: Testing utilities
    from voice_soundboard.testing import VoiceMock, AudioAssertions
    mock = VoiceMock()
    assertions = AudioAssertions(audio).assert_no_clipping()
    
    # v2.3: Real-time streaming
    from voice_soundboard.realtime import RealtimeEngine
    rt_engine = RealtimeEngine(backend)
    session = rt_engine.create_session()
    session.submit("Hello world!")
    for chunk in session.stream():
        play(chunk)
    
    # v2.3: Plugins
    from voice_soundboard.plugins import PluginRegistry
    registry = PluginRegistry()
    registry.discover("./my_plugins")
    
    # v2.3: Multi-speaker conversation
    from voice_soundboard.conversation import Conversation, Speaker
    conv = Conversation(speakers=[Speaker("Alice"), Speaker("Bob")])
    conv.add_turn("Alice", "Hello!")
    conv.add_turn("Bob", "Hi there!")
    audio = conv.synthesize(engine)
    
    # v2.3: Quality metrics
    from voice_soundboard.quality import evaluate_pronunciation, ab_test
    score = evaluate_pronunciation(audio, "Hello world")
    print(f"Quality: {score.level}")

    # v2.1: Incremental streaming
    from voice_soundboard.streaming import IncrementalSynthesizer
    synth = IncrementalSynthesizer(backend)
    for chunk in synth.feed("Hello"):
        play(chunk)

    # v2.1: Debug mode
    engine = VoiceEngine(Config(debug=True))
    result = engine.speak("Hello!")
    print(result.debug_info)
"""

__version__ = "2.5.0-alpha.1"
API_VERSION = 2

# Public API - backwards compatible with v1
from voice_soundboard.adapters.api import (
    VoiceEngine,
    SpeechResult,
    Config,
    quick_speak,
)

# Voice data
from voice_soundboard.compiler.voices import VOICES, PRESETS

# v2.1: Batch synthesis
from voice_soundboard.runtime.batch import batch_synthesize

__all__ = [
    # Version
    "__version__",
    "API_VERSION",
    # Core
    "VoiceEngine",
    "SpeechResult", 
    "Config",
    "quick_speak",
    # Data
    "VOICES",
    "PRESETS",
    # v2.1
    "batch_synthesize",
]

# v2.4 Submodules (lazy import for performance)
# Security: from voice_soundboard.security import PluginSandbox, InputValidator, AuditLogger
# Intelligence: from voice_soundboard.intelligence import EmotionDetector, AdaptivePacer
# Serverless: from voice_soundboard.serverless import create_lambda_handler, create_cloud_function_handler
# Distributed: from voice_soundboard.distributed import SynthesisCluster, SynthesisQueue
# Analytics: from voice_soundboard.analytics import UsageTracker, QualityMonitor, CostTracker
# Scenes: from voice_soundboard.scenes import Scene, SceneBuilder, SceneMixer
# Ambiance: from voice_soundboard.ambiance import AmbianceGenerator, get_preset
# Spatial: from voice_soundboard.spatial import SpatialMixer, SpatialPosition, SpatialScene
# Testing: from voice_soundboard.testing import VoiceMock, AudioAssertions

# v2.3 Submodules (lazy import for performance)
# Import with: from voice_soundboard.realtime import RealtimeEngine
# Import with: from voice_soundboard.plugins import PluginRegistry
# Import with: from voice_soundboard.monitoring import HealthCheck, MetricsCollector
# Import with: from voice_soundboard.conversation import Conversation, Speaker
# Import with: from voice_soundboard.quality import evaluate_pronunciation, ab_test
# Import with: from voice_soundboard.formats import convert_sample_rate, normalize_loudness
