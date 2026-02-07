"""Tests for claws agent command — create, list, info."""

import json
import yaml
import pytest
from pathlib import Path
from click.testing import CliRunner

from claws.cli import main


def _make_project(td_path: Path):
    """Helper: create a minimal project inside td_path."""
    config = {
        "project": "test-project",
        "version": 2,
        "providers": {
            "default": {
                "type": "anthropic",
                "model": "claude-sonnet-4-5-20250929",
            },
        },
        "agents": {},
        "eval": {"judges": ["logic", "consistency"], "threshold": 8.0},
    }
    (td_path / "claws.yaml").write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    (td_path / "agents").mkdir(exist_ok=True)
    (td_path / ".claws").mkdir(exist_ok=True)


class TestAgentCreate:
    def test_creates_agent_directory(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            agent_dir = Path(td) / "agents" / "scout"
            assert agent_dir.is_dir()

    def test_creates_identity_md(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            identity = (Path(td) / "agents" / "scout" / "identity.md").read_text()
            assert "scout" in identity
            assert "researcher" in identity

    def test_creates_memory_md(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            memory = (Path(td) / "agents" / "scout" / "memory.md").read_text()
            assert "scout" in memory

    def test_creates_output_dir(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            assert (Path(td) / "agents" / "scout" / "output").is_dir()

    def test_updates_claws_yaml(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            config = yaml.safe_load((Path(td) / "claws.yaml").read_text())
            assert "scout" in config["agents"]
            assert config["agents"]["scout"]["role"] == "researcher"

    def test_emits_agent_created_event(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            events = (Path(td) / ".claws" / "events.jsonl").read_text().strip().split("\n")
            event = json.loads(events[-1])
            assert event["type"] == "agent.created"
            assert event["agent"] == "scout"

    def test_duplicate_agent_error(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            result = runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
            )
            assert result.exit_code != 0
            assert "already exists" in result.output

    def test_not_in_project_error(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            # No _make_project — bare directory
            result = runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
            )
            assert result.exit_code != 0

    def test_custom_provider(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["agent", "create", "scout", "--role", "researcher", "--provider", "fast"],
                catch_exceptions=False,
            )
            config = yaml.safe_load((Path(td) / "claws.yaml").read_text())
            assert config["agents"]["scout"]["provider"] == "fast"


class TestAgentList:
    def test_empty_project(self, tmp_path):
        """Empty project with agents/ dir shows an empty table (Agents header)."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["agent", "list"], catch_exceptions=False)
            assert result.exit_code == 0
            # agents/ dir exists but is empty -- shows empty table with header
            assert "Agents" in result.output

    def test_lists_agents(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            result = runner.invoke(main, ["agent", "list"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "scout" in result.output
            assert "researcher" in result.output


class TestAgentInfo:
    def test_shows_identity(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main, ["agent", "create", "scout", "--role", "researcher"],
                catch_exceptions=False,
            )
            result = runner.invoke(main, ["agent", "info", "scout"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "scout" in result.output

    def test_nonexistent_agent_error(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["agent", "info", "ghost"])
            assert result.exit_code != 0
            assert "not found" in result.output
