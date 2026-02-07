"""Tests for claws run command — task execution with mocked providers."""

import json
import yaml
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner

from claws.cli import main
from claws.providers.base import Response


def _make_project_with_agent(td_path: Path, agent_name="scout", role="researcher"):
    """Helper: create a project with one agent ready to run."""
    config = {
        "project": "test-project",
        "version": 2,
        "providers": {
            "default": {
                "type": "anthropic",
                "model": "claude-sonnet-4-5-20250929",
            },
        },
        "agents": {
            agent_name: {
                "role": role,
                "provider": "default",
                "machine": "local",
            },
        },
        "eval": {"judges": ["logic", "consistency"], "threshold": 8.0},
    }
    (td_path / "claws.yaml").write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False)
    )
    (td_path / "agents").mkdir(exist_ok=True)
    agent_dir = td_path / "agents" / agent_name
    agent_dir.mkdir(exist_ok=True)
    (agent_dir / "output").mkdir(exist_ok=True)
    (agent_dir / "identity.md").write_text(f"# {agent_name}\n\n## Role\n{role}\n")
    (agent_dir / "memory.md").write_text(f"# Memory -- {agent_name}\n")
    (td_path / ".claws").mkdir(exist_ok=True)


def _mock_provider():
    """Return a mock provider that returns a fixed Response from complete()."""
    mock_prov = MagicMock()
    mock_prov.complete = AsyncMock(
        return_value=Response(
            content="Mock answer from the agent.",
            model="mock-model",
            tokens_in=10,
            tokens_out=20,
        )
    )

    async def mock_stream(messages, **kwargs):
        for chunk in ["Mock ", "streamed ", "answer."]:
            yield chunk

    mock_prov.stream = MagicMock(side_effect=mock_stream)
    return mock_prov


class TestRunSuccess:
    @patch("claws.commands.run.get_provider")
    def test_complete_mode(self, mock_get_provider, tmp_path):
        mock_get_provider.return_value = _mock_provider()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project_with_agent(Path(td))
            result = runner.invoke(
                main,
                ["run", "scout", "do something", "--no-stream"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            assert "Mock answer from the agent." in result.output

    @patch("claws.commands.run.get_provider")
    def test_stream_mode(self, mock_get_provider, tmp_path):
        mock_get_provider.return_value = _mock_provider()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project_with_agent(Path(td))
            result = runner.invoke(
                main,
                ["run", "scout", "do something"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            # Streamed chunks should appear
            assert "Mock" in result.output

    @patch("claws.commands.run.get_provider")
    def test_saves_output(self, mock_get_provider, tmp_path):
        mock_get_provider.return_value = _mock_provider()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project_with_agent(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "do something", "--no-stream"],
                catch_exceptions=False,
            )
            output_files = list((Path(td) / "agents" / "scout" / "output").glob("*.md"))
            assert len(output_files) == 1
            content = output_files[0].read_text()
            assert "do something" in content
            assert "Mock answer" in content

    @patch("claws.commands.run.get_provider")
    def test_no_save(self, mock_get_provider, tmp_path):
        mock_get_provider.return_value = _mock_provider()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project_with_agent(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "do something", "--no-stream", "--no-save"],
                catch_exceptions=False,
            )
            output_files = list((Path(td) / "agents" / "scout" / "output").glob("*.md"))
            assert len(output_files) == 0

    @patch("claws.commands.run.get_provider")
    def test_emits_started_and_completed_events(self, mock_get_provider, tmp_path):
        mock_get_provider.return_value = _mock_provider()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project_with_agent(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "do something", "--no-stream"],
                catch_exceptions=False,
            )
            lines = (Path(td) / ".claws" / "events.jsonl").read_text().strip().split("\n")
            types = [json.loads(l)["type"] for l in lines]
            assert "task.started" in types
            assert "task.completed" in types


class TestRunFailure:
    @patch("claws.commands.run.get_provider")
    def test_provider_error_emits_failed_event(self, mock_get_provider, tmp_path):
        mock_prov = MagicMock()
        mock_prov.complete = AsyncMock(side_effect=RuntimeError("API is down"))
        mock_get_provider.return_value = mock_prov
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project_with_agent(Path(td))
            result = runner.invoke(
                main,
                ["run", "scout", "fail task", "--no-stream"],
            )
            assert result.exit_code != 0
            lines = (Path(td) / ".claws" / "events.jsonl").read_text().strip().split("\n")
            types = [json.loads(l)["type"] for l in lines]
            assert "task.started" in types
            assert "task.failed" in types

    def test_nonexistent_agent_error(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project_with_agent(Path(td))
            result = runner.invoke(main, ["run", "ghost", "do something"])
            assert result.exit_code != 0
            assert "not found" in result.output

    def test_no_project_error(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["run", "scout", "something"])
            assert result.exit_code != 0
