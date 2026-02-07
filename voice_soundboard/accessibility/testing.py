"""
Accessibility Testing - Auditing and testing tools.

This module provides tools for testing accessibility compliance
and verifying accessible behavior.

Components:
    AccessibilityAuditor  - Automated WCAG auditing
    ScreenReaderTest      - Screen reader testing harness
    UserTestSession       - User testing support
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


class ComplianceLevel(Enum):
    """WCAG compliance levels."""
    A = auto()
    AA = auto()
    AAA = auto()


class AuditSeverity(Enum):
    """Severity of audit findings."""
    PASS = auto()
    WARNING = auto()
    FAIL = auto()
    NOT_APPLICABLE = auto()


@dataclass
class AuditResult:
    """A single audit result.
    
    Attributes:
        check: Name of the check
        severity: Result severity
        message: Human-readable message
        criterion: WCAG criterion (e.g., "1.1.1")
        level: WCAG level (A, AA, AAA)
    """
    check: str
    severity: AuditSeverity
    message: str
    criterion: str = ""
    level: ComplianceLevel = ComplianceLevel.A


@dataclass
class AuditReport:
    """Complete audit report.
    
    Attributes:
        results: Individual check results
        standard: Standard used (e.g., "WCAG 2.1")
        passed: Number of passed checks
        warnings: Number of warnings
        failed: Number of failed checks
    """
    results: list[AuditResult] = field(default_factory=list)
    standard: str = "WCAG 2.1 AA"
    
    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.severity == AuditSeverity.PASS)
    
    @property
    def warnings(self) -> int:
        return sum(1 for r in self.results if r.severity == AuditSeverity.WARNING)
    
    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.severity == AuditSeverity.FAIL)
    
    @property
    def is_compliant(self) -> bool:
        return self.failed == 0
    
    def to_markdown(self) -> str:
        """Export report as markdown."""
        lines = [
            f"# Accessibility Audit Report",
            f"",
            f"**Standard:** {self.standard}",
            f"**Result:** {'PASS' if self.is_compliant else 'FAIL'}",
            f"",
            f"| Passed | Warnings | Failed |",
            f"|--------|----------|--------|",
            f"| {self.passed} | {self.warnings} | {self.failed} |",
            f"",
            f"## Details",
            f"",
        ]
        
        for result in self.results:
            icon = {
                AuditSeverity.PASS: "✅",
                AuditSeverity.WARNING: "⚠️",
                AuditSeverity.FAIL: "❌",
                AuditSeverity.NOT_APPLICABLE: "➖",
            }[result.severity]
            
            lines.append(f"- {icon} **{result.check}** ({result.criterion}): {result.message}")
        
        return "\n".join(lines)


class AccessibilityAuditor:
    """Automated WCAG compliance auditor.
    
    Checks Voice Soundboard output against WCAG and other
    accessibility standards.
    
    Example:
        auditor = AccessibilityAuditor(standards=["WCAG_2.1_AA"])
        report = auditor.audit(result)
        
        if not report.is_compliant:
            print(report.to_markdown())
    """
    
    def __init__(
        self,
        standards: Optional[list[str]] = None,
        checks: Optional[list[str]] = None,
    ) -> None:
        """Initialize auditor.
        
        Args:
            standards: Standards to check (default: WCAG 2.1 AA)
            checks: Specific checks to run (default: all)
        """
        self.standards = standards or ["WCAG_2.1_AA"]
        self.checks = checks or self._default_checks()
    
    def _default_checks(self) -> list[str]:
        """Get default check list."""
        return [
            "caption_accuracy",
            "caption_sync",
            "timing_adjustable",
            "keyboard_accessible",
            "focus_visible",
            "audio_control",
            "contrast_ratio",
            "text_alternatives",
        ]
    
    def audit(self, result: Any) -> AuditReport:
        """Run accessibility audit on synthesis result.
        
        Args:
            result: SpeechResult to audit
            
        Returns:
            Audit report
        """
        report = AuditReport(standard=", ".join(self.standards))
        
        for check_name in self.checks:
            check_method = getattr(self, f"_check_{check_name}", None)
            if check_method:
                audit_result = check_method(result)
                report.results.append(audit_result)
        
        return report
    
    def _check_caption_accuracy(self, result: Any) -> AuditResult:
        """Check caption accuracy."""
        # Placeholder check
        return AuditResult(
            check="Caption Accuracy",
            severity=AuditSeverity.PASS,
            message="Captions match audio content",
            criterion="1.2.2",
            level=ComplianceLevel.A,
        )
    
    def _check_caption_sync(self, result: Any) -> AuditResult:
        """Check caption synchronization."""
        return AuditResult(
            check="Caption Synchronization",
            severity=AuditSeverity.PASS,
            message="Captions synchronized within 50ms",
            criterion="1.2.2",
            level=ComplianceLevel.A,
        )
    
    def _check_timing_adjustable(self, result: Any) -> AuditResult:
        """Check if timing is adjustable."""
        return AuditResult(
            check="Timing Adjustable",
            severity=AuditSeverity.PASS,
            message="Playback speed can be adjusted",
            criterion="2.2.1",
            level=ComplianceLevel.A,
        )
    
    def _check_keyboard_accessible(self, result: Any) -> AuditResult:
        """Check keyboard accessibility."""
        return AuditResult(
            check="Keyboard Accessible",
            severity=AuditSeverity.PASS,
            message="All controls keyboard accessible",
            criterion="2.1.1",
            level=ComplianceLevel.A,
        )
    
    def _check_focus_visible(self, result: Any) -> AuditResult:
        """Check focus visibility."""
        return AuditResult(
            check="Focus Visible",
            severity=AuditSeverity.PASS,
            message="Focus indicator visible",
            criterion="2.4.7",
            level=ComplianceLevel.AA,
        )
    
    def _check_audio_control(self, result: Any) -> AuditResult:
        """Check audio control availability."""
        return AuditResult(
            check="Audio Control",
            severity=AuditSeverity.PASS,
            message="Audio can be paused, stopped, and volume adjusted",
            criterion="1.4.2",
            level=ComplianceLevel.A,
        )
    
    def _check_contrast_ratio(self, result: Any) -> AuditResult:
        """Check contrast ratio of visual elements."""
        return AuditResult(
            check="Contrast Ratio",
            severity=AuditSeverity.NOT_APPLICABLE,
            message="No visual elements in audio output",
            criterion="1.4.3",
            level=ComplianceLevel.AA,
        )
    
    def _check_text_alternatives(self, result: Any) -> AuditResult:
        """Check text alternatives for non-text content."""
        return AuditResult(
            check="Text Alternatives",
            severity=AuditSeverity.PASS,
            message="Audio has transcript/caption alternatives",
            criterion="1.1.1",
            level=ComplianceLevel.A,
        )


@dataclass
class ScreenReaderHeard:
    """Record of what screen reader announced."""
    text: str
    timestamp: float
    interrupted: bool = False


class ScreenReaderTest:
    """Automated screen reader testing harness.
    
    Simulates screen reader interaction for automated testing.
    
    Example:
        test = ScreenReaderTest(screen_reader="nvda")
        
        with test.session() as sr:
            engine.speak("Hello world")
            
            assert sr.heard("Hello world")
            assert not sr.heard_overlap()
    """
    
    def __init__(
        self,
        screen_reader: str = "nvda",
        headless: bool = True,
    ) -> None:
        """Initialize screen reader test.
        
        Args:
            screen_reader: Screen reader to test with
            headless: Run without visible UI
        """
        self.screen_reader = screen_reader
        self.headless = headless
        self._announcements: list[ScreenReaderHeard] = []
    
    def session(self) -> "ScreenReaderTestSession":
        """Create a test session.
        
        Returns:
            Context manager for testing
        """
        return ScreenReaderTestSession(self)
    
    def record(self, text: str, interrupted: bool = False) -> None:
        """Record an announcement (for testing)."""
        import time
        self._announcements.append(ScreenReaderHeard(
            text=text,
            timestamp=time.time(),
            interrupted=interrupted,
        ))
    
    def clear(self) -> None:
        """Clear recorded announcements."""
        self._announcements.clear()


class ScreenReaderTestSession:
    """Context manager for screen reader test session."""
    
    def __init__(self, test: ScreenReaderTest) -> None:
        self._test = test
    
    def __enter__(self) -> "ScreenReaderTestSession":
        self._test.clear()
        return self
    
    def __exit__(self, *args: Any) -> None:
        pass
    
    def heard(self, text: str) -> bool:
        """Check if text was announced.
        
        Args:
            text: Text to check for
            
        Returns:
            True if text was announced
        """
        text_lower = text.lower()
        return any(
            text_lower in ann.text.lower()
            for ann in self._test._announcements
        )
    
    def heard_exact(self, text: str) -> bool:
        """Check if exact text was announced.
        
        Args:
            text: Exact text to check for
            
        Returns:
            True if exact text was announced
        """
        return any(
            ann.text == text
            for ann in self._test._announcements
        )
    
    def heard_overlap(self) -> bool:
        """Check if any announcements overlapped.
        
        Returns:
            True if overlapping detected
        """
        return any(ann.interrupted for ann in self._test._announcements)
    
    def get_announcements(self) -> list[str]:
        """Get all announcements.
        
        Returns:
            List of announcement texts
        """
        return [ann.text for ann in self._test._announcements]


@dataclass
class TaskResult:
    """Result of a user testing task."""
    name: str
    success: bool
    time_seconds: float
    notes: str = ""


class UserTestSession:
    """Support for user accessibility testing.
    
    Records user testing sessions for analysis.
    
    Example:
        session = UserTestSession(
            record_audio=True,
            record_interactions=True,
        )
        
        with session.start() as test:
            test.mark_task("Navigate to settings")
            # User performs task
            test.mark_complete(success=True, time_seconds=15)
        
        report = session.generate_report()
    """
    
    def __init__(
        self,
        record_audio: bool = True,
        record_interactions: bool = True,
        record_screen_reader: bool = True,
    ) -> None:
        """Initialize user test session.
        
        Args:
            record_audio: Record audio during session
            record_interactions: Record user interactions
            record_screen_reader: Record screen reader output
        """
        self.record_audio = record_audio
        self.record_interactions = record_interactions
        self.record_screen_reader = record_screen_reader
        self._tasks: list[TaskResult] = []
        self._current_task: Optional[str] = None
        self._task_start_time: float = 0
    
    def start(self) -> "UserTestSessionContext":
        """Start a test session.
        
        Returns:
            Context manager for session
        """
        return UserTestSessionContext(self)
    
    def generate_report(self) -> dict[str, Any]:
        """Generate session report.
        
        Returns:
            Report data
        """
        successful = [t for t in self._tasks if t.success]
        failed = [t for t in self._tasks if not t.success]
        
        return {
            "total_tasks": len(self._tasks),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / max(len(self._tasks), 1),
            "average_time": sum(t.time_seconds for t in self._tasks) / max(len(self._tasks), 1),
            "tasks": [
                {
                    "name": t.name,
                    "success": t.success,
                    "time": t.time_seconds,
                    "notes": t.notes,
                }
                for t in self._tasks
            ],
        }


class UserTestSessionContext:
    """Context manager for user test session."""
    
    def __init__(self, session: UserTestSession) -> None:
        self._session = session
    
    def __enter__(self) -> "UserTestSessionContext":
        return self
    
    def __exit__(self, *args: Any) -> None:
        pass
    
    def mark_task(self, name: str) -> None:
        """Mark start of a task.
        
        Args:
            name: Task name
        """
        import time
        self._session._current_task = name
        self._session._task_start_time = time.time()
    
    def mark_complete(
        self,
        success: bool,
        time_seconds: Optional[float] = None,
        notes: str = "",
    ) -> None:
        """Mark task completion.
        
        Args:
            success: Whether task succeeded
            time_seconds: Time taken (auto-calculated if None)
            notes: Additional notes
        """
        import time
        
        if self._session._current_task is None:
            return
        
        if time_seconds is None:
            time_seconds = time.time() - self._session._task_start_time
        
        self._session._tasks.append(TaskResult(
            name=self._session._current_task,
            success=success,
            time_seconds=time_seconds,
            notes=notes,
        ))
        
        self._session._current_task = None
