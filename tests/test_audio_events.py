"""Tests for the audio event adapter."""

import json
import struct
import tempfile
import wave
from pathlib import Path

import numpy as np
import pytest

from voice_soundboard.adapters.audio_events import (
    AudioEventAdapter,
    AudioEventManifest,
    AudioEventSpec,
    AudioVariant,
    render_timeline_with_events,
    stream_timeline_with_events,
)
from voice_soundboard.graph import ControlGraph, TokenEvent, SpeakerRef, Paralinguistic, ParalinguisticEvent


def create_test_wav(path: Path, duration: float, sample_rate: int = 24000):
    """Create a test WAV file with a sine wave."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    num_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, num_samples)
    audio = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(audio.tobytes())


@pytest.fixture
def temp_assets():
    """Create temporary asset directory with test WAVs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        # Create WAV files
        create_test_wav(base / "laugh" / "soft.wav", 0.18)
        create_test_wav(base / "laugh" / "medium.wav", 0.25)
        create_test_wav(base / "laugh" / "hard.wav", 0.35)
        create_test_wav(base / "sigh" / "short.wav", 0.4)
        
        # Create manifest
        manifest = {
            "sample_rate": 24000,
            "events": {
                "laugh": {
                    "variants": [
                        {"id": "soft", "file": "laugh/soft.wav", "intensity_range": [0.0, 0.4], "duration": 0.18},
                        {"id": "medium", "file": "laugh/medium.wav", "intensity_range": [0.4, 0.7], "duration": 0.25},
                        {"id": "hard", "file": "laugh/hard.wav", "intensity_range": [0.7, 1.0], "duration": 0.35},
                    ]
                },
                "sigh": {
                    "variants": [
                        {"id": "short", "file": "sigh/short.wav", "intensity_range": [0.0, 1.0], "duration": 0.4},
                    ]
                },
            }
        }
        
        manifest_path = base / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        
        yield base, manifest_path


class TestAudioVariant:
    """Tests for AudioVariant."""
    
    def test_matches_intensity_in_range(self):
        variant = AudioVariant(
            id="test",
            file=Path("test.wav"),
            intensity_min=0.3,
            intensity_max=0.7,
            duration=0.2,
        )
        
        assert variant.matches_intensity(0.5)
        assert variant.matches_intensity(0.3)  # Inclusive
        assert variant.matches_intensity(0.7)  # Inclusive
    
    def test_matches_intensity_out_of_range(self):
        variant = AudioVariant(
            id="test",
            file=Path("test.wav"),
            intensity_min=0.3,
            intensity_max=0.7,
            duration=0.2,
        )
        
        assert not variant.matches_intensity(0.2)
        assert not variant.matches_intensity(0.8)
    
    def test_range_width(self):
        variant = AudioVariant(
            id="test",
            file=Path("test.wav"),
            intensity_min=0.2,
            intensity_max=0.8,
            duration=0.2,
        )
        
        assert variant.range_width == pytest.approx(0.6)


class TestAudioEventSpec:
    """Tests for AudioEventSpec variant selection."""
    
    def test_select_exact_match(self):
        spec = AudioEventSpec(
            type="laugh",
            variants=[
                AudioVariant("soft", Path("a.wav"), 0.0, 0.4, 0.2),
                AudioVariant("hard", Path("b.wav"), 0.6, 1.0, 0.3),
            ],
        )
        
        result = spec.select_variant(0.2)
        assert result.id == "soft"
        
        result = spec.select_variant(0.8)
        assert result.id == "hard"
    
    def test_select_narrowest_when_overlapping(self):
        """When multiple ranges match, pick narrowest."""
        spec = AudioEventSpec(
            type="laugh",
            variants=[
                AudioVariant("wide", Path("a.wav"), 0.0, 1.0, 0.2),   # Range: 1.0
                AudioVariant("narrow", Path("b.wav"), 0.4, 0.6, 0.3),  # Range: 0.2
            ],
        )
        
        # 0.5 matches both, should pick narrow
        result = spec.select_variant(0.5)
        assert result.id == "narrow"
    
    def test_select_closest_when_no_match(self):
        """When no exact match, pick closest range."""
        spec = AudioEventSpec(
            type="laugh",
            variants=[
                AudioVariant("low", Path("a.wav"), 0.0, 0.3, 0.2),
                AudioVariant("high", Path("b.wav"), 0.7, 1.0, 0.3),
            ],
        )
        
        # 0.5 is between ranges, closer to low (distance 0.2) than high (distance 0.2)
        # Both equal distance, should pick first
        result = spec.select_variant(0.5)
        assert result is not None
        
        # 0.4 is closer to low (distance 0.1) than high (distance 0.3)
        result = spec.select_variant(0.4)
        assert result.id == "low"
    
    def test_select_empty_variants(self):
        spec = AudioEventSpec(type="laugh", variants=[])
        assert spec.select_variant(0.5) is None


class TestAudioEventManifest:
    """Tests for AudioEventManifest."""
    
    def test_load_manifest(self, temp_assets):
        base, manifest_path = temp_assets
        
        manifest = AudioEventManifest(manifest_path)
        
        assert manifest.sample_rate == 24000
        assert "laugh" in manifest.events
        assert "sigh" in manifest.events
    
    def test_get_event_spec(self, temp_assets):
        base, manifest_path = temp_assets
        
        manifest = AudioEventManifest(manifest_path)
        
        spec = manifest.get_event_spec("laugh")
        assert spec is not None
        assert len(spec.variants) == 3
        
        # Also works with Paralinguistic enum
        spec = manifest.get_event_spec(Paralinguistic.LAUGH)
        assert spec is not None
    
    def test_validate_success(self, temp_assets):
        base, manifest_path = temp_assets
        
        manifest = AudioEventManifest(manifest_path)
        issues = manifest.validate()
        
        assert issues == []
    
    def test_validate_missing_file(self, temp_assets):
        base, manifest_path = temp_assets
        
        # Delete a WAV file
        (base / "laugh" / "soft.wav").unlink()
        
        manifest = AudioEventManifest(manifest_path)
        issues = manifest.validate()
        
        assert len(issues) == 1
        assert "not found" in issues[0]


class TestAudioEventAdapter:
    """Tests for AudioEventAdapter."""
    
    def test_from_manifest(self, temp_assets):
        base, manifest_path = temp_assets
        
        adapter = AudioEventAdapter.from_manifest(manifest_path)
        
        assert adapter.sample_rate == 24000
        assert "laugh" in adapter.supported_events()
    
    def test_try_load_missing(self):
        adapter = AudioEventAdapter.try_load("/nonexistent/manifest.json")
        assert adapter is None
    
    def test_render_event(self, temp_assets):
        base, manifest_path = temp_assets
        
        adapter = AudioEventAdapter.from_manifest(manifest_path)
        
        event = ParalinguisticEvent(
            type=Paralinguistic.LAUGH,
            start_time=0.0,
            intensity=0.5,  # Should select "medium"
        )
        
        pcm = adapter.render(event)
        
        assert pcm is not None
        assert isinstance(pcm, np.ndarray)
        assert pcm.dtype == np.float32
        # Duration should be ~0.25s at 24000 Hz
        expected_samples = int(0.25 * 24000)
        assert abs(len(pcm) - expected_samples) < 100
    
    def test_render_unknown_event(self, temp_assets):
        base, manifest_path = temp_assets
        
        adapter = AudioEventAdapter.from_manifest(manifest_path)
        
        event = ParalinguisticEvent(
            type=Paralinguistic.YAWN,  # Not in manifest
            start_time=0.0,
        )
        
        pcm = adapter.render(event)
        assert pcm is None
    
    def test_render_caching(self, temp_assets):
        base, manifest_path = temp_assets
        
        adapter = AudioEventAdapter.from_manifest(manifest_path)
        
        event = ParalinguisticEvent(type=Paralinguistic.LAUGH, start_time=0.0, intensity=0.5)
        
        pcm1 = adapter.render(event)
        pcm2 = adapter.render(event)
        
        # Should be same cached array
        assert pcm1 is pcm2


class TestRenderTimeline:
    """Tests for render_timeline_with_events."""
    
    def test_no_adapter(self):
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("test"),
            events=[ParalinguisticEvent(Paralinguistic.LAUGH, start_time=0.0)],
        )
        speech = np.zeros(24000, dtype=np.float32)
        
        result = render_timeline_with_events(graph, speech, None, 24000)
        
        # Should return speech unchanged
        assert np.array_equal(result, speech)
    
    def test_no_events(self, temp_assets):
        base, manifest_path = temp_assets
        adapter = AudioEventAdapter.from_manifest(manifest_path)
        
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("test"),
            events=[],
        )
        speech = np.zeros(24000, dtype=np.float32)
        
        result = render_timeline_with_events(graph, speech, adapter, 24000)
        
        assert np.array_equal(result, speech)
    
    def test_event_at_start(self, temp_assets):
        base, manifest_path = temp_assets
        adapter = AudioEventAdapter.from_manifest(manifest_path)
        
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("test"),
            events=[ParalinguisticEvent(Paralinguistic.LAUGH, start_time=0.0, intensity=0.5)],
        )
        speech = np.ones(24000, dtype=np.float32)  # 1 second of ones
        
        result = render_timeline_with_events(graph, speech, adapter, 24000)
        
        # Result should be longer than speech (event prepended)
        assert len(result) > len(speech)
    
    def test_sample_rate_mismatch(self, temp_assets):
        base, manifest_path = temp_assets
        adapter = AudioEventAdapter.from_manifest(manifest_path)
        
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("test"),
            events=[ParalinguisticEvent(Paralinguistic.LAUGH, start_time=0.0)],
        )
        speech = np.zeros(22050, dtype=np.float32)
        
        # Adapter is 24000 Hz, speech is 22050 Hz
        result = render_timeline_with_events(graph, speech, adapter, 22050)
        
        # Should return speech unchanged (sample rate mismatch)
        assert np.array_equal(result, speech)


class TestStreamTimeline:
    """Tests for stream_timeline_with_events."""
    
    def test_no_adapter(self):
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("test"),
        )
        speech_chunks = [np.zeros(1000) for _ in range(3)]
        
        result = list(stream_timeline_with_events(graph, iter(speech_chunks), None, 24000))
        
        assert len(result) == 3
    
    def test_events_at_start_yielded_first(self, temp_assets):
        base, manifest_path = temp_assets
        adapter = AudioEventAdapter.from_manifest(manifest_path)
        
        graph = ControlGraph(
            tokens=[TokenEvent(text="Hello")],
            speaker=SpeakerRef.from_voice("test"),
            events=[ParalinguisticEvent(Paralinguistic.LAUGH, start_time=0.0, intensity=0.5)],
        )
        speech_chunks = [np.ones(1000, dtype=np.float32) for _ in range(3)]
        
        result = list(stream_timeline_with_events(graph, iter(speech_chunks), adapter, 24000))
        
        # First chunk should be the event (sine wave), not speech (ones)
        assert len(result) >= 4  # 1 event + 3 speech chunks
        assert not np.allclose(result[0], 1.0)  # Event is sine, not ones


class TestIntegration:
    """Integration tests for the complete flow."""
    
    def test_deterministic_selection(self, temp_assets):
        """Variant selection must be deterministic (no randomness)."""
        base, manifest_path = temp_assets
        adapter = AudioEventAdapter.from_manifest(manifest_path)
        
        event = ParalinguisticEvent(type=Paralinguistic.LAUGH, start_time=0.0, intensity=0.5)
        
        # Render 100 times, should always get same result
        results = [len(adapter.render(event)) for _ in range(100)]
        
        assert len(set(results)) == 1  # All identical
    
    def test_event_duration_preserved(self, temp_assets):
        """Event WAV duration should match manifest."""
        base, manifest_path = temp_assets
        adapter = AudioEventAdapter.from_manifest(manifest_path)
        
        # Test each variant's duration matches
        for intensity, expected_id, expected_duration in [
            (0.2, "soft", 0.18),
            (0.5, "medium", 0.25),
            (0.8, "hard", 0.35),
        ]:
            event = ParalinguisticEvent(type=Paralinguistic.LAUGH, start_time=0.0, intensity=intensity)
            pcm = adapter.render(event)
            
            actual_duration = len(pcm) / adapter.sample_rate
            assert abs(actual_duration - expected_duration) < 0.01
