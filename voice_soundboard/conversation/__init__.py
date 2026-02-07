"""
Multi-Speaker Conversations for Voice Soundboard v2.3.

Provides first-class support for conversations with multiple speakers,
turn-taking, and dialogue synthesis.

Components:
    Conversation    - Multi-speaker dialogue container
    Speaker         - Speaker configuration
    Turn            - A single conversation turn

Example:
    from voice_soundboard.conversation import Conversation, Speaker
    
    conv = Conversation(
        speakers={
            "alice": Speaker(voice="af_bella", style="friendly"),
            "bob": Speaker(voice="am_michael", style="professional"),
        }
    )
    
    script = [
        ("alice", "Hello Bob!"),
        ("bob", "Hi Alice, how are you?"),
    ]
    
    audio = conv.synthesize(script, engine)
"""

from voice_soundboard.conversation.speaker import Speaker, SpeakerStyle
from voice_soundboard.conversation.turn import Turn, TurnType, Timeline
from voice_soundboard.conversation.conversation import Conversation
from voice_soundboard.conversation.parser import ScriptParser

__all__ = [
    "Speaker",
    "SpeakerStyle",
    "Turn",
    "TurnType",
    "Timeline",
    "Conversation",
    "ScriptParser",
]
