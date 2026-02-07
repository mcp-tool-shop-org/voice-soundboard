"""
Property-Based Timeline Tests - Invariants across random timelines.

Uses Hypothesis to generate hundreds of random timelines and verify
that timeline invariants hold in all cases. This is where subtle bugs die.

Invariants tested:
    1. No overlap ever - each item starts >= previous end
    2. Total duration is bounded (no runaway inflation)
    3. Determinism - identical input → identical output
    4. Ordering preserved - output order matches input order
    5. Event atomicity - events appear whole in output
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from voice_soundboard.runtime.timeline import (
    Event,
    Token,
    Pause,
    StreamItem,
    stream_timeline,
    total_duration_ms,
    validate_no_overlap,
)


# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Strategy for generating events
event_strategy = st.builds(
    Event,
    type=st.sampled_from(["laugh", "sigh", "breath", "gasp", "cry", "cough"]),
    duration=st.floats(min_value=0.05, max_value=1.0),
    intensity=st.floats(min_value=0.0, max_value=1.0),
)

# Strategy for generating tokens
token_strategy = st.builds(
    Token,
    text=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
    duration=st.floats(min_value=0.05, max_value=1.0),
)

# Strategy for generating pauses
pause_strategy = st.builds(
    Pause,
    duration=st.floats(min_value=0.05, max_value=0.5),
)

# Strategy for generating any timeline item
timeline_item_strategy = st.one_of(event_strategy, token_strategy, pause_strategy)

# Strategy for generating complete timelines
timeline_strategy = st.lists(
    timeline_item_strategy,
    min_size=0,
    max_size=20,
)


# =============================================================================
# Property Tests - Invariants
# =============================================================================

class TestNoOverlap:
    """Property: No items ever overlap in time."""
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_no_overlap_any_timeline(self, timeline):
        """Items never overlap across any random timeline."""
        stream = list(stream_timeline(timeline))
        
        if not stream:
            return  # Empty is valid
        
        cursor = 0.0
        for item in stream:
            assert item.start >= cursor - 1e-9, (
                f"Overlap: item starts at {item.start}, but cursor at {cursor}"
            )
            cursor = item.end
    
    @given(timeline_strategy)
    @settings(max_examples=100)
    def test_validate_no_overlap_passes(self, timeline):
        """validate_no_overlap helper always passes for valid streams."""
        stream = list(stream_timeline(timeline))
        if stream:
            assert validate_no_overlap(stream)


class TestDurationBounds:
    """Property: Total duration is bounded and predictable."""
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_no_duration_inflation(self, timeline):
        """Duration never exceeds sum of input durations (plus margin).
        
        Some pauses may be absorbed, so output can be <= input.
        But output should never significantly exceed input.
        """
        stream = list(stream_timeline(timeline))
        
        # Calculate max possible duration (all items, no absorption)
        max_expected = sum(
            item.duration for item in timeline
            if not isinstance(item, Pause) or True  # Count pauses
        )
        
        actual = sum(item.duration for item in stream)
        
        # Allow small float tolerance, but no unbounded growth
        assert actual <= max_expected + 0.001, (
            f"Duration inflation: actual={actual}, max_expected={max_expected}"
        )
    
    @given(timeline_strategy)
    @settings(max_examples=100)
    def test_duration_non_negative(self, timeline):
        """All durations are non-negative."""
        stream = list(stream_timeline(timeline))
        
        for item in stream:
            assert item.duration >= 0, f"Negative duration: {item.duration}"
            assert item.start >= 0, f"Negative start: {item.start}"


class TestDeterminism:
    """Property: Identical input produces identical output."""
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_deterministic_output(self, timeline):
        """Same timeline always produces same stream."""
        s1 = list(stream_timeline(timeline))
        s2 = list(stream_timeline(timeline))
        
        # Same length
        assert len(s1) == len(s2)
        
        # Same items
        for i1, i2 in zip(s1, s2):
            assert i1.kind == i2.kind
            assert i1.duration == i2.duration
            assert i1.start == i2.start
    
    @given(timeline_strategy, st.integers(min_value=1, max_value=5))
    @settings(max_examples=50)
    def test_deterministic_multiple_runs(self, timeline, n_runs):
        """Multiple runs produce identical results."""
        results = [
            [(i.kind, i.duration, i.start) for i in stream_timeline(timeline)]
            for _ in range(n_runs)
        ]
        
        # All runs identical
        first = results[0]
        for result in results[1:]:
            assert result == first


class TestOrdering:
    """Property: Output ordering matches input ordering."""
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_event_order_preserved(self, timeline):
        """Events appear in same order as input."""
        stream = list(stream_timeline(timeline))
        
        # Extract events from input
        input_events = [
            (item.type, item.duration)
            for item in timeline
            if isinstance(item, Event)
        ]
        
        # Extract events from output
        output_events = [
            (item.event_type, item.duration)
            for item in stream
            if item.kind == "event"
        ]
        
        assert input_events == output_events
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_token_order_preserved(self, timeline):
        """Tokens appear in same order as input."""
        stream = list(stream_timeline(timeline))
        
        # Extract tokens from input
        input_tokens = [
            (item.text, item.duration)
            for item in timeline
            if isinstance(item, Token)
        ]
        
        # Extract tokens from output
        output_tokens = [
            (item.text, item.duration)
            for item in stream
            if item.kind == "speech"
        ]
        
        assert input_tokens == output_tokens


class TestEventAtomicity:
    """Property: Events are atomic - they appear whole in output."""
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_event_duration_unchanged(self, timeline):
        """Event durations are not modified."""
        stream = list(stream_timeline(timeline))
        
        input_event_durations = {
            (item.type, item.duration)
            for item in timeline
            if isinstance(item, Event)
        }
        
        output_event_durations = {
            (item.event_type, item.duration)
            for item in stream
            if item.kind == "event"
        }
        
        assert input_event_durations == output_event_durations
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_all_events_present(self, timeline):
        """All input events appear in output."""
        input_event_count = sum(1 for item in timeline if isinstance(item, Event))
        output_event_count = sum(1 for item in stream_timeline(timeline) if item.kind == "event")
        
        assert input_event_count == output_event_count


class TestSpeechPreservation:
    """Property: Speech tokens are fully preserved."""
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_all_tokens_present(self, timeline):
        """All input tokens appear in output."""
        input_token_count = sum(1 for item in timeline if isinstance(item, Token))
        output_speech_count = sum(1 for item in stream_timeline(timeline) if item.kind == "speech")
        
        assert input_token_count == output_speech_count
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_token_duration_unchanged(self, timeline):
        """Token durations are not modified."""
        input_durations = sorted(item.duration for item in timeline if isinstance(item, Token))
        output_durations = sorted(item.duration for item in stream_timeline(timeline) if item.kind == "speech")
        
        assert input_durations == output_durations


class TestPauseSemantics:
    """Property: Pause absorption follows rules."""
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_pauses_never_in_output(self, timeline):
        """Pauses don't appear as stream items (they affect cursor only)."""
        stream = list(stream_timeline(timeline))
        
        for item in stream:
            assert item.kind in ("event", "speech"), (
                f"Unexpected kind in stream: {item.kind}"
            )
    
    @given(timeline_strategy)
    @settings(max_examples=100)
    def test_pause_after_event_absorbed(self, timeline):
        """A pause immediately after an event is absorbed.
        
        This is hard to test generically, but we can verify the cursor
        positioning is correct.
        """
        stream = list(stream_timeline(timeline))
        
        # Just verify stream is valid (detailed tests in golden)
        if stream:
            for item in stream:
                assert item.duration >= 0


class TestTimelineLength:
    """Property: Timeline length relationships."""
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_output_length_bounded(self, timeline):
        """Output length is bounded by input event + token count."""
        max_output = sum(
            1 for item in timeline
            if isinstance(item, (Event, Token))
        )
        
        actual_output = len(list(stream_timeline(timeline)))
        
        assert actual_output <= max_output
    
    @given(st.lists(pause_strategy, min_size=0, max_size=10))
    @settings(max_examples=50)
    def test_empty_input_empty_output(self, pauses):
        """Timeline with only pauses produces empty stream."""
        stream = list(stream_timeline(pauses))
        assert stream == []


class TestMonotonicity:
    """Property: Time is monotonically increasing."""
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_start_times_monotonic(self, timeline):
        """Start times are monotonically non-decreasing."""
        stream = list(stream_timeline(timeline))
        
        if not stream:
            return
        
        for i in range(1, len(stream)):
            assert stream[i].start >= stream[i-1].start, (
                f"Non-monotonic: {stream[i].start} < {stream[i-1].start}"
            )
    
    @given(timeline_strategy)
    @settings(max_examples=200)
    def test_end_times_monotonic(self, timeline):
        """End times are monotonically non-decreasing."""
        stream = list(stream_timeline(timeline))
        
        if not stream:
            return
        
        for i in range(1, len(stream)):
            assert stream[i].end >= stream[i-1].end, (
                f"Non-monotonic ends: {stream[i].end} < {stream[i-1].end}"
            )


# =============================================================================
# Stress Tests
# =============================================================================

class TestStress:
    """Stress tests with extreme inputs."""
    
    @given(st.lists(event_strategy, min_size=50, max_size=100))
    @settings(max_examples=20)
    def test_many_events(self, events):
        """Handle timeline with many events."""
        stream = list(stream_timeline(events))
        
        assert len(stream) == len(events)
        validate_no_overlap(stream)
    
    @given(st.lists(token_strategy, min_size=50, max_size=100))
    @settings(max_examples=20)
    def test_many_tokens(self, tokens):
        """Handle timeline with many tokens."""
        stream = list(stream_timeline(tokens))
        
        assert len(stream) == len(tokens)
        validate_no_overlap(stream)
    
    @given(st.lists(pause_strategy, min_size=50, max_size=100))
    @settings(max_examples=20)
    def test_many_pauses(self, pauses):
        """Timeline with only pauses produces empty stream."""
        stream = list(stream_timeline(pauses))
        assert stream == []
    
    @given(
        st.lists(
            st.one_of(event_strategy, token_strategy),
            min_size=100,
            max_size=200,
        )
    )
    @settings(max_examples=10)
    def test_long_mixed_timeline(self, timeline):
        """Handle very long mixed timeline."""
        stream = list(stream_timeline(timeline))
        
        assert len(stream) == len(timeline)
        validate_no_overlap(stream)
