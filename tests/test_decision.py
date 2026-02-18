"""Tests for claws decision — first-class decision protocol.

Tests cover:
- Event types (DECISION_PRESENTED, DECISION_RESOLVED)
- CLI commands (present, resolve, list, history)
- Event log integration (decisions are events, not scratchpad-only)
- Edge cases (resolve non-existent, double resolve, no options)
"""

import json
import yaml
import pytest
from pathlib import Path
from click.testing import CliRunner

from claws.cli import main
from claws.events import (
    EventSpine,
    Event,
    DECISION_PRESENTED,
    DECISION_RESOLVED,
)
from claws.commands.decision import _get_decisions, _next_decision_number


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


# --- Event type tests ---


class TestDecisionEventTypes:
    """Test that decision event types are properly defined."""

    def test_decision_presented_constant(self):
        assert DECISION_PRESENTED == "decision.presented"

    def test_decision_resolved_constant(self):
        assert DECISION_RESOLVED == "decision.resolved"

    def test_emit_decision_presented(self, tmp_path):
        spine = EventSpine(tmp_path)
        event = spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={
                "number": 1,
                "question": "Which API?",
                "options": ["REST", "GraphQL"],
                "context": "For the new service",
            },
        ))
        assert event.type == DECISION_PRESENTED
        assert event.agent == "scout"
        assert event.data["number"] == 1
        assert event.data["options"] == ["REST", "GraphQL"]

    def test_emit_decision_resolved(self, tmp_path):
        spine = EventSpine(tmp_path)
        event = spine.emit(Event(
            type=DECISION_RESOLVED,
            agent="scout",
            data={
                "number": 1,
                "resolution": "REST",
                "reasoning": "Simpler for v1",
            },
        ))
        assert event.type == DECISION_RESOLVED
        assert event.data["resolution"] == "REST"
        assert event.data["reasoning"] == "Simpler for v1"

    def test_read_by_type(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(type=DECISION_PRESENTED, agent="a", data={"number": 1}))
        spine.emit(Event(type=DECISION_PRESENTED, agent="a", data={"number": 2}))
        spine.emit(Event(type=DECISION_RESOLVED, agent="a", data={"number": 1}))

        presented = spine.read_by_type(DECISION_PRESENTED)
        assert len(presented) == 2
        resolved = spine.read_by_type(DECISION_RESOLVED)
        assert len(resolved) == 1


# --- Helper function tests ---


class TestDecisionHelpers:
    """Test _get_decisions and _next_decision_number helpers."""

    def test_get_decisions_empty(self, tmp_path):
        spine = EventSpine(tmp_path)
        decisions = _get_decisions(spine, "scout")
        assert decisions == []

    def test_get_decisions_with_presented(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={"number": 1, "question": "Q1", "options": ["A", "B"]},
        ))
        decisions = _get_decisions(spine, "scout")
        assert len(decisions) == 1
        assert decisions[0]["question"] == "Q1"
        assert decisions[0]["status"] == "pending"
        assert decisions[0]["options"] == ["A", "B"]

    def test_get_decisions_with_resolution(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={"number": 1, "question": "Q1", "options": ["A", "B"]},
        ))
        spine.emit(Event(
            type=DECISION_RESOLVED,
            agent="scout",
            data={"number": 1, "resolution": "A", "reasoning": "Better"},
        ))
        decisions = _get_decisions(spine, "scout")
        assert len(decisions) == 1
        assert decisions[0]["status"] == "resolved"
        assert decisions[0]["resolution"] == "A"
        assert decisions[0]["reasoning"] == "Better"

    def test_get_decisions_multiple_agents(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={"number": 1, "question": "Q1", "options": ["A"]},
        ))
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="forge",
            data={"number": 1, "question": "Q2", "options": ["X"]},
        ))
        scout_decisions = _get_decisions(spine, "scout")
        forge_decisions = _get_decisions(spine, "forge")
        assert len(scout_decisions) == 1
        assert len(forge_decisions) == 1
        assert scout_decisions[0]["question"] == "Q1"
        assert forge_decisions[0]["question"] == "Q2"

    def test_get_decisions_sorted_by_number(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={"number": 3, "question": "Q3", "options": []},
        ))
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={"number": 1, "question": "Q1", "options": []},
        ))
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={"number": 2, "question": "Q2", "options": []},
        ))
        decisions = _get_decisions(spine, "scout")
        assert [d["number"] for d in decisions] == [1, 2, 3]

    def test_next_decision_number_empty(self, tmp_path):
        spine = EventSpine(tmp_path)
        assert _next_decision_number(spine, "scout") == 1

    def test_next_decision_number_increments(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={"number": 1, "question": "Q1", "options": []},
        ))
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={"number": 2, "question": "Q2", "options": []},
        ))
        assert _next_decision_number(spine, "scout") == 3

    def test_next_decision_number_per_agent(self, tmp_path):
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={"number": 5, "question": "Q", "options": []},
        ))
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="forge",
            data={"number": 2, "question": "Q", "options": []},
        ))
        assert _next_decision_number(spine, "scout") == 6
        assert _next_decision_number(spine, "forge") == 3


# --- CLI present command ---


class TestDecisionPresent:
    """Test `claws decision present`."""

    def test_present_basic(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        runner = CliRunner()
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(main, [
                "decision", "present", "scout", "Which API?",
                "-o", "REST", "-o", "GraphQL",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Decision #1 presented" in result.output
            assert "REST" in result.output
            assert "GraphQL" in result.output

            # Verify event was emitted
            spine = EventSpine(tmp_path)
            events = spine.read_by_type(DECISION_PRESENTED)
            assert len(events) == 1
            assert events[0].data["question"] == "Which API?"
            assert events[0].data["options"] == ["REST", "GraphQL"]
            assert events[0].data["number"] == 1
        finally:
            os.chdir(old_cwd)

    def test_present_with_context(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(main, [
                "decision", "present", "scout", "Deploy where?",
                "-o", "AWS", "-o", "GCP",
                "-c", "Budget constraint: $500/mo",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Context: Budget constraint" in result.output

            spine = EventSpine(tmp_path)
            events = spine.read_by_type(DECISION_PRESENTED)
            assert events[0].data["context"] == "Budget constraint: $500/mo"
        finally:
            os.chdir(old_cwd)

    def test_present_increments_number(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            runner.invoke(main, [
                "decision", "present", "scout", "Q1", "-o", "A", "-o", "B",
            ], catch_exceptions=False)
            result = runner.invoke(main, [
                "decision", "present", "scout", "Q2", "-o", "X", "-o", "Y",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Decision #2 presented" in result.output
        finally:
            os.chdir(old_cwd)

    def test_present_no_project(self, tmp_path):
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(main, [
                "decision", "present", "scout", "Q?", "-o", "A",
            ])
            assert result.exit_code != 0
        finally:
            os.chdir(old_cwd)

    def test_present_no_agent(self, tmp_path):
        _make_project(tmp_path)
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(main, [
                "decision", "present", "ghost", "Q?", "-o", "A",
            ])
            assert result.exit_code != 0
        finally:
            os.chdir(old_cwd)

    def test_present_requires_options(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(main, [
                "decision", "present", "scout", "Q?",
            ])
            # Click should error because --option is required
            assert result.exit_code != 0
        finally:
            os.chdir(old_cwd)


# --- CLI resolve command ---


class TestDecisionResolve:
    """Test `claws decision resolve`."""

    def test_resolve_basic(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            # Present first
            runner.invoke(main, [
                "decision", "present", "scout", "Which API?",
                "-o", "REST", "-o", "GraphQL",
            ], catch_exceptions=False)
            # Resolve
            result = runner.invoke(main, [
                "decision", "resolve", "scout", "1", "REST",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Decision #1 resolved" in result.output
            assert "REST" in result.output

            # Verify event
            spine = EventSpine(tmp_path)
            events = spine.read_by_type(DECISION_RESOLVED)
            assert len(events) == 1
            assert events[0].data["resolution"] == "REST"
        finally:
            os.chdir(old_cwd)

    def test_resolve_with_reasoning(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            runner.invoke(main, [
                "decision", "present", "scout", "Which API?",
                "-o", "REST", "-o", "GraphQL",
            ], catch_exceptions=False)
            result = runner.invoke(main, [
                "decision", "resolve", "scout", "1", "REST",
                "--reasoning", "Simpler for v1, GraphQL adds complexity",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Reasoning: Simpler" in result.output

            spine = EventSpine(tmp_path)
            events = spine.read_by_type(DECISION_RESOLVED)
            assert events[0].data["reasoning"] == "Simpler for v1, GraphQL adds complexity"
        finally:
            os.chdir(old_cwd)

    def test_resolve_nonexistent(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(main, [
                "decision", "resolve", "scout", "99", "something",
            ])
            assert result.exit_code != 0
        finally:
            os.chdir(old_cwd)

    def test_resolve_already_resolved(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            runner.invoke(main, [
                "decision", "present", "scout", "Q?",
                "-o", "A", "-o", "B",
            ], catch_exceptions=False)
            runner.invoke(main, [
                "decision", "resolve", "scout", "1", "A",
            ], catch_exceptions=False)
            result = runner.invoke(main, [
                "decision", "resolve", "scout", "1", "B",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "already resolved" in result.output
        finally:
            os.chdir(old_cwd)


# --- CLI list command ---


class TestDecisionList:
    """Test `claws decision list`."""

    def test_list_empty(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(main, [
                "decision", "list", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "No pending decisions" in result.output
        finally:
            os.chdir(old_cwd)

    def test_list_pending_only(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            # Present two, resolve one
            runner.invoke(main, [
                "decision", "present", "scout", "Q1",
                "-o", "A", "-o", "B",
            ], catch_exceptions=False)
            runner.invoke(main, [
                "decision", "present", "scout", "Q2",
                "-o", "X", "-o", "Y",
            ], catch_exceptions=False)
            runner.invoke(main, [
                "decision", "resolve", "scout", "1", "A",
            ], catch_exceptions=False)

            result = runner.invoke(main, [
                "decision", "list", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Q2" in result.output
            assert "pending" in result.output
            # Q1 resolved, should not appear
            assert "Q1" not in result.output
        finally:
            os.chdir(old_cwd)

    def test_list_all(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            runner.invoke(main, [
                "decision", "present", "scout", "Q1",
                "-o", "A", "-o", "B",
            ], catch_exceptions=False)
            runner.invoke(main, [
                "decision", "resolve", "scout", "1", "A",
            ], catch_exceptions=False)
            runner.invoke(main, [
                "decision", "present", "scout", "Q2",
                "-o", "X", "-o", "Y",
            ], catch_exceptions=False)

            result = runner.invoke(main, [
                "decision", "list", "scout", "--all",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Q1" in result.output
            assert "Q2" in result.output
        finally:
            os.chdir(old_cwd)

    def test_list_shows_options(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            runner.invoke(main, [
                "decision", "present", "scout", "Framework?",
                "-o", "Django", "-o", "Flask", "-o", "FastAPI",
            ], catch_exceptions=False)
            result = runner.invoke(main, [
                "decision", "list", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Django" in result.output
            assert "Flask" in result.output
            assert "FastAPI" in result.output
        finally:
            os.chdir(old_cwd)


# --- CLI history command ---


class TestDecisionHistory:
    """Test `claws decision history`."""

    def test_history_empty(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(main, [
                "decision", "history", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "No resolved decisions" in result.output
        finally:
            os.chdir(old_cwd)

    def test_history_shows_resolved(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            runner.invoke(main, [
                "decision", "present", "scout", "Which DB?",
                "-o", "Postgres", "-o", "SQLite",
            ], catch_exceptions=False)
            runner.invoke(main, [
                "decision", "resolve", "scout", "1", "Postgres",
                "-r", "Need concurrent writes",
            ], catch_exceptions=False)

            result = runner.invoke(main, [
                "decision", "history", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Which DB?" in result.output
            assert "Postgres" in result.output
            assert "Need concurrent writes" in result.output
            assert "Decision #1" in result.output
        finally:
            os.chdir(old_cwd)

    def test_history_excludes_pending(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            runner.invoke(main, [
                "decision", "present", "scout", "Resolved one",
                "-o", "A", "-o", "B",
            ], catch_exceptions=False)
            runner.invoke(main, [
                "decision", "resolve", "scout", "1", "A",
            ], catch_exceptions=False)
            runner.invoke(main, [
                "decision", "present", "scout", "Still pending",
                "-o", "X", "-o", "Y",
            ], catch_exceptions=False)

            result = runner.invoke(main, [
                "decision", "history", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Resolved one" in result.output
            assert "Still pending" not in result.output
        finally:
            os.chdir(old_cwd)

    def test_history_multiple_resolved(self, tmp_path):
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            for i, (q, opts, res) in enumerate([
                ("API style?", ["REST", "GraphQL"], "REST"),
                ("Database?", ["Postgres", "MySQL"], "Postgres"),
                ("Deploy?", ["Docker", "Bare metal"], "Docker"),
            ], 1):
                runner.invoke(main, [
                    "decision", "present", "scout", q,
                    "-o", opts[0], "-o", opts[1],
                ], catch_exceptions=False)
                runner.invoke(main, [
                    "decision", "resolve", "scout", str(i), res,
                ], catch_exceptions=False)

            result = runner.invoke(main, [
                "decision", "history", "scout",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Decision #1" in result.output
            assert "Decision #2" in result.output
            assert "Decision #3" in result.output
        finally:
            os.chdir(old_cwd)


# --- Integration / edge cases ---


class TestDecisionIntegration:
    """Integration tests and edge cases."""

    def test_decisions_independent_of_scratchpad(self, tmp_path):
        """Decisions work without a scratchpad."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        # No scratchpad init needed
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(main, [
                "decision", "present", "scout", "Question?",
                "-o", "Yes", "-o", "No",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Decision #1 presented" in result.output
        finally:
            os.chdir(old_cwd)

    def test_decisions_survive_across_sessions(self, tmp_path):
        """Decisions persist in event log and can be read later."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")

        # Simulate "session 1": present a decision
        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={"number": 1, "question": "Q1", "options": ["A", "B"]},
        ))

        # Simulate "session 2": read decisions back
        spine2 = EventSpine(tmp_path)
        decisions = _get_decisions(spine2, "scout")
        assert len(decisions) == 1
        assert decisions[0]["question"] == "Q1"
        assert decisions[0]["status"] == "pending"

    def test_event_log_contains_both_types(self, tmp_path):
        """Both DECISION_PRESENTED and DECISION_RESOLVED coexist in log."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")

        spine = EventSpine(tmp_path)
        spine.emit(Event(
            type=DECISION_PRESENTED,
            agent="scout",
            data={"number": 1, "question": "Q?", "options": ["A"]},
        ))
        spine.emit(Event(
            type=DECISION_RESOLVED,
            agent="scout",
            data={"number": 1, "resolution": "A", "reasoning": "Only option"},
        ))

        all_events = spine.read_all()
        types = [e.type for e in all_events]
        assert DECISION_PRESENTED in types
        assert DECISION_RESOLVED in types

    def test_decision_numbers_per_agent(self, tmp_path):
        """Decision numbers are per-agent."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        _make_agent(tmp_path, "forge")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            # Both agents get decision #1
            result1 = runner.invoke(main, [
                "decision", "present", "scout", "Scout Q?",
                "-o", "A", "-o", "B",
            ], catch_exceptions=False)
            result2 = runner.invoke(main, [
                "decision", "present", "forge", "Forge Q?",
                "-o", "X", "-o", "Y",
            ], catch_exceptions=False)
            assert "Decision #1 presented" in result1.output
            assert "Decision #1 presented" in result2.output
        finally:
            os.chdir(old_cwd)

    def test_three_or_more_options(self, tmp_path):
        """Decisions can have more than two options."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()
            result = runner.invoke(main, [
                "decision", "present", "scout", "Framework?",
                "-o", "Django", "-o", "Flask", "-o", "FastAPI", "-o", "Starlette",
            ], catch_exceptions=False)
            assert result.exit_code == 0
            spine = EventSpine(tmp_path)
            events = spine.read_by_type(DECISION_PRESENTED)
            assert len(events[0].data["options"]) == 4
        finally:
            os.chdir(old_cwd)

    def test_full_lifecycle(self, tmp_path):
        """Full lifecycle: present → list → resolve → history."""
        _make_project(tmp_path)
        _make_agent(tmp_path, "scout")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            runner = CliRunner()

            # 1. Present
            result = runner.invoke(main, [
                "decision", "present", "scout", "Ship or iterate?",
                "-o", "Ship MVP now", "-o", "Iterate one more week",
                "-c", "Users are asking for the feature",
            ], catch_exceptions=False)
            assert result.exit_code == 0

            # 2. List (pending)
            result = runner.invoke(main, [
                "decision", "list", "scout",
            ], catch_exceptions=False)
            assert "Ship or iterate?" in result.output
            assert "pending" in result.output

            # 3. Resolve
            result = runner.invoke(main, [
                "decision", "resolve", "scout", "1", "Ship MVP now",
                "-r", "Users have waited long enough, iterate post-launch",
            ], catch_exceptions=False)
            assert result.exit_code == 0

            # 4. List (no pending)
            result = runner.invoke(main, [
                "decision", "list", "scout",
            ], catch_exceptions=False)
            assert "No pending decisions" in result.output

            # 5. History
            result = runner.invoke(main, [
                "decision", "history", "scout",
            ], catch_exceptions=False)
            assert "Ship or iterate?" in result.output
            assert "Ship MVP now" in result.output
            assert "iterate post-launch" in result.output
        finally:
            os.chdir(old_cwd)
