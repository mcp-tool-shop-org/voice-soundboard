"""Tests for the accessibility module."""

from types import SimpleNamespace

from voice_soundboard.accessibility.bridge import (
    AccessibilityBridge,
    AccessibilityConfig,
    Announcement,
    AnnouncementPriority,
)
from voice_soundboard.accessibility.captions import (
    Caption,
    CaptionConfig,
    CaptionFormat,
    CaptionGenerator,
    LiveCaptions,
    TranscriptExporter,
)
from voice_soundboard.accessibility.cognitive import (
    ConsistencyConfig,
    ConsistencyGuard,
    PlainLanguage,
    PlainLanguageConfig,
)
from voice_soundboard.accessibility.descriptions import (
    AudioDescriber,
    Description,
    DescriptionStyle,
    DescriptionTrack,
)
from voice_soundboard.accessibility.motor import (
    ReducedInteraction,
    SwitchControl,
    VoiceCommands,
)
from voice_soundboard.accessibility.navigation import (
    AudioLandmarks,
    DocumentStructure,
    Landmark,
    LandmarkType,
    TableNavigator,
    TableNavigatorConfig,
)
from voice_soundboard.accessibility.visual import (
    ColorScheme,
    HapticConfig,
    HapticFeedback,
    HapticPattern,
    IndicatorConfig,
    SpeechIndicator,
    VisualizationStyle,
    VisualizerConfig,
    WaveformVisualizer,
)
from voice_soundboard.accessibility.testing import (
    AccessibilityAuditor,
    AuditReport,
    AuditResult,
    AuditSeverity,
    ScreenReaderTest,
    UserTestSession,
)
from voice_soundboard.accessibility.screen_readers.base import (
    NullScreenReaderAdapter,
    ScreenReaderAdapter,
    ScreenReaderCapabilities,
    ScreenReaderMode,
)
from voice_soundboard.accessibility.screen_readers.detection import (
    get_adapter_for_mode,
    get_available_adapters,
)


# ---------------------------------------------------------------------------
# Mock adapter for tests that need a real adapter without a real screen reader
# ---------------------------------------------------------------------------

class MockScreenReaderAdapter(ScreenReaderAdapter):
    """Fake adapter that records calls instead of talking to AT."""

    def __init__(self, active: bool = True):
        self._active = active
        self.spoken: list[tuple[str, bool]] = []
        self.ducked: float | None = None

    @property
    def name(self) -> str:
        return "MockReader"

    @property
    def is_active(self) -> bool:
        return self._active

    def speak(self, text: str, interrupt: bool = False) -> None:
        self.spoken.append((text, interrupt))

    def duck(self, amount: float = 0.3) -> None:
        self.ducked = amount

    def unduck(self) -> None:
        self.ducked = None


# ===================================================================
# AccessibilityBridge
# ===================================================================

class TestAnnouncementDataclass:
    """Tests for the Announcement dataclass and its defaults."""

    def test_defaults(self):
        ann = Announcement(text="hello")
        assert ann.text == "hello"
        assert ann.priority == AnnouncementPriority.POLITE
        assert ann.clear_queue is False
        assert ann.language is None
        assert ann.source is None

    def test_explicit_priority(self):
        ann = Announcement(text="urgent", priority=AnnouncementPriority.ASSERTIVE)
        assert ann.priority == AnnouncementPriority.ASSERTIVE


class TestAccessibilityConfig:
    """Tests for AccessibilityConfig defaults."""

    def test_defaults(self):
        cfg = AccessibilityConfig()
        assert cfg.auto_detect_screen_reader is True
        assert cfg.announce_progress is True
        assert cfg.progress_interval_percent == 25
        assert cfg.duck_screen_reader is True
        assert cfg.duck_amount == 0.3
        assert cfg.default_priority == AnnouncementPriority.POLITE
        assert cfg.announcement_prefix == ""
        assert cfg.announcement_suffix == ""
        assert cfg.min_announcement_gap_ms == 250
        assert cfg.announcement_timeout_ms == 10000


class TestAccessibilityBridge:
    """Tests for AccessibilityBridge core behaviour."""

    def test_create_with_defaults(self):
        bridge = AccessibilityBridge(
            config=AccessibilityConfig(auto_detect_screen_reader=False),
        )
        assert bridge.screen_reader_active is False
        assert bridge.screen_reader_name is None

    def test_create_with_mock_adapter(self):
        adapter = MockScreenReaderAdapter(active=True)
        bridge = AccessibilityBridge(adapter=adapter)
        assert bridge.screen_reader_active is True
        assert bridge.screen_reader_name == "MockReader"

    def test_inactive_adapter(self):
        adapter = MockScreenReaderAdapter(active=False)
        bridge = AccessibilityBridge(adapter=adapter)
        assert bridge.screen_reader_active is False

    def test_announce_delivers_to_adapter(self):
        adapter = MockScreenReaderAdapter()
        bridge = AccessibilityBridge(adapter=adapter)
        bridge.announce("Hello")
        assert len(adapter.spoken) == 1
        assert adapter.spoken[0][0] == "Hello"
        assert adapter.spoken[0][1] is False  # not interrupt

    def test_announce_assertive_interrupts(self):
        adapter = MockScreenReaderAdapter()
        bridge = AccessibilityBridge(adapter=adapter)
        bridge.announce("Alert!", priority=AnnouncementPriority.ASSERTIVE)
        assert adapter.spoken[0][1] is True  # interrupt

    def test_announce_off_not_delivered(self):
        adapter = MockScreenReaderAdapter()
        bridge = AccessibilityBridge(adapter=adapter)
        bridge.announce("hidden", priority=AnnouncementPriority.OFF)
        assert len(adapter.spoken) == 0

    def test_announce_prefix_suffix(self):
        adapter = MockScreenReaderAdapter()
        cfg = AccessibilityConfig(
            announcement_prefix="[VS] ",
            announcement_suffix=" (done)",
        )
        bridge = AccessibilityBridge(config=cfg, adapter=adapter)
        bridge.announce("test")
        assert adapter.spoken[0][0] == "[VS] test (done)"

    def test_clear_queue(self):
        adapter = MockScreenReaderAdapter()
        bridge = AccessibilityBridge(adapter=adapter)
        bridge.announce("one")
        bridge.announce("two")
        bridge.announce("clear!", clear_queue=True)
        # The internal queue should only have the last announcement
        assert len(bridge._announcement_queue) == 1
        assert bridge._announcement_queue[0].text == "clear!"

    def test_listener_receives_announcements(self):
        heard = []

        class Listener:
            def on_announcement(self, announcement):
                heard.append(announcement.text)

            def on_synthesis_start(self, text):
                pass

            def on_synthesis_end(self, duration_ms):
                pass

        adapter = MockScreenReaderAdapter()
        bridge = AccessibilityBridge(adapter=adapter)
        bridge.add_listener(Listener())
        bridge.announce("ping")
        assert heard == ["ping"]

    def test_remove_listener(self):
        heard = []

        class Listener:
            def on_announcement(self, announcement):
                heard.append(announcement.text)

            def on_synthesis_start(self, text):
                pass

            def on_synthesis_end(self, duration_ms):
                pass

        adapter = MockScreenReaderAdapter()
        bridge = AccessibilityBridge(adapter=adapter)
        listener = Listener()
        bridge.add_listener(listener)
        bridge.remove_listener(listener)
        bridge.announce("no-one listening")
        assert heard == []

    def test_listener_error_does_not_break_announce(self):
        class BadListener:
            def on_announcement(self, announcement):
                raise RuntimeError("boom")

            def on_synthesis_start(self, text):
                pass

            def on_synthesis_end(self, duration_ms):
                pass

        adapter = MockScreenReaderAdapter()
        bridge = AccessibilityBridge(adapter=adapter)
        bridge.add_listener(BadListener())
        bridge.announce("still works")
        assert len(adapter.spoken) == 1

    def test_synthesis_start_ducks(self):
        adapter = MockScreenReaderAdapter()
        bridge = AccessibilityBridge(adapter=adapter)
        bridge.on_synthesis_start("hello")
        assert adapter.ducked == 0.3

    def test_synthesis_end_unducks(self):
        adapter = MockScreenReaderAdapter()
        bridge = AccessibilityBridge(adapter=adapter)
        bridge.on_synthesis_start("hello")
        bridge.on_synthesis_end(500.0)
        assert adapter.ducked is None

    def test_progress_announcement(self):
        adapter = MockScreenReaderAdapter()
        bridge = AccessibilityBridge(adapter=adapter)
        bridge.on_progress(25)
        assert any("25%" in text for text, _ in adapter.spoken)

    def test_progress_not_at_zero_or_100(self):
        adapter = MockScreenReaderAdapter()
        bridge = AccessibilityBridge(adapter=adapter)
        bridge.on_progress(0)
        bridge.on_progress(100)
        assert len(adapter.spoken) == 0

    def test_progress_disabled(self):
        adapter = MockScreenReaderAdapter()
        cfg = AccessibilityConfig(announce_progress=False)
        bridge = AccessibilityBridge(config=cfg, adapter=adapter)
        bridge.on_progress(50)
        assert len(adapter.spoken) == 0


# ===================================================================
# Screen Reader Detection / Adapters
# ===================================================================

class TestNullScreenReaderAdapter:
    """Tests for the no-op adapter."""

    def test_name(self):
        assert NullScreenReaderAdapter().name == "None"

    def test_inactive(self):
        assert NullScreenReaderAdapter().is_active is False

    def test_speak_noop(self):
        NullScreenReaderAdapter().speak("hello")  # should not raise

    def test_capabilities_defaults(self):
        caps = ScreenReaderCapabilities()
        assert caps.can_speak is True
        assert caps.can_interrupt is True
        assert caps.supports_braille is False


class TestScreenReaderDetection:
    """Tests for detection helpers (no real screen readers needed)."""

    def test_get_available_adapters_returns_list(self):
        adapters = get_available_adapters()
        assert isinstance(adapters, list)

    def test_none_mode_returns_null_adapter(self):
        adapter = get_adapter_for_mode(ScreenReaderMode.NONE)
        assert adapter is not None
        assert adapter.is_active is False
        assert adapter.name == "None"

    def test_screen_reader_mode_enum(self):
        assert ScreenReaderMode.AUTO is not None
        assert ScreenReaderMode.NVDA is not None
        assert ScreenReaderMode.NONE is not None


# ===================================================================
# CaptionGenerator
# ===================================================================

class TestCaptionDataclass:
    """Tests for Caption and CaptionConfig defaults."""

    def test_caption_defaults(self):
        cap = Caption(text="hi", start_time=0.0, end_time=1.0)
        assert cap.speaker is None
        assert cap.style is None

    def test_caption_config_defaults(self):
        cfg = CaptionConfig()
        assert cfg.format == CaptionFormat.WEBVTT
        assert cfg.max_line_length == 42
        assert cfg.max_lines == 2
        assert cfg.position == "bottom"


class TestCaptionGenerator:
    """Tests for CaptionGenerator output."""

    def test_generate_from_text_webvtt(self):
        gen = CaptionGenerator()
        result = gen.generate_from_text("Hello world", duration_ms=2000)
        assert result.startswith("WEBVTT")
        assert "Hello world" in result
        assert "-->" in result

    def test_generate_from_text_srt(self):
        cfg = CaptionConfig(format=CaptionFormat.SRT)
        gen = CaptionGenerator(config=cfg)
        result = gen.generate_from_text("Hello world", duration_ms=2000)
        assert "WEBVTT" not in result
        assert "-->" in result

    def test_generate_from_text_ttml(self):
        cfg = CaptionConfig(format=CaptionFormat.TTML)
        gen = CaptionGenerator(config=cfg)
        result = gen.generate_from_text("Hello world", duration_ms=2000)
        assert "<tt" in result
        assert "Hello world" in result

    def test_generate_from_text_with_speaker(self):
        gen = CaptionGenerator()
        result = gen.generate_from_text("Hi", duration_ms=1000, speaker="Alice")
        assert "Alice" in result

    def test_generate_from_text_empty(self):
        gen = CaptionGenerator()
        result = gen.generate_from_text("", duration_ms=1000)
        # Should produce valid VTT header with no cues
        assert result.startswith("WEBVTT")

    def test_generate_extracts_from_result_object(self):
        gen = CaptionGenerator()
        fake_result = SimpleNamespace(text="Test caption", duration_ms=500)
        output = gen.generate(fake_result)
        assert "Test caption" in output

    def test_srt_time_format(self):
        gen = CaptionGenerator()
        formatted = gen._format_srt_time(3661.5)
        assert formatted == "01:01:01,500"

    def test_vtt_time_format(self):
        gen = CaptionGenerator()
        formatted = gen._format_vtt_time(3661.5)
        assert formatted == "01:01:01.500"


class TestLiveCaptions:
    """Tests for LiveCaptions."""

    def test_defaults(self):
        lc = LiveCaptions()
        assert lc.display == "overlay"
        assert lc.font_size == "medium"
        assert lc.get_current() == ""

    def test_update_with_text_chunk(self):
        lc = LiveCaptions()
        chunk = SimpleNamespace(text="Hello")
        lc.update(chunk)
        assert lc.get_current() == "Hello"

    def test_speaker_label(self):
        lc = LiveCaptions(speaker_labels=True)
        lc.set_speaker("Bob")
        chunk = SimpleNamespace(text="Hi there")
        lc.update(chunk)
        assert lc.get_current() == "Bob: Hi there"

    def test_clear(self):
        lc = LiveCaptions()
        lc.update(SimpleNamespace(text="something"))
        lc.clear()
        assert lc.get_current() == ""


class TestTranscriptExporter:
    """Tests for TranscriptExporter."""

    def _make_conversation(self):
        turn1 = SimpleNamespace(speaker="Alice", text="Hello", timestamp=0.0)
        turn2 = SimpleNamespace(speaker="Bob", text="Hi", timestamp=5.0)
        return SimpleNamespace(turns=[turn1, turn2])

    def test_export_markdown(self):
        exporter = TranscriptExporter(format="markdown")
        result = exporter.export(self._make_conversation())
        assert "# Transcript" in result
        assert "Alice" in result
        assert "Bob" in result

    def test_export_html(self):
        exporter = TranscriptExporter(format="html")
        result = exporter.export(self._make_conversation())
        assert "<html>" in result
        assert "Alice" in result

    def test_export_txt(self):
        exporter = TranscriptExporter(format="txt")
        result = exporter.export(self._make_conversation())
        assert "TRANSCRIPT" in result
        assert "Alice: Hello" in result


# ===================================================================
# Cognitive Accessibility
# ===================================================================

class TestPlainLanguage:
    """Tests for PlainLanguage jargon replacement and readability."""

    def test_jargon_replacement(self):
        pl = PlainLanguage()
        result = pl.transform("We need to utilize synergy")
        assert "use" in result
        assert "teamwork" in result

    def test_capitalize_replacement(self):
        pl = PlainLanguage()
        result = pl.transform("Leverage this result")
        assert result.startswith("Use")

    def test_no_jargon_mode(self):
        cfg = PlainLanguageConfig(avoid_jargon=False)
        pl = PlainLanguage(config=cfg)
        result = pl.transform("utilize leverage")
        assert "utilize" in result

    def test_assess_readability(self):
        pl = PlainLanguage()
        metrics = pl.assess_readability("The cat sat on the mat.")
        assert "word_count" in metrics
        assert metrics["word_count"] == 6
        assert "estimated_grade_level" in metrics


class TestConsistencyGuard:
    """Tests for ConsistencyGuard."""

    def test_announce_change(self):
        guard = ConsistencyGuard()
        guard.announce_change("Voice changed")
        pending = guard.get_pending_announcements()
        assert pending == ["Voice changed"]
        # second call should be empty (consumed)
        assert guard.get_pending_announcements() == []

    def test_should_confirm_destructive(self):
        guard = ConsistencyGuard()
        assert guard.should_confirm("delete") is True
        assert guard.should_confirm("clear") is True
        assert guard.should_confirm("play") is False

    def test_timeout_warning(self):
        guard = ConsistencyGuard()
        assert guard.timeout_warning_needed(29) is False
        assert guard.timeout_warning_needed(30) is True

    def test_disabled_announcements(self):
        cfg = ConsistencyConfig(announce_changes=False)
        guard = ConsistencyGuard(config=cfg)
        guard.announce_change("ignored")
        assert guard.get_pending_announcements() == []


# ===================================================================
# Audio Descriptions
# ===================================================================

class TestDescriptionTrack:
    """Tests for DescriptionTrack ordering and lookup."""

    def test_add_and_sort(self):
        track = DescriptionTrack()
        track.add(5.0, "second").add(1.0, "first")
        descs = track.get_descriptions()
        assert descs[0].text == "first"
        assert descs[1].text == "second"

    def test_at_time(self):
        track = DescriptionTrack()
        track.add(3.0, "match")
        assert track.at_time(3.2, tolerance=0.5) is not None
        assert track.at_time(10.0, tolerance=0.5) is None

    def test_to_srt(self):
        track = DescriptionTrack()
        track.add(0.0, "Opening scene")
        srt = track.to_srt()
        assert "Opening scene" in srt
        assert "-->" in srt

    def test_chaining(self):
        track = DescriptionTrack()
        result = track.add(0.0, "a").add(1.0, "b").add(2.0, "c")
        assert result is track
        assert len(track.descriptions) == 3


class TestAudioDescriber:
    """Tests for AudioDescriber basics."""

    def test_defaults(self):
        describer = AudioDescriber()
        assert describer.config.style == DescriptionStyle.DESCRIPTIVE
        assert describer.model == "auto"

    def test_describe_image_placeholder(self):
        describer = AudioDescriber()
        desc = describer.describe_image("test.png")
        assert isinstance(desc, Description)
        assert "test.png" in desc.text


# ===================================================================
# Motor Accessibility
# ===================================================================

class TestVoiceCommands:
    """Tests for VoiceCommands registration and lookup."""

    def test_register_and_list(self):
        vc = VoiceCommands()
        vc.register("stop", lambda: None)
        vc.register("play", lambda: None)
        assert "stop" in vc.get_commands()
        assert "play" in vc.get_commands()

    def test_unregister(self):
        vc = VoiceCommands()
        vc.register("stop", lambda: None)
        vc.unregister("stop")
        assert "stop" not in vc.get_commands()

    def test_decorator(self):
        vc = VoiceCommands()

        @vc.command("greet")
        def greet():
            pass

        assert "greet" in vc.get_commands()

    def test_start_stop(self):
        vc = VoiceCommands()
        assert vc.is_listening is False
        vc.start()
        assert vc.is_listening is True
        vc.stop()
        assert vc.is_listening is False


class TestSwitchControl:
    """Tests for SwitchControl scanning interface."""

    def test_add_actions(self):
        sc = SwitchControl()
        sc.add_action("Play", lambda: None)
        sc.add_action("Stop", lambda: None)
        assert sc.actions == ["Play", "Stop"]

    def test_navigation(self):
        sc = SwitchControl()
        sc.add_action("A", lambda: None)
        sc.add_action("B", lambda: None)
        sc.add_action("C", lambda: None)
        sc.start()
        assert sc.current_action == "A"
        assert sc.next() == "B"
        assert sc.next() == "C"
        # wraps around
        assert sc.next() == "A"

    def test_previous(self):
        sc = SwitchControl()
        sc.add_action("A", lambda: None)
        sc.add_action("B", lambda: None)
        sc.start()
        # wraps backward
        name = sc.previous()
        assert name == "B"

    def test_select_calls_callback(self):
        called = []
        sc = SwitchControl()
        sc.add_action("Go", lambda: called.append(True))
        sc.start()
        sc.select()
        assert called == [True]

    def test_remove_action(self):
        sc = SwitchControl()
        sc.add_action("X", lambda: None)
        sc.remove_action("X")
        assert sc.actions == []

    def test_chaining(self):
        sc = SwitchControl()
        result = sc.add_action("A", lambda: None)
        assert result is sc

    def test_empty_next_returns_none(self):
        sc = SwitchControl()
        assert sc.next() is None


class TestReducedInteraction:
    """Tests for ReducedInteraction."""

    def test_defaults(self):
        ri = ReducedInteraction()
        assert ri.auto_play is True
        assert ri.large_targets is True
        assert ri.dwell_time_ms == 1000

    def test_should_confirm(self):
        ri = ReducedInteraction()
        assert ri.should_confirm("delete") is True
        assert ri.should_confirm("play") is False


# ===================================================================
# Navigation
# ===================================================================

class TestAudioLandmarks:
    """Tests for AudioLandmarks parsing and navigation."""

    def test_parse_markdown_headings(self):
        content = "# Title\nSome text\n## Section\nMore text"
        lm = AudioLandmarks()
        landmarks = lm.parse_content(content)
        headings = [lm_item for lm_item in landmarks if lm_item.type == LandmarkType.HEADING]
        assert len(headings) == 2
        assert headings[0].text == "Title"
        assert headings[1].text == "Section"

    def test_next_landmark(self):
        lm = AudioLandmarks()
        lm.parse_content("# A\n## B\n## C")
        first = lm.next_landmark()
        assert first is not None
        assert first.text == "A"
        second = lm.next_landmark()
        assert second.text == "B"

    def test_next_landmark_with_filter(self):
        lm = AudioLandmarks()
        lm.parse_content("# Heading\n- list item")
        result = lm.next_landmark(type_filter=LandmarkType.LIST)
        assert result is not None
        assert result.type == LandmarkType.LIST

    def test_earcon_lookup(self):
        lm = AudioLandmarks()
        landmark = Landmark(type=LandmarkType.HEADING, text="Test")
        earcon = lm.get_earcon(landmark)
        assert earcon == "chime_up.wav"

    def test_announce_with_level(self):
        lm = AudioLandmarks()
        landmark = Landmark(type=LandmarkType.HEADING, text="Intro", level=2)
        text = lm.announce(landmark)
        assert "Heading" in text
        assert "level 2" in text
        assert "Intro" in text


class TestTableNavigator:
    """Tests for TableNavigator."""

    def _make_table(self):
        return [
            ["Name", "Age", "City"],
            ["Alice", "30", "NYC"],
            ["Bob", "25", "LA"],
        ]

    def test_load_and_current_cell(self):
        nav = TableNavigator()
        nav.load(self._make_table())
        # With header row, starts at row 1, col 0
        assert nav.current_cell == "Alice"

    def test_move_right(self):
        nav = TableNavigator()
        nav.load(self._make_table())
        result = nav.move_right()
        assert "30" in result
        assert nav.current_position == (1, 1)

    def test_move_down(self):
        nav = TableNavigator()
        nav.load(self._make_table())
        result = nav.move_down()
        assert "Bob" in result

    def test_wrap_navigation(self):
        nav = TableNavigator()
        nav.load(self._make_table())
        nav.move_right()  # Age
        nav.move_right()  # City
        nav.move_right()  # wraps to Name column
        assert nav.current_position[1] == 0

    def test_no_wrap(self):
        cfg = TableNavigatorConfig(wrap_navigation=False)
        nav = TableNavigator(config=cfg)
        nav.load(self._make_table())
        nav.move_right()
        nav.move_right()
        result = nav.move_right()
        assert result is None

    def test_read_row(self):
        nav = TableNavigator()
        nav.load(self._make_table())
        row_text = nav.read_row()
        assert "Alice" in row_text
        assert "30" in row_text

    def test_read_column(self):
        nav = TableNavigator()
        nav.load(self._make_table())
        col_text = nav.read_column()
        assert "Name" in col_text
        assert "Alice" in col_text
        assert "Bob" in col_text


class TestDocumentStructure:
    """Tests for DocumentStructure parsing."""

    def test_parse_markdown(self):
        doc = DocumentStructure()
        doc.parse("# Title\nContent\n## Sub\nMore")
        headings = doc.get_headings()
        assert len(headings) == 2
        assert headings[0].text == "Title"
        assert headings[0].level == 1
        assert headings[1].text == "Sub"
        assert headings[1].level == 2

    def test_get_section(self):
        doc = DocumentStructure()
        doc.parse("# Intro\nHello\n# Body\nMain content")
        section = doc.get_section("Body")
        assert section is not None
        assert "Main content" in section.content

    def test_get_section_not_found(self):
        doc = DocumentStructure()
        doc.parse("# Intro\nHello")
        assert doc.get_section("Missing") is None

    def test_generate_toc(self):
        doc = DocumentStructure()
        doc.parse("# A\n## B\n### C\n#### D")
        toc = doc.generate_toc(max_level=3)
        assert "A" in toc
        assert "B" in toc
        assert "C" in toc
        assert "D" not in toc  # level 4 excluded

    def test_heading_level_filter(self):
        doc = DocumentStructure()
        doc.parse("# H1\n## H2\n### H3")
        assert len(doc.get_headings(max_level=1)) == 1


# ===================================================================
# Visual Indicators
# ===================================================================

class TestVisualizerConfig:
    """Tests for VisualizerConfig and WaveformVisualizer."""

    def test_defaults(self):
        cfg = VisualizerConfig()
        assert cfg.style == VisualizationStyle.WAVEFORM
        assert cfg.color_scheme == ColorScheme.DEFAULT
        assert cfg.width == 800
        assert cfg.height == 200

    def test_render_returns_dict(self):
        viz = WaveformVisualizer()
        result = viz.render(b"\x00" * 200)
        assert result["width"] == 800
        assert result["height"] == 200

    def test_render_custom_size(self):
        viz = WaveformVisualizer()
        result = viz.render(b"\x00", width=400, height=100)
        assert result["width"] == 400
        assert result["height"] == 100


class TestSpeechIndicator:
    """Tests for SpeechIndicator."""

    def test_defaults(self):
        ind = SpeechIndicator()
        assert ind.is_speaking is False
        assert ind.current_speaker is None

    def test_set_speaking(self):
        ind = SpeechIndicator()
        ind.set_speaking("Alice", True)
        assert ind.is_speaking is True
        assert ind.current_speaker == "Alice"

    def test_detach_clears(self):
        ind = SpeechIndicator()
        ind.set_speaking("Alice", True)
        ind.detach()
        assert ind.is_speaking is False
        assert ind.current_speaker is None

    def test_color_from_config(self):
        cfg = IndicatorConfig(colors={"Alice": "#ff0000"})
        ind = SpeechIndicator(config=cfg)
        assert ind.get_color("Alice") == "#ff0000"

    def test_color_auto_generated(self):
        ind = SpeechIndicator()
        color = ind.get_color("Bob")
        assert color.startswith("hsl(")


class TestHapticFeedback:
    """Tests for HapticFeedback."""

    def test_defaults(self):
        cfg = HapticConfig()
        assert cfg.enabled is True
        assert cfg.intensity == 1.0
        assert cfg.patterns["word_boundary"] == HapticPattern.TAP

    def test_trigger_disabled(self):
        cfg = HapticConfig(enabled=False)
        hf = HapticFeedback(config=cfg)
        hf.trigger("word_boundary")  # should not raise

    def test_connect(self):
        hf = HapticFeedback()
        assert hf.connect() is True


# ===================================================================
# Accessibility Testing / Auditing
# ===================================================================

class TestAuditReport:
    """Tests for AuditReport aggregation."""

    def test_empty_report_compliant(self):
        report = AuditReport()
        assert report.is_compliant is True
        assert report.passed == 0
        assert report.failed == 0

    def test_report_with_failure(self):
        report = AuditReport(results=[
            AuditResult(
                check="Test",
                severity=AuditSeverity.FAIL,
                message="broken",
            ),
        ])
        assert report.is_compliant is False
        assert report.failed == 1

    def test_report_counts(self):
        report = AuditReport(results=[
            AuditResult(check="A", severity=AuditSeverity.PASS, message="ok"),
            AuditResult(check="B", severity=AuditSeverity.WARNING, message="eh"),
            AuditResult(check="C", severity=AuditSeverity.FAIL, message="bad"),
        ])
        assert report.passed == 1
        assert report.warnings == 1
        assert report.failed == 1

    def test_to_markdown(self):
        report = AuditReport(results=[
            AuditResult(
                check="Focus",
                severity=AuditSeverity.PASS,
                message="ok",
                criterion="2.4.7",
            ),
        ])
        md = report.to_markdown()
        assert "Accessibility Audit Report" in md
        assert "Focus" in md
        assert "2.4.7" in md


class TestAccessibilityAuditor:
    """Tests for AccessibilityAuditor."""

    def test_audit_returns_report(self):
        auditor = AccessibilityAuditor()
        report = auditor.audit(SimpleNamespace())
        assert isinstance(report, AuditReport)
        assert len(report.results) > 0

    def test_default_checks(self):
        auditor = AccessibilityAuditor()
        assert "caption_accuracy" in auditor.checks
        assert "keyboard_accessible" in auditor.checks

    def test_custom_checks(self):
        auditor = AccessibilityAuditor(checks=["caption_accuracy"])
        report = auditor.audit(SimpleNamespace())
        assert len(report.results) == 1


class TestScreenReaderTest:
    """Tests for the ScreenReaderTest testing harness."""

    def test_record_and_heard(self):
        srt = ScreenReaderTest()
        with srt.session() as session:
            srt.record("Hello world")
            assert session.heard("hello") is True
            assert session.heard("goodbye") is False

    def test_heard_exact(self):
        srt = ScreenReaderTest()
        with srt.session() as session:
            srt.record("Hello world")
            assert session.heard_exact("Hello world") is True
            assert session.heard_exact("hello world") is False

    def test_no_overlap(self):
        srt = ScreenReaderTest()
        with srt.session() as session:
            srt.record("one")
            srt.record("two")
            assert session.heard_overlap() is False

    def test_overlap_detected(self):
        srt = ScreenReaderTest()
        with srt.session() as session:
            srt.record("one", interrupted=True)
            assert session.heard_overlap() is True

    def test_get_announcements(self):
        srt = ScreenReaderTest()
        with srt.session() as session:
            srt.record("a")
            srt.record("b")
            assert session.get_announcements() == ["a", "b"]


class TestUserTestSession:
    """Tests for UserTestSession report generation."""

    def test_generate_report(self):
        session = UserTestSession()
        with session.start() as ctx:
            ctx.mark_task("Task 1")
            ctx.mark_complete(success=True, time_seconds=5.0)
            ctx.mark_task("Task 2")
            ctx.mark_complete(success=False, time_seconds=10.0)

        report = session.generate_report()
        assert report["total_tasks"] == 2
        assert report["successful"] == 1
        assert report["failed"] == 1
        assert report["success_rate"] == 0.5
        assert report["average_time"] == 7.5
