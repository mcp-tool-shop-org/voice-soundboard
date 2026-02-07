"""Tests for event timing invariants.

These tests verify TIMELINE CORRECTNESS, not audio quality.

Invariants tested:
1. Events insert time (delay speech)
2. Events do not overlap speech
3. Event duration == WAV duration
4. Streaming order is deterministic
"""

import numpy as np
import pytest

from voice_soundboard.graph import (
    ControlGraph,
    TokenEvent,
    SpeakerRef,
    Paralinguistic,
    ParalinguisticEvent,
)
from voice_soundboard.adapters.audio_events import (
    render_timeline_with_events,
    stream_timeline_with_events,
)


SAMPLE_RATE = 24000


def make_pcm(duration_sec: float) -> np.ndarray:
    """Create fake PCM of a given duration."""
    samples = int(duration_sec * SAMPLE_RATE)
    return np.ones(samples, dtype=np.float32)


def make_graph(
    text: str = "hello",
    events: list[ParalinguisticEvent] | None = None,
) -> ControlGraph:
    """Create a test graph."""
    return ControlGraph(
        tokens=[TokenEvent(text=text)],
        speaker=SpeakerRef.from_voice("test"),
        events=events or [],
    )


class TestEventInsertsTime:
    """Test that events insert time before/after speech."""
    
    def test_event_at_start_extends_duration(self, temp_audio_assets):
        """Event at start should make output longer than speech alone."""
        adapter = temp_audio_assets
        
        speech_duration = 1.0
        speech = make_pcm(speech_duration)
        
        event = ParalinguisticEvent(
            type=Paralinguistic.LAUGH,
            start_time=0.0,
            intensity=0.5,
            duration=0.25,
        )
        graph = make_graph(events=[event])
        
        result = render_timeline_with_events(graph, speech, adapter, SAMPLE_RATE)
        
        # Result should be longer than speech by event duration
        result_duration = len(result) / SAMPLE_RATE
        assert result_duration > speech_duration
    
    def test_event_time_is_additive(self, temp_audio_assets):
        """Multiple events should add their durations."""
        adapter = temp_audio_assets
        
        speech = make_pcm(0.5)
        
        events = [
            ParalinguisticEvent(Paralinguistic.LAUGH, start_time=0.0, intensity=0.5),
            ParalinguisticEvent(Paralinguistic.SIGH, start_time=0.6, intensity=0.5),
        ]
        graph = make_graph(events=events)
        
        result = render_timeline_with_events(graph, speech, adapter, SAMPLE_RATE)
        
        # Should be longer than speech alone
        assert len(result) > len(speech)


class TestEventNeverOverlapsSpeech:
    """Test that events never overlap with speech audio."""
    
    def test_events_are_sequential_not_overlaid(self, temp_audio_assets):
        """Events should be sequential, not mixed with speech."""
        adapter = temp_audio_assets
        
        # Create 1 second of alternating +1/-1 (easy to detect mixing)
        speech = np.ones(SAMPLE_RATE, dtype=np.float32)
        
        event = ParalinguisticEvent(
            type=Paralinguistic.LAUGH,
            start_time=0.0,
            intensity=0.5,
        )
        graph = make_graph(events=[event])
        
        result = render_timeline_with_events(graph, speech, adapter, SAMPLE_RATE)
        
        # The event portion should NOT be mixed with speech
        # (If mixed, values would be different from pure speech or pure event)
        event_pcm = adapter.render(event)
        event_len = len(event_pcm)
        
        # First portion should be event (not ones)
        first_portion = result[:event_len]
        # It should match the event PCM exactly (no mixing)
        assert np.allclose(first_portion, event_pcm, atol=1e-6)
    
    def test_speech_follows_event_without_overlap(self, temp_audio_assets):
        """Speech should start exactly after event ends."""
        adapter = temp_audio_assets
        
        speech = np.ones(SAMPLE_RATE, dtype=np.float32)
        
        event = ParalinguisticEvent(
            type=Paralinguistic.LAUGH,
            start_time=0.0,
            intensity=0.5,
        )
        graph = make_graph(events=[event])
        
        result = render_timeline_with_events(graph, speech, adapter, SAMPLE_RATE)
        
        event_len = len(adapter.render(event))
        
        # After event, should be speech (ones)
        speech_portion = result[event_len:event_len + 1000]
        assert np.allclose(speech_portion, 1.0)


class TestDurationConsistency:
    """Test that event durations match actual WAV durations."""
    
    def test_rendered_duration_matches_manifest(self, temp_audio_assets):
        """Rendered PCM duration should match manifest duration."""
        adapter = temp_audio_assets
        
        # Test all intensity levels
        for intensity in [0.2, 0.5, 0.8]:
            event = ParalinguisticEvent(
                type=Paralinguistic.LAUGH,
                start_time=0.0,
                intensity=intensity,
            )
            
            pcm = adapter.render(event)
            actual_duration = len(pcm) / adapter.sample_rate
            
            # Should match one of the manifest durations (within tolerance)
            # soft=0.18, medium=0.25, hard=0.35
            valid_durations = [0.18, 0.25, 0.35]
            
            matches = any(abs(actual_duration - d) < 0.02 for d in valid_durations)
            assert matches, f"Duration {actual_duration} not in {valid_durations}"
    
    def test_total_timeline_duration_is_predictable(self, temp_audio_assets):
        """Total output duration should be sum of components."""
        adapter = temp_audio_assets
        
        speech_duration = 0.5
        speech = make_pcm(speech_duration)
        
        event = ParalinguisticEvent(
            type=Paralinguistic.LAUGH,
            start_time=0.0,
            intensity=0.5,
        )
        graph = make_graph(events=[event])
        
        event_pcm = adapter.render(event)
        event_duration = len(event_pcm) / SAMPLE_RATE
        
        result = render_timeline_with_events(graph, speech, adapter, SAMPLE_RATE)
        result_duration = len(result) / SAMPLE_RATE
        
        # Should be approximately sum of parts
        expected = event_duration + speech_duration
        assert result_duration == pytest.approx(expected, abs=0.01)


class TestStreamingDeterminism:
    """Test that streaming is deterministic and ordered."""
    
    def test_streaming_order_is_deterministic(self, temp_audio_assets):
        """Multiple stream calls should produce identical order."""
        adapter = temp_audio_assets
        
        speech_chunks = [make_pcm(0.1) for _ in range(5)]
        
        event = ParalinguisticEvent(
            type=Paralinguistic.LAUGH,
            start_time=0.0,
            intensity=0.5,
        )
        graph = make_graph(events=[event])
        
        # Stream twice
        result1 = [len(chunk) for chunk in stream_timeline_with_events(
            graph, iter(speech_chunks), adapter, SAMPLE_RATE
        )]
        
        speech_chunks2 = [make_pcm(0.1) for _ in range(5)]
        result2 = [len(chunk) for chunk in stream_timeline_with_events(
            graph, iter(speech_chunks2), adapter, SAMPLE_RATE
        )]
        
        # Order and sizes should be identical
        assert result1 == result2
    
    def test_event_at_start_yields_first(self, temp_audio_assets):
        """Event at start_time=0 should yield before speech."""
        adapter = temp_audio_assets
        
        speech_chunks = [np.ones(1000, dtype=np.float32) for _ in range(3)]
        
        event = ParalinguisticEvent(
            type=Paralinguistic.LAUGH,
            start_time=0.0,
            intensity=0.5,
        )
        graph = make_graph(events=[event])
        
        chunks = list(stream_timeline_with_events(
            graph, iter(speech_chunks), adapter, SAMPLE_RATE
        ))
        
        # First chunk should be event (not all ones)
        assert len(chunks) > len(speech_chunks)  # Has event
        assert not np.allclose(chunks[0], 1.0)  # First is not speech


class TestNoEventScenarios:
    """Test behavior when no events or no adapter."""
    
    def test_no_events_passes_speech_through(self, temp_audio_assets):
        """Graph without events should return speech unchanged."""
        adapter = temp_audio_assets
        
        speech = make_pcm(1.0)
        graph = make_graph(events=[])
        
        result = render_timeline_with_events(graph, speech, adapter, SAMPLE_RATE)
        
        assert np.array_equal(result, speech)
    
    def test_no_adapter_passes_speech_through(self):
        """No adapter should return speech unchanged."""
        speech = make_pcm(1.0)
        
        event = ParalinguisticEvent(
            type=Paralinguistic.LAUGH,
            start_time=0.0,
            intensity=0.5,
        )
        graph = make_graph(events=[event])
        
        result = render_timeline_with_events(graph, speech, None, SAMPLE_RATE)
        
        assert np.array_equal(result, speech)
    
    def test_unsupported_event_skipped(self, temp_audio_assets):
        """Events not in manifest should be skipped gracefully."""
        adapter = temp_audio_assets
        
        speech = make_pcm(0.5)
        
        # YAWN is not in our test manifest
        event = ParalinguisticEvent(
            type=Paralinguistic.YAWN,
            start_time=0.0,
            intensity=0.5,
        )
        graph = make_graph(events=[event])
        
        result = render_timeline_with_events(graph, speech, adapter, SAMPLE_RATE)
        
        # Should just pass through speech (event skipped)
        assert np.array_equal(result, speech)


class TestSampleRateMismatch:
    """Test behavior when sample rates don't match."""
    
    def test_mismatched_rate_skips_events(self, temp_audio_assets):
        """Sample rate mismatch should skip events safely."""
        adapter = temp_audio_assets  # 24000 Hz
        
        speech = make_pcm(0.5)
        
        event = ParalinguisticEvent(
            type=Paralinguistic.LAUGH,
            start_time=0.0,
            intensity=0.5,
        )
        graph = make_graph(events=[event])
        
        # Pass wrong sample rate
        result = render_timeline_with_events(graph, speech, adapter, 22050)
        
        # Should return speech unchanged (events skipped)
        assert np.array_equal(result, speech)


# Fixture for temp audio assets
@pytest.fixture
def temp_audio_assets(tmp_path):
    """Create temporary audio assets for testing."""
    import json
    import wave
    
    def create_wav(path, duration, sample_rate=24000):
        path.parent.mkdir(parents=True, exist_ok=True)
        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(audio.tobytes())
    
    # Create test WAVs
    create_wav(tmp_path / "laugh" / "soft.wav", 0.18)
    create_wav(tmp_path / "laugh" / "medium.wav", 0.25)
    create_wav(tmp_path / "laugh" / "hard.wav", 0.35)
    create_wav(tmp_path / "sigh" / "short.wav", 0.4)
    
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
    
    manifest_path = tmp_path / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)
    
    from voice_soundboard.adapters.audio_events import AudioEventAdapter
    return AudioEventAdapter.from_manifest(manifest_path)
