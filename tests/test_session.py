"""Tests for claws session — session continuity.

Tests cover:
- Event types (SESSION_STARTED, SESSION_ENDED)
- CLI commands (start, end)
- Scratchpad integration (auto-read on start, auto-tend on end)
- Reflections added via --summary on end
- Edge cases (no scratchpad, no project, no agent, unclosed session warning)
"""

import json
import os
import yaml
import pytest
from pathlib import Path
from click.testing import CliRunner

from claws.cli import main
from claws.events import (
    EventSpine,
    Event,
    SESSION_STARTED,
    SESSION_ENDED,
    DECISION_PRESENTED,
    DECISION_RESOLVED,
)
from claws.scratchpad import (
    Scratchpad,
    Thread,
    Decision,
    load_scratchpad,
    save_scratchpad,
)
from claws.commands.session import _count_pending_decisions, _last_session_event


def _make_project(td_path: Path, agents=None):
    """Helper: create a project with optional agents."""
    if agents is None:
        agents = {}
    config = {
        "project": "test-project",
        "version": 2,
        "providers": {
            "default": {
                "type": "anthropic",
                "model": "claude-sonnet-4-5-20250929",
            },
        },
        "agents": agents,
        "eval": {"judges": ["logic", "consistency"], "threshold": 8.0},
    }
    (td_path / "claws.yaml").write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False)
    )
    (td_path / "agents").mkdir(exist_ok=True)
    (td_path / ".claws").mkdir(exist_ok=True)


def _make_agent(td_path: Path, name: str, role: str = "researcher"):
    """Helper: create an agent directory."""
    agent_dir = td_path / "agents" / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "identity.md").write_text(f"# {name}\nRole: {role}\n")
    (agent_dir / "memory.md").write_text(f"# {name} Memory\n")


def _make_scratchpad(td_path: Path, agent_name: str, **kwargs):
    """Helper: create a scratchpad with optional data."""
    sp = Scratchpad(agent_name=agent_name, **kwargs)
    save_scratchpad(td_path, sp)
    return sp


def _chdir(path: Path):
    """Context-free chdir helper — returns old cwd."""
    old = os.getcwd()
    os.chdir(path)
    return old


# --- Event type tests ---


class TestSessionEventTypes:
    """Test that session event types are properly defined."""

    def test_session_started_constant(self):
        assert SESSION_STARTED == "session.started"

    def test_session_ended_constant(self):
        assert SESSION_ENDED == "session.ended"

    def test_emit_session_started(self, tmp_path):
        spine = EventSpine(tmp_path)
        event = spine.emit(Event(
            type=SESSION_STARTED,
            agent="scout",
            data={"scratchpad": True, "threads": 2, "pending_decisions": 1},
        ))
        assert event.type == SESSION_STARTED
        assert event.agent == "scout"
        assert event.data["threads"] == 2

    def test_emit_session_ended(self, tmp_path):
        spine = EventSpine(tmp_path)
        event = spine.emit(Event(
            type=SESSION_ENDED,
            agent="scout",
            data={"summary": "Did some work", "scratchpad_tended": True},
        ))
        assert event.type == SESSION_ENDED
        assert event.data["summary"] == "Did some work"

    def test_read_by_type(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=SESSION_STARTED, agent="a", data={}))
        spine.emit(Event(type=SESSION_ENDED, agent="a", data={}))
        spine.emit(Event(type=SESSION_STARTED, agent="a", data={}))

        started = spine.read_by_type(SESSION_STARTED)
        assert len(started) == 2
        ended = spine.read_by_type(SESSION_ENDED)
        assert len(ended) == 1


# --- Helper function tests ---


class TestSessionHelpers:
    """Test helper functions."""

    def test_count_pending_decisions_empty(self, tmp_path):
        spine = EventSpine(tmp_path)
        assert _count_pending_decisions(spine, "scout") == 0

    def test_count_pending_decisions_with_presented(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED, agent="scout",
            data={"number": 1, "question": "Q?", "options": ["A"]},
        ))
        spine.emit(Event(
            type=DECISION_PRESENTED, agent="scout",
            data={"number": 2, "question": "Q2?", "options": ["B"]},
        ))
        assert _count_pending_decisions(spine, "scout") == 2

    def test_count_pending_decisions_with_resolved(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED, agent="scout",
            data={"number": 1, "question": "Q?", "options": ["A"]},
        ))
        spine.emit(Event(
            type=DECISION_PRESENTED, agent="scout",
            data={"number": 2, "question": "Q2?", "options": ["B"]},
        ))
        spine.emit(Event(
            type=DECISION_RESOLVED, agent="scout",
            data={"number": 1, "resolution": "A"},
        ))
        assert _count_pending_decisions(spine, "scout") == 1

    def test_count_pending_decisions_per_agent(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED, agent="scout",
            data={"number": 1, "question": "Q?", "options": ["A"]},
        ))
        spine.emit(Event(
            type=DECISION_PRESENTED, agent="forge",
            data={"number": 1, "question": "Q?", "options": ["X"]},
        ))
        assert _count_pending_decisions(spine, "scout") == 1
        assert _count_pending_decisions(spine, "forge") == 1

    def test_last_session_event_none(self, tmp_path):
        spine = EventSpine(tmp_path)
        assert _last_session_event(spine, "scout") is None

    def test_last_session_event_started(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=SESSION_STARTED, agent="scout", data={}))
        last = _last_session_event(spine, "scout")
        assert last is not None
        assert last.type == SESSION_STARTED

    def test_last_session_event_ended(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=SESSION_STARTED, agent="scout", data={}))
        spine.emit(Event(type=SESSION_ENDED, agent="scout", data={}))
        last = _last_session_event(spine, "scout")
        assert last is not None
        assert last.type == SESSION_ENDED

    def test_last_session_event_per_agent(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=SESSION_STARTED, agent="scout", data={}))
        spine.emit(Event(type=SESSION_ENDED, agent="forge", data={}))
        last_scout = _last_session_event(spine, "scout")
        last_forge = _last_session_event(spine, "forge")
        assert last_scout.type == SESSION_STARTED
        assert last_forge.type == SESSION_ENDED


# --- CLI session start ---


class TestSessionStart:
    """Test `claws session start`."""

    def test_start_no_scratchpad(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Session started" in result.output
            assert "scout" in result.output
            assert "No scratchpad found" in result.output
            assert "Clean slate" in result.output

            # Verify event emitted
            spine = EventSpine(tmp_path)
            events = spine.read_by_type(SESSION_STARTED)
            assert len(events) == 1
            assert events[0].agent == "scout"
            assert events[0].data["scratchpad"] is False
        finally:
            os.chdir(old)

    def test_start_with_empty_scratchpad(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout")
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Session started" in result.output
            assert "No active threads" in result.output

            spine = EventSpine(tmp_path)
            events = spine.read_by_type(SESSION_STARTED)
            assert events[0].data["scratchpad"] is True
            assert events[0].data["threads"] == 0
        finally:
            os.chdir(old)

    def test_start_shows_threads(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout", threads=[
            Thread(name="API design", state="in progress", next_action="Write endpoints"),
            Thread(name="Testing", state="blocked", next_action="Fix CI"),
        ])
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "API design" in result.output
            assert "Testing" in result.output
            assert "in progress" in result.output

            spine = EventSpine(tmp_path)
            assert spine.read_by_type(SESSION_STARTED)[0].data["threads"] == 2
        finally:
            os.chdir(old)

    def test_start_shows_pending_decisions(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout", decisions=[
            Decision(number=1, question="Which DB?", urgency="high"),
            Decision(number=2, question="Deploy strategy?", urgency="normal"),
        ])
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Which DB?" in result.output
            assert "Deploy strategy?" in result.output
            assert "2 pending scratchpad decision" in result.output
        finally:
            os.chdir(old)

    def test_start_shows_inbox(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout", inbox=[
            "Review PR #42",
            "Check deployment logs",
        ])
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Review PR #42" in result.output
            assert "Check deployment logs" in result.output
            assert "2 item" in result.output
        finally:
            os.chdir(old)

    def test_start_shows_last_reflection(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout", reflections=[
            "Old reflection",
            "Most recent insight about the architecture",
        ])
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Most recent insight" in result.output
        finally:
            os.chdir(old)

    def test_start_shows_event_log_decisions(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        # Add a pending decision to the event log
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED, agent="scout",
            data={"number": 1, "question": "Q?", "options": ["A"]},
        ))
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "1 pending decision(s) in event log" in result.output
        finally:
            os.chdir(old)

    def test_start_summary_line_with_context(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout",
            threads=[Thread(name="T1")],
            inbox=["item1", "item2"],
        )
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED, agent="scout",
            data={"number": 1, "question": "Q?", "options": ["A"]},
        ))
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "1 threads" in result.output
            assert "1 decisions" in result.output
            assert "2 inbox" in result.output
        finally:
            os.chdir(old)

    def test_start_warns_unclosed_session(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        # Emit a session.started without a matching end
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=SESSION_STARTED, agent="scout", data={}))
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Previous session" in result.output
            assert "was not ended" in result.output
        finally:
            os.chdir(old)

    def test_start_no_warning_after_end(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=SESSION_STARTED, agent="scout", data={}))
        spine.emit(Event(type=SESSION_ENDED, agent="scout", data={}))
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "was not ended" not in result.output
        finally:
            os.chdir(old)

    def test_start_no_project(self, tmp_path):
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ])
            assert result.exit_code != 0
        finally:
            os.chdir(old)

    def test_start_no_agent(self, tmp_path):
        _make_project(tmp_path)
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "ghost",
            ])
            assert result.exit_code != 0
        finally:
            os.chdir(old)


# --- CLI session end ---


class TestSessionEnd:
    """Test `claws session end`."""

    def test_end_no_scratchpad(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "end", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Session ended" in result.output
            assert "Done" in result.output

            spine = EventSpine(tmp_path)
            events = spine.read_by_type(SESSION_ENDED)
            assert len(events) == 1
            assert events[0].data["scratchpad_tended"] is False
        finally:
            os.chdir(old)

    def test_end_tends_scratchpad(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout", threads=[
            Thread(name="work"),
        ])
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "end", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Scratchpad tended" in result.output

            spine = EventSpine(tmp_path)
            events = spine.read_by_type(SESSION_ENDED)
            assert events[0].data["scratchpad_tended"] is True
            assert events[0].data["threads"] == 1

            # Verify scratchpad was actually saved (last_tended updated)
            sp = load_scratchpad(tmp_path, "scout")
            assert sp.last_tended != ""
        finally:
            os.chdir(old)

    def test_end_with_summary(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout")
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "end", "scout",
                "--summary", "Completed the API integration",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Completed the API integration" in result.output

            # Verify reflection was added to scratchpad
            sp = load_scratchpad(tmp_path, "scout")
            assert "Completed the API integration" in sp.reflections

            # Verify event data includes summary
            spine = EventSpine(tmp_path)
            events = spine.read_by_type(SESSION_ENDED)
            assert events[0].data["summary"] == "Completed the API integration"
        finally:
            os.chdir(old)

    def test_end_summary_short_flag(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout")
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "end", "scout",
                "-s", "Quick session",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Quick session" in result.output
        finally:
            os.chdir(old)

    def test_end_no_summary_no_reflection(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout")
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            runner.invoke(main, [
                "session", "end", "scout",
            ], catch_exceptions=False)

            sp = load_scratchpad(tmp_path, "scout")
            assert len(sp.reflections) == 0
        finally:
            os.chdir(old)

    def test_end_preserves_existing_reflections(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout", reflections=["old insight"])
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            runner.invoke(main, [
                "session", "end", "scout",
                "-s", "new insight",
            ], catch_exceptions=False)

            sp = load_scratchpad(tmp_path, "scout")
            assert "old insight" in sp.reflections
            assert "new insight" in sp.reflections
        finally:
            os.chdir(old)

    def test_end_shows_pending_count(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout", decisions=[
            Decision(number=1, question="Q?", urgency="normal"),
        ])
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "end", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "1 pending decision" in result.output
        finally:
            os.chdir(old)

    def test_end_no_project(self, tmp_path):
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "end", "scout",
            ])
            assert result.exit_code != 0
        finally:
            os.chdir(old)

    def test_end_no_agent(self, tmp_path):
        _make_project(tmp_path)
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "end", "ghost",
            ])
            assert result.exit_code != 0
        finally:
            os.chdir(old)


# --- Integration tests ---


class TestSessionIntegration:
    """Integration and lifecycle tests."""

    def test_full_lifecycle(self, tmp_path):
        """Full lifecycle: start → work → end with summary."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout",
            threads=[Thread(name="feature-x", state="coding")],
            inbox=["Review PR"],
        )
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()

            # Start session
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "feature-x" in result.output

            # End session
            result = runner.invoke(main, [
                "session", "end", "scout",
                "-s", "Finished feature-x, PR ready",
            ], catch_exceptions=False)
            assert result.exit_code == 0

            # Verify both events in log
            spine = EventSpine(tmp_path)
            started = spine.read_by_type(SESSION_STARTED)
            ended = spine.read_by_type(SESSION_ENDED)
            assert len(started) == 1
            assert len(ended) == 1
            assert ended[0].data["summary"] == "Finished feature-x, PR ready"
        finally:
            os.chdir(old)

    def test_multiple_sessions(self, tmp_path):
        """Multiple start/end cycles accumulate in event log."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            for i in range(3):
                runner.invoke(main, ["session", "start", "scout"], catch_exceptions=False)
                runner.invoke(main, ["session", "end", "scout"], catch_exceptions=False)

            spine = EventSpine(tmp_path)
            assert len(spine.read_by_type(SESSION_STARTED)) == 3
            assert len(spine.read_by_type(SESSION_ENDED)) == 3
        finally:
            os.chdir(old)

    def test_session_independent_of_scratchpad(self, tmp_path):
        """Sessions work fine without a scratchpad."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0

            result = runner.invoke(main, [
                "session", "end", "scout",
                "-s", "Light session, no scratchpad",
            ], catch_exceptions=False)
            assert result.exit_code == 0

            spine = EventSpine(tmp_path)
            ended = spine.read_by_type(SESSION_ENDED)
            assert ended[0].data["scratchpad_tended"] is False
            assert ended[0].data["summary"] == "Light session, no scratchpad"
        finally:
            os.chdir(old)

    def test_session_per_agent_isolation(self, tmp_path):
        """Sessions for different agents don't interfere."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_agent(tmp_path, "forge")
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            runner.invoke(main, ["session", "start", "scout"], catch_exceptions=False)
            runner.invoke(main, ["session", "start", "forge"], catch_exceptions=False)

            # Only scout's session is unclosed — forge shouldn't warn
            spine = EventSpine(tmp_path)
            started = spine.read_by_type(SESSION_STARTED)
            assert len(started) == 2
            agents = {e.agent for e in started}
            assert agents == {"scout", "forge"}
        finally:
            os.chdir(old)

    def test_end_summary_without_scratchpad_still_records(self, tmp_path):
        """Summary is recorded in event even without scratchpad."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            runner.invoke(main, [
                "session", "end", "scout",
                "-s", "Just a note",
            ], catch_exceptions=False)

            spine = EventSpine(tmp_path)
            events = spine.read_by_type(SESSION_ENDED)
            assert events[0].data["summary"] == "Just a note"
        finally:
            os.chdir(old)

    def test_rich_scratchpad_context(self, tmp_path):
        """Start shows full context from a populated scratchpad."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_scratchpad(tmp_path, "scout",
            threads=[
                Thread(name="Auth system", state="implementing", next_action="Add JWT"),
                Thread(name="Docs", state="drafting"),
            ],
            decisions=[
                Decision(number=1, question="OAuth provider?", urgency="high"),
                Decision(number=2, question="Token TTL?", urgency="normal", resolved=True, resolution="1h"),
            ],
            inbox=["Meeting notes from standup", "Bug report #123"],
            reflections=["JWT approach working well"],
        )
        old = _chdir(tmp_path)
        try:
            runner = CliRunner()
            result = runner.invoke(main, [
                "session", "start", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            # Threads
            assert "Auth system" in result.output
            assert "Docs" in result.output
            # Only pending decision shown
            assert "OAuth provider?" in result.output
            assert "1 pending scratchpad" in result.output
            # Inbox
            assert "Meeting notes" in result.output
            assert "Bug report" in result.output
            # Last reflection
            assert "JWT approach" in result.output
            # Summary line
            assert "2 threads" in result.output
        finally:
            os.chdir(old)
