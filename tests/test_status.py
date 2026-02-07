"""Tests for claws status command."""

import json
import yaml
import pytest
from pathlib import Path
from click.testing import CliRunner

from claws.cli import main
from claws.events import EventSpine, Event, TASK_STARTED, TASK_COMPLETED, TASK_FAILED, AGENT_CREATED


def _make_project(td_path: Path, agents=None):
    """Helper: create a project with optional agents in config."""
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


class TestStatus:
    def test_empty_project(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "test-project" in result.output

    def test_shows_agent_table(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            agents = {
                "scout": {"role": "researcher", "provider": "default", "machine": "local"},
            }
            _make_project(Path(td), agents=agents)
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "scout" in result.output
            assert "researcher" in result.output

    def test_agent_status_new(self, tmp_path):
        """Agent with no events should show 'new' status."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            agents = {
                "scout": {"role": "researcher", "provider": "default", "machine": "local"},
            }
            _make_project(Path(td), agents=agents)
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "new" in result.output

    def test_agent_status_running(self, tmp_path):
        """Agent whose last event is task.started should show 'running'."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            agents = {
                "scout": {"role": "researcher", "provider": "default", "machine": "local"},
            }
            _make_project(Path(td), agents=agents)
            spine = EventSpine(Path(td))
            spine.emit(Event(type=TASK_STARTED, agent="scout", data={"task": "hello"}))
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "running" in result.output

    def test_agent_status_idle(self, tmp_path):
        """Agent whose last event is task.completed should show 'idle'."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            agents = {
                "scout": {"role": "researcher", "provider": "default", "machine": "local"},
            }
            _make_project(Path(td), agents=agents)
            spine = EventSpine(Path(td))
            spine.emit(Event(type=TASK_STARTED, agent="scout", data={"task": "t"}))
            spine.emit(Event(
                type=TASK_COMPLETED, agent="scout",
                data={"task": "t", "tokens_in": 10, "tokens_out": 20, "elapsed_s": 1.5},
            ))
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "idle" in result.output

    def test_agent_status_failed(self, tmp_path):
        """Agent whose last event is task.failed should show 'failed'."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            agents = {
                "scout": {"role": "researcher", "provider": "default", "machine": "local"},
            }
            _make_project(Path(td), agents=agents)
            spine = EventSpine(Path(td))
            spine.emit(Event(type=TASK_STARTED, agent="scout", data={"task": "t"}))
            spine.emit(Event(type=TASK_FAILED, agent="scout", data={"error": "boom"}))
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "failed" in result.output

    def test_shows_recent_events(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            agents = {
                "scout": {"role": "researcher", "provider": "default", "machine": "local"},
            }
            _make_project(Path(td), agents=agents)
            spine = EventSpine(Path(td))
            spine.emit(Event(type=AGENT_CREATED, agent="scout", data={"role": "researcher"}))
            spine.emit(Event(type=TASK_STARTED, agent="scout", data={"task": "analyze code"}))
            spine.emit(Event(
                type=TASK_COMPLETED, agent="scout",
                data={"task": "analyze code", "tokens_in": 50, "tokens_out": 100, "elapsed_s": 2.3},
            ))
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Recent Activity" in result.output

    def test_shows_stats(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            spine = EventSpine(Path(td))
            spine.emit(Event(
                type=TASK_COMPLETED, agent="a",
                data={"tokens_in": 100, "tokens_out": 200, "elapsed_s": 5.0},
            ))
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "1 tasks completed" in result.output

    def test_no_project_error(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["status"])
            assert result.exit_code != 0

    def test_events_limit_option(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            spine = EventSpine(Path(td))
            for i in range(20):
                spine.emit(Event(type=TASK_STARTED, agent=f"a{i}", data={"task": f"t{i}"}))
            result = runner.invoke(
                main, ["status", "--events", "5"], catch_exceptions=False
            )
            assert result.exit_code == 0
