"""
Golden Timeline Tests - Exact millisecond expectations.

These tests lock in guarantees with exact timing assertions:
- "This timeline must produce exactly 1250 ms of audio"
- "Speech resumes at exactly T = X ms after a sigh"

Golden tests are the regression firewall. If one fails, something is
fundamentally wrong with timeline semantics.

Design principles:
- Test exact ms values, not just ordering
- Test event/pause replacement semantics
- Test complex multi-event sequences
- Each test is a regression lock
"""

import pytest

from voice_soundboard.runtime.timeline import (
    Event,
    Token,
    Pause,
    StreamItem,
    stream_timeline,
    total_duration_ms,
)


class TestGoldenSimple:
    """Simple golden tests for basic timeline semantics."""
    
    def test_golden_laugh_then_word(self):
        """Laugh before speech: 250ms + 400ms = 650ms total."""
        timeline = [
            Event("laugh", duration=0.25),
            Token("hello", duration=0.40),
        ]
        
        stream = list(stream_timeline(timeline))
        
        # Exact total duration
        assert total_duration_ms(stream) == 650
        
        # Exact item details
        assert len(stream) == 2
        
        assert stream[0].kind == "event"
        assert int(stream[0].duration * 1000) == 250
        assert stream[0].start == 0.0
        
        assert stream[1].kind == "speech"
        assert int(stream[1].duration * 1000) == 400
        # Speech starts exactly after event ends
        assert int(stream[1].start * 1000) == 250
    
    def test_golden_word_then_sigh(self):
        """Speech then sigh: 300ms + 450ms = 750ms total."""
        timeline = [
            Token("okay", duration=0.30),
            Event("sigh", duration=0.45),
        ]
        
        stream = list(stream_timeline(timeline))
        
        assert total_duration_ms(stream) == 750
        assert len(stream) == 2
        
        assert stream[0].kind == "speech"
        assert int(stream[0].duration * 1000) == 300
        
        assert stream[1].kind == "event"
        assert int(stream[1].duration * 1000) == 450
        assert int(stream[1].start * 1000) == 300
    
    def test_golden_only_event(self):
        """Single event: 200ms."""
        timeline = [
            Event("breath", duration=0.20),
        ]
        
        stream = list(stream_timeline(timeline))
        
        assert total_duration_ms(stream) == 200
        assert len(stream) == 1
        assert stream[0].kind == "event"
    
    def test_golden_only_speech(self):
        """Single speech: 500ms."""
        timeline = [
            Token("hello world", duration=0.50),
        ]
        
        stream = list(stream_timeline(timeline))
        
        assert total_duration_ms(stream) == 500
        assert len(stream) == 1
        assert stream[0].kind == "speech"


class TestGoldenPauseReplacement:
    """Golden tests for pause replacement semantics.
    
    Key rule: Pause following an event is REPLACED, not added.
    This prevents double gaps.
    """
    
    def test_golden_sigh_replaces_pause(self):
        """Pause after event is absorbed.
        
        Timeline: [Pause(300), Event(450), Token(350)]
        - Pause(300) adds silence (no preceding event): +300ms
        - Event(450) inserts: +450ms  
        - Token(350) is speech: +350ms
        
        But wait, the spec says pause AFTER event is replaced.
        Let me re-read: "Pauses may be replaced by events (no double gaps)"
        
        Actually: [Pause, Event, Token] - pause comes BEFORE event.
        Let's test the case where pause comes AFTER event.
        """
        timeline = [
            Event("sigh", duration=0.45),
            Pause(duration=0.30),  # This should be absorbed
            Token("okay", duration=0.35),
        ]
        
        stream = list(stream_timeline(timeline))
        
        # Pause is absorbed, so: 450ms + 350ms = 800ms
        assert total_duration_ms(stream) == 800
        
        # Only event and speech in output (pause absorbed)
        assert [s.kind for s in stream] == ["event", "speech"]
        
        assert int(stream[0].duration * 1000) == 450
        assert int(stream[1].duration * 1000) == 350
    
    def test_golden_pause_before_event_not_replaced(self):
        """Pause BEFORE event is NOT absorbed - it adds silence.
        
        Timeline: [Pause(200), Event(300), Token(400)]
        - Pause adds: +200ms (no preceding event)
        - Event inserts: +300ms
        - Token adds: +400ms
        Total: 900ms (but pause doesn't yield a stream item)
        
        Actually, pauses without preceding events add time to cursor
        but don't yield stream items. So stream only has event + speech.
        But duration calculation only counts stream items!
        
        Let me reconsider: if pauses add cursor time but don't yield,
        total_duration_ms only counts event + speech = 700ms.
        But the actual timeline duration would include the pause gap.
        
        For stream items, we count what's yielded. Pauses are implicit.
        """
        timeline = [
            Pause(duration=0.20),
            Event("laugh", duration=0.30),
            Token("hey", duration=0.40),
        ]
        
        stream = list(stream_timeline(timeline))
        
        # Stream items are only event + speech
        assert [s.kind for s in stream] == ["event", "speech"]
        
        # Duration is just event + speech (pause is cursor advancement)
        assert total_duration_ms(stream) == 700
        
        # But positions account for pause:
        # pause advances cursor by 200ms
        # event starts at 200ms
        # speech starts at 200 + 300 = 500ms
        assert int(stream[0].start * 1000) == 200
        assert int(stream[1].start * 1000) == 500
    
    def test_golden_double_event_single_pause(self):
        """Two events with pause between - pause absorbed.
        
        Timeline: [Event1(200), Pause(100), Event2(300), Token(400)]
        - Event1: +200ms
        - Pause: absorbed (following event)
        - Event2: +300ms
        - Token: +400ms
        Total: 900ms
        """
        timeline = [
            Event("laugh", duration=0.20),
            Pause(duration=0.10),  # Absorbed
            Event("sigh", duration=0.30),
            Token("okay", duration=0.40),
        ]
        
        stream = list(stream_timeline(timeline))
        
        assert total_duration_ms(stream) == 900
        assert [s.kind for s in stream] == ["event", "event", "speech"]
        
        # Positions: 0, 200, 500
        assert int(stream[0].start * 1000) == 0
        assert int(stream[1].start * 1000) == 200
        assert int(stream[2].start * 1000) == 500


class TestGoldenComplex:
    """Complex golden tests with multiple events and tokens."""
    
    def test_golden_complex_sequence(self):
        """Multi-event multi-token sequence.
        
        Timeline: [Event(200), Token(300), Event(400), Token(250)]
        - Event1: 200ms at 0
        - Token1: 300ms at 200
        - Event2: 400ms at 500
        - Token2: 250ms at 900
        Total: 1150ms
        """
        timeline = [
            Event("laugh", duration=0.20),
            Token("well", duration=0.30),
            Event("sigh", duration=0.40),
            Token("that", duration=0.25),
        ]
        
        stream = list(stream_timeline(timeline))
        
        assert total_duration_ms(stream) == 1150
        
        expected = [
            ("event", 200, 0),
            ("speech", 300, 200),
            ("event", 400, 500),
            ("speech", 250, 900),
        ]
        
        for item, (kind, ms, start_ms) in zip(stream, expected):
            assert item.kind == kind
            assert int(item.duration * 1000) == ms
            assert int(item.start * 1000) == start_ms
    
    def test_golden_interleaved_events_tokens(self):
        """Alternating events and tokens.
        
        Timeline: [E, T, E, T, E, T]
        Tests proper cursor advancement across many items.
        """
        timeline = [
            Event("breath", duration=0.10),
            Token("one", duration=0.20),
            Event("laugh", duration=0.15),
            Token("two", duration=0.25),
            Event("sigh", duration=0.20),
            Token("three", duration=0.30),
        ]
        
        stream = list(stream_timeline(timeline))
        
        # 100 + 200 + 150 + 250 + 200 + 300 = 1200ms
        assert total_duration_ms(stream) == 1200
        assert len(stream) == 6
        
        # Verify sequence
        expected_kinds = ["event", "speech", "event", "speech", "event", "speech"]
        assert [s.kind for s in stream] == expected_kinds
    
    def test_golden_consecutive_tokens(self):
        """Multiple consecutive tokens (fluent speech).
        
        Timeline: [T, T, T] - no events
        """
        timeline = [
            Token("hello", duration=0.30),
            Token("beautiful", duration=0.40),
            Token("world", duration=0.25),
        ]
        
        stream = list(stream_timeline(timeline))
        
        # 300 + 400 + 250 = 950ms
        assert total_duration_ms(stream) == 950
        
        # All speech
        assert all(s.kind == "speech" for s in stream)
        
        # Sequential positions
        assert int(stream[0].start * 1000) == 0
        assert int(stream[1].start * 1000) == 300
        assert int(stream[2].start * 1000) == 700
    
    def test_golden_consecutive_events(self):
        """Multiple consecutive events (emotional expression).
        
        Timeline: [E, E, E]
        """
        timeline = [
            Event("gasp", duration=0.15),
            Event("laugh", duration=0.30),
            Event("sigh", duration=0.25),
        ]
        
        stream = list(stream_timeline(timeline))
        
        # 150 + 300 + 250 = 700ms
        assert total_duration_ms(stream) == 700
        
        # All events
        assert all(s.kind == "event" for s in stream)
        
        # Sequential positions (with float tolerance)
        assert int(stream[0].start * 1000) == 0
        assert int(stream[1].start * 1000) == 150
        assert abs(stream[2].start * 1000 - 450) < 1  # Float tolerance


class TestGoldenEdgeCases:
    """Edge case golden tests."""
    
    def test_golden_empty_timeline(self):
        """Empty timeline produces empty stream."""
        stream = list(stream_timeline([]))
        assert stream == []
        assert total_duration_ms(stream) == 0
    
    def test_golden_zero_duration_event(self):
        """Zero duration event (edge case - should still be in stream)."""
        timeline = [
            Event("breath", duration=0.0),
            Token("hi", duration=0.30),
        ]
        
        stream = list(stream_timeline(timeline))
        
        # Event still appears, just with 0 duration
        assert len(stream) == 2
        assert total_duration_ms(stream) == 300
    
    def test_golden_very_long_event(self):
        """Very long event (10 seconds)."""
        timeline = [
            Event("dramatic_pause", duration=10.0),
            Token("finally", duration=0.40),
        ]
        
        stream = list(stream_timeline(timeline))
        
        assert total_duration_ms(stream) == 10400
        assert int(stream[1].start * 1000) == 10000
    
    def test_golden_many_pauses_absorbed(self):
        """Multiple consecutive pauses after event all absorbed."""
        timeline = [
            Event("sigh", duration=0.30),
            Pause(duration=0.10),  # Absorbed
            Pause(duration=0.10),  # NOT absorbed - previous item is pause
            Pause(duration=0.10),  # NOT absorbed
            Token("okay", duration=0.50),
        ]
        
        stream = list(stream_timeline(timeline))
        
        # First pause absorbed, next two add cursor time
        # Event: 300ms, Pause1: absorbed, Pause2: +100ms, Pause3: +100ms, Token: 500ms
        # Stream items: event(300) + speech(500) = 800ms
        # But speech starts at 300 + 0 + 100 + 100 = 500ms
        
        assert [s.kind for s in stream] == ["event", "speech"]
        assert total_duration_ms(stream) == 800
        assert int(stream[1].start * 1000) == 500
    
    def test_golden_precise_timing_fractions(self):
        """Test precise fractional timing (no float errors)."""
        timeline = [
            Event("breath", duration=0.123),
            Token("precise", duration=0.456),
        ]
        
        stream = list(stream_timeline(timeline))
        
        # 123 + 456 = 579ms
        assert total_duration_ms(stream) == 579
        assert int(stream[1].start * 1000) == 123


class TestGoldenEventMetadata:
    """Golden tests for event metadata preservation."""
    
    def test_golden_event_type_preserved(self):
        """Event type is preserved in stream."""
        timeline = [
            Event("laugh", duration=0.20),
            Event("sigh", duration=0.30),
        ]
        
        stream = list(stream_timeline(timeline))
        
        assert stream[0].event_type == "laugh"
        assert stream[1].event_type == "sigh"
    
    def test_golden_event_intensity_preserved(self):
        """Event intensity is preserved."""
        timeline = [
            Event("laugh", duration=0.20, intensity=0.5),
            Event("sigh", duration=0.30, intensity=0.8),
        ]
        
        stream = list(stream_timeline(timeline))
        
        assert stream[0].intensity == 0.5
        assert stream[1].intensity == 0.8
    
    def test_golden_token_text_preserved(self):
        """Token text is preserved in stream."""
        timeline = [
            Token("hello", duration=0.30),
            Token("world", duration=0.25),
        ]
        
        stream = list(stream_timeline(timeline))
        
        assert stream[0].text == "hello"
        assert stream[1].text == "world"
