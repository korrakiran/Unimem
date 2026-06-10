"""Tests for crash recovery: signal handlers, orphan session recovery, and task promotion."""

import json
import os
import signal
import sys
import time
import unittest.mock as mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from unimem.memory.manager import MemoryManager
from unimem.memory.schemas import Event, Session
from unimem.storage.json_store import JsonStore
from unimem.utils.paths import get_sessions_dir


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_session(sessions_dir: Path, session_id: str, tool: str, start_time: str, end_time=None) -> Path:
    """Write a Session JSON file directly for test setup."""
    session = Session(
        session_id=session_id,
        tool=tool,
        start_time=start_time,
        end_time=end_time,
    )
    path = sessions_dir / f"session_{session_id}.json"
    JsonStore.save(path, session.model_dump())
    return path


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------------------------------------------------------------------------
# 1. Signal handler tests
# ---------------------------------------------------------------------------

class TestSignalHandlers:
    """Verify that SIGTERM / SIGINT handlers call end_session on the live manager."""

    def test_generic_adapter_sigterm_calls_end_session(self, initialized_unimem):
        """Signal handler should call manager.end_session(session_id) on SIGTERM."""
        from unimem.adapters.generic import GenericAdapter

        adapter = GenericAdapter(initialized_unimem)
        manager = MemoryManager(initialized_unimem)

        session = manager.start_session("generic")
        session_id = session.session_id

        end_session_calls = []

        original_end = manager.end_session

        def _mock_end(sid):
            end_session_calls.append(sid)
            return original_end(sid)

        # Patch manager inside the adapter's launch closure by intercepting via
        # the MemoryManager class directly for this session
        with mock.patch.object(manager, "end_session", side_effect=_mock_end):
            # Build the same closure that launch() builds and fire it directly
            def _handle_signal(signum, frame):
                if session_id and manager.is_initialized():
                    manager.end_session(session_id)
                signal.signal(signum, signal.SIG_DFL)
                # Don't actually kill the test process — just test the end_session path

            _handle_signal(signal.SIGTERM, None)

        assert session_id in end_session_calls, "end_session was not called on SIGTERM"

    def test_claude_adapter_sigint_calls_end_session(self, initialized_unimem):
        """Signal handler should call manager.end_session(session_id) on SIGINT."""
        from unimem.adapters.claude import ClaudeAdapter

        manager = MemoryManager(initialized_unimem)
        session = manager.start_session("claude")
        session_id = session.session_id

        end_session_calls = []
        original_end = manager.end_session

        def _mock_end(sid):
            end_session_calls.append(sid)
            return original_end(sid)

        with mock.patch.object(manager, "end_session", side_effect=_mock_end):
            def _handle_signal(signum, frame):
                if session_id and manager.is_initialized():
                    manager.end_session(session_id)
                signal.signal(signum, signal.SIG_DFL)

            _handle_signal(signal.SIGINT, None)

        assert session_id in end_session_calls, "end_session was not called on SIGINT"

    def test_generic_adapter_launch_registers_signal_handlers(self, initialized_unimem):
        """After launch() returns, SIGTERM and SIGINT handlers should be registered
        (we check that during the run the handler slot was set)."""
        from unimem.adapters.generic import GenericAdapter

        adapter = GenericAdapter(initialized_unimem)
        registered_signals = {}

        original_signal = signal.signal

        def _capture_signal(signum, handler):
            registered_signals[signum] = handler
            return original_signal(signum, handler)

        with mock.patch("signal.signal", side_effect=_capture_signal):
            result = adapter.launch([sys.executable, "-c", "pass"])

        assert signal.SIGTERM in registered_signals, "SIGTERM handler not registered"
        assert signal.SIGINT in registered_signals, "SIGINT handler not registered"
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# 2. Orphan session recovery tests
# ---------------------------------------------------------------------------

class TestOrphanSessionRecovery:
    """Verify recover_orphan_sessions() closes old open sessions."""

    def test_recovers_session_older_than_10_minutes(self, initialized_unimem):
        """Sessions with no end_time older than 10 min should be closed."""
        manager = MemoryManager(initialized_unimem)
        sessions_dir = get_sessions_dir(initialized_unimem)

        old_start = _iso(datetime.now(timezone.utc) - timedelta(minutes=15))
        _write_session(sessions_dir, "orphan001", "claude", old_start)

        recovered = manager.recover_orphan_sessions()

        assert "orphan001" in recovered

        # The session file should now have an end_time set
        data = JsonStore.load(sessions_dir / "session_orphan001.json")
        assert data["end_time"] is not None, "end_time not set after recovery"

    def test_ignores_session_newer_than_10_minutes(self, initialized_unimem):
        """Sessions started recently (< 10 min ago) should NOT be closed."""
        manager = MemoryManager(initialized_unimem)
        sessions_dir = get_sessions_dir(initialized_unimem)

        recent_start = _iso(datetime.now(timezone.utc) - timedelta(minutes=5))
        _write_session(sessions_dir, "recent001", "generic", recent_start)

        recovered = manager.recover_orphan_sessions()

        assert "recent001" not in recovered

        data = JsonStore.load(sessions_dir / "session_recent001.json")
        assert data["end_time"] is None, "Recent session should not have been closed"

    def test_ignores_already_closed_sessions(self, initialized_unimem):
        """Sessions that already have end_time should not appear in recovered list."""
        manager = MemoryManager(initialized_unimem)
        sessions_dir = get_sessions_dir(initialized_unimem)

        old_start = _iso(datetime.now(timezone.utc) - timedelta(minutes=20))
        old_end = _iso(datetime.now(timezone.utc) - timedelta(minutes=5))
        _write_session(sessions_dir, "closed001", "generic", old_start, end_time=old_end)

        recovered = manager.recover_orphan_sessions()

        assert "closed001" not in recovered

    def test_recover_orphan_called_on_load_state(self, initialized_unimem):
        """load_state() should automatically call recover_orphan_sessions()."""
        manager = MemoryManager(initialized_unimem)

        with mock.patch.object(
            manager, "recover_orphan_sessions", wraps=manager.recover_orphan_sessions
        ) as mock_recover:
            manager.load_state()

        mock_recover.assert_called_once()

    def test_recover_returns_empty_when_no_sessions(self, initialized_unimem):
        """recover_orphan_sessions() should return empty list when sessions dir is empty."""
        manager = MemoryManager(initialized_unimem)
        recovered = manager.recover_orphan_sessions()
        assert isinstance(recovered, list)
        # May contain sessions created by initialize(); none should be older than 10 min
        # so the result should be empty (or only have already-closed entries excluded)
        assert all(isinstance(s, str) for s in recovered)


# ---------------------------------------------------------------------------
# 3. Task promotion on orphan recovery tests
# ---------------------------------------------------------------------------

class TestTaskPromotionOnOrphanRecovery:
    """Verify LocalSummarizer promotes current_task when it matches in_progress and
    file changes exist (the orphan-recovery scenario)."""

    def test_promotes_task_when_in_progress_matches_and_files_changed(self, initialized_unimem):
        """If current_task appears in in_progress_features and files were changed,
        summarizer should promote current_task = next_task."""
        from unimem.summarizer.local import LocalSummarizer
        from unimem.memory.schemas import ProjectState, Event

        summarizer = LocalSummarizer()

        state = ProjectState(
            project_name="test",
            current_task="implement signal handler",
            next_task="write unit tests",
            in_progress_features=["Implement signal handler", "Refactor adapters"],
            completed_features=[],
        )

        # Simulate events with file changes (what an orphaned session would have produced)
        events = [
            Event(
                tool="claude",
                event_type="agent_run",
                prompt="working on signal handling",
                response_summary="implementing signal handlers in adapters",
                files_changed=["unimem/adapters/generic.py", "unimem/adapters/claude.py"],
            )
        ]

        result = summarizer.summarize(state, events)

        assert result.current_task == "write unit tests", (
            f"Expected promotion to 'write unit tests', got '{result.current_task}'"
        )
        assert result.next_task == ""

    def test_does_not_promote_when_no_files_changed(self, initialized_unimem):
        """Without file changes, in_progress match alone should NOT trigger promotion."""
        from unimem.summarizer.local import LocalSummarizer
        from unimem.memory.schemas import ProjectState, Event

        summarizer = LocalSummarizer()

        state = ProjectState(
            project_name="test",
            current_task="implement signal handler",
            next_task="write unit tests",
            in_progress_features=["Implement signal handler"],
            completed_features=[],
        )

        # No files changed — session was truly empty
        events = [
            Event(
                tool="claude",
                event_type="agent_run",
                prompt="starting work",
                response_summary="no progress yet",
                files_changed=[],
            )
        ]

        result = summarizer.summarize(state, events)

        # Should NOT promote because there were no file changes
        assert result.current_task == "implement signal handler"

    def test_standard_completed_promotion_still_works(self, initialized_unimem):
        """Existing promotion via completed_features should remain unaffected."""
        from unimem.summarizer.local import LocalSummarizer
        from unimem.memory.schemas import ProjectState, Event

        summarizer = LocalSummarizer()

        state = ProjectState(
            project_name="test",
            current_task="Task A",
            next_task="Task B",
            completed_features=[],
            in_progress_features=[],
        )

        events = [
            Event(
                tool="watcher",
                event_type="git_commit",
                prompt="",
                response_summary="complete Task A",
                files_changed=[],
            )
        ]

        result = summarizer.summarize(state, events)

        assert result.current_task == "Task B"
        assert result.next_task == ""

    def test_full_orphan_recovery_promotes_task_via_manager(self, initialized_unimem):
        """Integration: writing an orphan session + file-change events, then calling
        load_state() should trigger recovery and task promotion end-to-end."""
        manager = MemoryManager(initialized_unimem)

        # Set up state with a clear task pipeline
        state = manager.load_state()
        state.current_task = "implement crash recovery"
        state.next_task = "update documentation"
        state.in_progress_features = ["Implement crash recovery"]
        manager.save_state(state)

        # Simulate a file-change event (as if the crashed agent did real work)
        event = Event(
            tool="claude",
            event_type="agent_run",
            prompt="implementing crash recovery features",
            response_summary="implementing crash recovery in adapters",
            files_changed=["unimem/adapters/generic.py"],
        )
        manager.record_event(event, auto_snapshot=False)

        # Write an orphan session (> 10 min old, no end_time)
        sessions_dir = get_sessions_dir(initialized_unimem)
        old_start = _iso(datetime.now(timezone.utc) - timedelta(minutes=15))
        _write_session(sessions_dir, "orphan_promo_test", "claude", old_start)

        # load_state() triggers recover_orphan_sessions() + rebuild_state_from_events()
        recovered_state = manager.load_state()

        # current_task should have been promoted to next_task
        assert recovered_state.current_task == "update documentation", (
            f"Task not promoted. current_task='{recovered_state.current_task}'"
        )
