"""Tests for claws init command."""

import os
import yaml
import pytest
from pathlib import Path
from click.testing import CliRunner

from claws.cli import main


class TestInitDirect:
    """Tests for init with explicit --provider/--model flags (non-interactive)."""

    def test_creates_project_directory(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj", "--provider", "anthropic"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            assert (Path(td) / "myproj").is_dir()

    def test_project_structure(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj", "--provider", "anthropic"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            proj = Path(td) / "myproj"
            assert (proj / "claws.yaml").is_file()
            assert (proj / ".gitignore").is_file()
            assert (proj / "agents").is_dir()
            assert (proj / ".claws").is_dir()

    def test_claws_yaml_contents(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            runner.invoke(
                main, ["init", "myproj", "--provider", "anthropic"],
                catch_exceptions=False,
            )
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert config["project"] == "myproj"
            assert config["version"] == 2
            assert "default" in config["providers"]

    def test_event_emitted(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            runner.invoke(
                main, ["init", "myproj", "--provider", "anthropic"],
                catch_exceptions=False,
            )
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
                main, ["init", "myproj", "--provider", "openai-compatible"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert config["providers"]["default"]["type"] == "openai-compatible"

    def test_custom_model(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj", "--model", "codex-5.3"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert config["providers"]["default"]["model"] == "codex-5.3"

    def test_existing_directory_error(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            Path(td, "myproj").mkdir()
            result = runner.invoke(main, ["init", "myproj", "--provider", "anthropic"])
            assert result.exit_code != 0
            assert "already exists" in result.output

    def test_gitignore_contents(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            runner.invoke(
                main, ["init", "myproj", "--provider", "anthropic"],
                catch_exceptions=False,
            )
            gitignore = (Path(td) / "myproj" / ".gitignore").read_text()
            assert ".claws/" in gitignore
            assert ".env" in gitignore

    def test_default_model_for_anthropic(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            runner.invoke(
                main, ["init", "myproj", "--provider", "anthropic"],
                catch_exceptions=False,
            )
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert config["providers"]["default"]["model"] == "claude-opus-4-6"

    def test_default_model_for_openai(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            runner.invoke(
                main, ["init", "myproj", "--provider", "openai-compatible"],
                catch_exceptions=False,
            )
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert config["providers"]["default"]["model"] == "codex-5.3"


class TestInitInteractive:
    """Tests for the interactive guided setup wizard."""

    def test_interactive_default_anthropic(self, tmp_path):
        """No flags + Enter (default choice) selects Anthropic."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj"],
                input="\n",
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert config["providers"]["default"]["type"] == "anthropic"
            assert config["providers"]["default"]["model"] == "claude-opus-4-6"

    def test_interactive_choose_openai(self, tmp_path):
        """Choosing '2' selects OpenAI with codex-5.3."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj"],
                input="2\n",
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert config["providers"]["default"]["type"] == "openai-compatible"
            assert config["providers"]["default"]["model"] == "codex-5.3"
            assert "openai.com" in config["providers"]["default"]["base_url"]

    def test_interactive_choose_openrouter(self, tmp_path):
        """Choosing '3' selects OpenRouter."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj"],
                input="3\n",
                catch_exceptions=False,
            )
            assert result.exit_code == 0, result.output
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            assert config["providers"]["default"]["type"] == "openai-compatible"
            assert "openrouter.ai" in config["providers"]["default"]["base_url"]

    def test_interactive_shows_provider_menu(self, tmp_path):
        """The wizard output includes the provider choices."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj"],
                input="1\n",
                catch_exceptions=False,
            )
            assert "Anthropic" in result.output
            assert "OpenAI" in result.output
            assert "OpenRouter" in result.output

    def test_interactive_shows_api_key_instructions(self, tmp_path):
        """When no API key is set, the wizard shows setup instructions."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            # Ensure no key is set
            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)
            result = runner.invoke(
                main, ["init", "myproj"],
                input="1\n",
                catch_exceptions=False,
            )
            assert "ANTHROPIC_API_KEY" in result.output
            assert "console.anthropic.com" in result.output

    def test_interactive_detects_existing_key(self, tmp_path, monkeypatch):
        """When API key is already set, the wizard confirms it."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj"],
                input="1\n",
                catch_exceptions=False,
            )
            assert "detected" in result.output

    def test_interactive_creates_valid_project(self, tmp_path):
        """Interactive path creates the same project structure as direct."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj"],
                input="1\n",
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            proj = Path(td) / "myproj"
            assert (proj / "claws.yaml").is_file()
            assert (proj / ".gitignore").is_file()
            assert (proj / "agents").is_dir()
            assert (proj / ".claws").is_dir()
            assert (proj / ".claws" / "events.jsonl").is_file()

    def test_interactive_openai_includes_base_url(self, tmp_path):
        """OpenAI config includes base_url and api_key_env."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj"],
                input="2\n",
                catch_exceptions=False,
            )
            config = yaml.safe_load((Path(td) / "myproj" / "claws.yaml").read_text())
            prov = config["providers"]["default"]
            assert prov["base_url"] == "https://api.openai.com/v1"
            assert prov["api_key_env"] == "OPENAI_API_KEY"

    def test_interactive_shows_next_steps(self, tmp_path):
        """The wizard shows next steps including claws doctor."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main, ["init", "myproj"],
                input="1\n",
                catch_exceptions=False,
            )
            assert "claws doctor" in result.output
            assert "claws agent create" in result.output
