"""Tests for claws init command."""

import os
import yaml
import pytest
from pathlib import Path
from click.testing import CliRunner

from claws.cli import main


class TestInit:
    def test_creates_project_directory(self, tmp_path):
        """init creates the named directory in cwd."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(main, ["init", "myproj"], catch_exceptions=False)
            assert result.exit_code == 0, result.output
            assert (Path(td) / "myproj").is_dir()

    def test_project_structure(self, tmp_path):
        """init should create claws.yaml, .gitignore, agents/, .claws/."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(main, ["init", "myproj"], catch_exceptions=False)
            assert result.exit_code == 0, result.output
            proj = Path(td) / "myproj"
            assert proj.is_dir()
            assert (proj / "claws.yaml").is_file()
            assert (proj / ".gitignore").is_file()
            assert (proj / "agents").is_dir()
            assert (proj / ".claws").is_dir()

    def test_claws_yaml_contents(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            runner.invoke(main, ["init", "myproj"], catch_exceptions=False)
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert config["project"] == "myproj"
            assert config["version"] == 2
            assert "default" in config["providers"]

    def test_event_emitted(self, tmp_path):
        """init should emit a project.initialized event."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            runner.invoke(main, ["init", "myproj"], catch_exceptions=False)
            events_file = Path(td) / "myproj" / ".claws" / "events.jsonl"
            assert events_file.exists()
            import json
            line = events_file.read_text().strip()
            event = json.loads(line)
            assert event["type"] == "project.initialized"
            assert event["data"]["project"] == "myproj"

    def test_custom_provider(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj", "--provider", "ollama"], catch_exceptions=False
            )
            assert result.exit_code == 0
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert config["providers"]["default"]["type"] == "ollama"

    def test_custom_model(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj", "--model", "gpt-4o"], catch_exceptions=False
            )
            assert result.exit_code == 0
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert config["providers"]["default"]["model"] == "gpt-4o"

    def test_existing_directory_error(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            Path(td, "myproj").mkdir()
            result = runner.invoke(main, ["init", "myproj"])
            assert result.exit_code != 0
            assert "already exists" in result.output

    def test_gitignore_contents(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            runner.invoke(main, ["init", "myproj"], catch_exceptions=False)
            gitignore = (Path(td) / "myproj" / ".gitignore").read_text()
            assert ".claws/" in gitignore
            assert ".env" in gitignore

    def test_default_model_for_anthropic(self, tmp_path):
        """Default model for anthropic should be claude-sonnet-4-5-20250929."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            runner.invoke(main, ["init", "myproj"], catch_exceptions=False)
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert "claude" in config["providers"]["default"]["model"]
