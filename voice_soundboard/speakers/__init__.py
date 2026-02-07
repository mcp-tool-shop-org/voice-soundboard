"""
Speaker Database - Manage speaker embeddings and voices.

v2.1 Feature (P2): Speaker database for voice cloning.

Provides a simple database for storing and retrieving
speaker embeddings by name.

Usage:
    from voice_soundboard.speakers import SpeakerDB
    
    db = SpeakerDB("./speakers")
    db.add("customer_alice", "alice_reference.wav")
    
    # Later
    engine.speak("Hello Alice!", speaker=db.get("customer_alice"))
"""

from voice_soundboard.speakers.database import SpeakerDB, SpeakerEntry

__all__ = ["SpeakerDB", "SpeakerEntry"]
