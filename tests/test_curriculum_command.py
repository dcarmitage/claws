"""Tests for the claws curriculum CLI command — list, show, create."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from claws.cli import main
from claws.config import CONFIG_FILENAME


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal claws project."""
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
        "eval": {
            "judges": ["logic", "consistency"],
            "threshold": 8.0,
        },
    }
    (tmp_path / CONFIG_FILENAME).write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False)
    )
    (tmp_path / "agents").mkdir(exist_ok=True)
    (tmp_path / ".claws").mkdir(exist_ok=True)
    return tmp_path


class TestCurriculumList:
    """Test the 'curriculum list' command."""

    def test_lists_builtin_curricula(self, tmp_path):
        """Should list built-in curricula (at minimum 'default')."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["curriculum", "list"],
                                   catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "default" in result.output

    def test_lists_project_curricula(self, tmp_path):
        """Should list curricula from project's curricula/ directory."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))

            # Create a project curriculum
            curricula_dir = Path(td) / "curricula"
            curricula_dir.mkdir(exist_ok=True)
            curriculum_data = {
                "name": "custom",
                "version": 1,
                "description": "Custom test curriculum",
                "defaults": {"eval_threshold": 8.0, "max_retries": 1, "retry_strategy": "reflect"},
                "phases": [],
            }
            (curricula_dir / "custom.yaml").write_text(
                yaml.dump(curriculum_data, default_flow_style=False, sort_keys=False)
            )

            result = runner.invoke(main, ["curriculum", "list"],
                                   catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "custom" in result.output

    def test_list_shows_source(self, tmp_path):
        """Should indicate whether a curriculum is built-in or project-local."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["curriculum", "list"],
                                   catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "built-in" in result.output


class TestCurriculumShow:
    """Test the 'curriculum show' command."""

    def test_show_default_curriculum(self, tmp_path):
        """Should display default curriculum details."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["curriculum", "show", "default"],
                                   catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "default" in result.output
        assert "foundation" in result.output.lower() or "Phase" in result.output

    def test_show_displays_phases(self, tmp_path):
        """Should display phase information."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["curriculum", "show", "default"],
                                   catch_exceptions=False)

        assert result.exit_code == 0, result.output
        # The default curriculum has foundation, domain, capstone phases
        assert "foundation" in result.output.lower()

    def test_show_displays_traits(self, tmp_path):
        """Should display personality trait pools."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["curriculum", "show", "default"],
                                   catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "Personality" in result.output or "Trait" in result.output

    def test_show_nonexistent_curriculum(self, tmp_path):
        """Should error when curriculum doesn't exist."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["curriculum", "show", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_show_displays_gate_info(self, tmp_path):
        """Should display gate (min_passed, min_avg_score) information."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["curriculum", "show", "default"],
                                   catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "min_passed" in result.output or "Gate" in result.output


class TestCurriculumCreate:
    """Test the 'curriculum create' command."""

    def test_create_scaffolds_yaml(self, tmp_path):
        """Should create a new curriculum YAML file."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["curriculum", "create", "mytest"],
                                   catch_exceptions=False)

            assert result.exit_code == 0, result.output

            yaml_path = Path(td) / "curricula" / "mytest.yaml"
            assert yaml_path.exists()

            data = yaml.safe_load(yaml_path.read_text())
            assert data["name"] == "mytest"
            assert "phases" in data
            assert "defaults" in data

    def test_create_refuses_existing(self, tmp_path):
        """Should error if curriculum already exists."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            # Create it once
            runner.invoke(main, ["curriculum", "create", "mytest"],
                          catch_exceptions=False)
            # Try again
            result = runner.invoke(main, ["curriculum", "create", "mytest"])

            assert result.exit_code != 0
            assert "already exists" in result.output

    def test_create_not_in_project(self, tmp_path):
        """Should error when not in a claws project."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(main, ["curriculum", "create", "mytest"])

            assert result.exit_code != 0

    def test_create_yaml_has_valid_schema(self, tmp_path):
        """Created YAML should have valid curriculum schema."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(main, ["curriculum", "create", "validated"],
                          catch_exceptions=False)

            yaml_path = Path(td) / "curricula" / "validated.yaml"
            data = yaml.safe_load(yaml_path.read_text())

            assert "name" in data
            assert "version" in data
            assert "defaults" in data
            assert "eval_threshold" in data["defaults"]
            assert "max_retries" in data["defaults"]
            assert "phases" in data
            assert len(data["phases"]) >= 1
            assert "tasks" in data["phases"][0]
            assert "gate" in data["phases"][0]
