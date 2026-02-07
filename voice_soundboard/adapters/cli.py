"""
CLI Adapter - Command-line interface.

Thin wrapper over compiler + engine.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(args: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="voice-soundboard",
        description="Text-to-speech for AI agents and developers",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # speak command
    speak_parser = subparsers.add_parser("speak", help="Generate speech from text")
    speak_parser.add_argument("text", help="Text to speak")
    speak_parser.add_argument("-v", "--voice", help="Voice ID (e.g., af_bella)")
    speak_parser.add_argument("-p", "--preset", help="Voice preset (e.g., narrator)")
    speak_parser.add_argument("-e", "--emotion", help="Emotion (e.g., happy, calm)")
    speak_parser.add_argument("-s", "--speed", type=float, help="Speed multiplier")
    speak_parser.add_argument("--style", help="Natural language style")
    speak_parser.add_argument("-o", "--output", help="Output filename")
    speak_parser.add_argument("--play", action="store_true", help="Play audio after generation")
    
    # voices command
    subparsers.add_parser("voices", help="List available voices")
    
    # presets command
    subparsers.add_parser("presets", help="List voice presets")
    
    # emotions command
    subparsers.add_parser("emotions", help="List available emotions")
    
    # version command
    subparsers.add_parser("version", help="Show version")
    
    parsed = parser.parse_args(args)
    
    if parsed.command is None:
        parser.print_help()
        return 0
    
    if parsed.command == "version":
        from voice_soundboard import __version__
        print(f"voice-soundboard {__version__}")
        return 0
    
    if parsed.command == "voices":
        return _cmd_voices()
    
    if parsed.command == "presets":
        return _cmd_presets()
    
    if parsed.command == "emotions":
        return _cmd_emotions()
    
    if parsed.command == "speak":
        return _cmd_speak(parsed)
    
    return 1


def _cmd_speak(args: argparse.Namespace) -> int:
    """Handle speak command."""
    from voice_soundboard import VoiceEngine
    
    engine = VoiceEngine()
    
    try:
        result = engine.speak(
            args.text,
            voice=args.voice,
            preset=args.preset,
            emotion=args.emotion,
            speed=args.speed,
            style=args.style,
            save_as=args.output,
        )
        
        print(f"Audio saved to: {result.audio_path}")
        print(f"Duration: {result.duration_seconds:.2f}s")
        print(f"Voice: {result.voice_used}")
        
        if args.play:
            _play_audio(result.audio_path)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _cmd_voices() -> int:
    """List available voices."""
    from voice_soundboard.compiler import VOICES
    
    print("Available voices:")
    print()
    
    # Group by accent
    by_accent: dict[str, list] = {}
    for voice_id, info in VOICES.items():
        accent = info.accent
        if accent not in by_accent:
            by_accent[accent] = []
        by_accent[accent].append((voice_id, info))
    
    for accent in sorted(by_accent.keys()):
        print(f"  {accent.title()}:")
        for voice_id, info in sorted(by_accent[accent]):
            print(f"    {voice_id:15} - {info.name} ({info.gender}, {info.style})")
        print()
    
    return 0


def _cmd_presets() -> int:
    """List voice presets."""
    from voice_soundboard.compiler import PRESETS
    
    print("Voice presets:")
    print()
    for name, config in PRESETS.items():
        print(f"  {name:15} - {config.description}")
        print(f"                    Voice: {config.voice}, Speed: {config.speed}")
        print()
    
    return 0


def _cmd_emotions() -> int:
    """List available emotions."""
    from voice_soundboard.compiler import EMOTIONS
    
    print("Available emotions:")
    print()
    for name, profile in EMOTIONS.items():
        mods = []
        if profile.speed != 1.0:
            mods.append(f"speed={profile.speed:.2f}")
        if profile.pitch != 1.0:
            mods.append(f"pitch={profile.pitch:.2f}")
        if profile.energy != 1.0:
            mods.append(f"energy={profile.energy:.2f}")
        
        mod_str = ", ".join(mods) if mods else "neutral"
        print(f"  {name:15} - {mod_str}")
    
    return 0


def _play_audio(path: Path) -> None:
    """Play audio file (best effort)."""
    try:
        import sounddevice as sd
        import soundfile as sf
        
        data, sr = sf.read(path)
        sd.play(data, sr)
        sd.wait()
    except ImportError:
        print("(Install sounddevice to enable playback)")
    except Exception as e:
        print(f"(Playback failed: {e})")


if __name__ == "__main__":
    sys.exit(main())
