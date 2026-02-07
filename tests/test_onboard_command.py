"""Tests for the claws agent onboard CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from claws.cli import main
from claws.config import CONFIG_FILENAME
from claws.onboarding.state import OnboardingState


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal claws project with an agent."""
    config = {
        "project": "test-project",
        "version": 2,
        "providers": {
            "default": {
                "type": "openai-compatible",
                "model": "test-model",
                "base_url": "http://localhost:9999/v1",
            },
        },
        "agents": {
            "scout": {
                "role": "researcher",
                "provider": "default",
                "machine": "local",
            },
        },
        "eval": {
            "judges": ["logic", "consistency"],
            "threshold": 8.0,
        },
    }
    (tmp_path / CONFIG_FILENAME).write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False)
    )
    (tmp_path / "agents" / "scout" / "output").mkdir(parents=True)
    (tmp_path / "agents" / "scout" / "identity.md").write_text("# scout\n\n## Role\nresearcher\n")
    (tmp_path / "agents" / "scout" / "memory.md").write_text("# Memory -- scout\n")
    (tmp_path / ".claws").mkdir(exist_ok=True)
    return tmp_path


def _make_curriculum(tmp_path: Path, name: str = "default") -> None:
    """Create a simple curriculum YAML for testing."""
    curriculum = {
        "name": name,
        "version": 1,
        "description": "Test curriculum",
        "defaults": {
            "eval_threshold": 7.0,
            "max_retries": 0,
            "retry_strategy": "reflect",
        },
        "personality": {
            "temperature_offset": 0.1,
            "traits": {
                "style": {
                    "pick": 1,
                    "pool": ["methodical"],
                },
            },
            "reflections": [],
        },
        "phases": [
            {
                "name": "foundation",
                "description": "Basic tasks",
                "gate": {"min_passed": 1, "min_avg_score": 7.0},
                "tasks": [
                    {
                        "id": "t01",
                        "name": "Test task",
                        "template": "Do something simple.",
                    },
                ],
            },
        ],
    }
    curricula_dir = tmp_path / "curricula"
    curricula_dir.mkdir(exist_ok=True)
    (curricula_dir / f"{name}.yaml").write_text(
        yaml.dump(curriculum, default_flow_style=False, sort_keys=False)
    )


def _make_judge_response(judge: str, overall: float) -> str:
    """Create a mock judge JSON response string."""
    return json.dumps({
        "judge": judge,
        "scores": {"dim_a": overall, "dim_b": overall},
        "overall": overall,
        "tier": "good" if overall >= 7.0 else "poor",
        "rationale": f"Test rationale for {judge}.",
    })


def _make_mock_provider(overall_score: float = 8.5):
    """Create a mock provider for onboarding tests."""
    mock_provider = MagicMock()
    call_count = 0

    async def mock_complete(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count % 3 == 1:
            result.content = "This is the agent's response."
        elif call_count % 3 == 2:
            result.content = _make_judge_response("logic", overall_score)
        else:
            result.content = _make_judge_response("consistency", overall_score)
        return result

    mock_provider.complete = mock_complete
    return mock_provider


class TestOnboardCommand:
    """Test the claws agent onboard CLI command."""

    def test_onboard_success(self, tmp_path):
        """Successful onboarding should exit 0."""
        project_root = _make_project(tmp_path)
        _make_curriculum(tmp_path)

        mock_provider = _make_mock_provider(8.5)
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=project_root) as td:
            with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
                result = runner.invoke(
                    main,
                    ["agent", "onboard", "scout", "--curriculum", "default", "--seed", "42"],
                )

            assert result.exit_code == 0, result.output
            assert "complete" in result.output.lower() or "graduated" in result.output.lower()

    def test_onboard_no_agent(self, tmp_path):
        """Onboarding a nonexistent agent should fail."""
        project_root = _make_project(tmp_path)
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=project_root) as td:
            result = runner.invoke(
                main,
                ["agent", "onboard", "ghost"],
            )

            assert result.exit_code != 0
            assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_onboard_already_completed(self, tmp_path):
        """Onboarding an already-onboarded agent should error without --force."""
        project_root = _make_project(tmp_path)
        _make_curriculum(tmp_path)

        # Create completed state
        state_dir = project_root / "agents" / "scout" / ".onboarding"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_data = {
            "agent": "scout",
            "curriculum": "default",
            "status": "completed",
            "seed": 42,
            "current_phase": 0,
            "current_task": 0,
            "phases": [],
        }
        (state_dir / "state.yaml").write_text(
            yaml.dump(state_data, default_flow_style=False, sort_keys=False)
        )

        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=project_root) as td:
            result = runner.invoke(
                main,
                ["agent", "onboard", "scout"],
            )

            assert result.exit_code != 0
            assert "already" in result.output.lower()

    def test_onboard_invalid_curriculum(self, tmp_path):
        """Onboarding with a nonexistent curriculum should fail."""
        project_root = _make_project(tmp_path)
        runner = CliRunner()

        mock_provider = _make_mock_provider(8.5)

        with runner.isolated_filesystem(temp_dir=project_root) as td:
            with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
                result = runner.invoke(
                    main,
                    ["agent", "onboard", "scout", "--curriculum", "nonexistent"],
                )

            assert result.exit_code != 0

    def test_onboard_seed_flag(self, tmp_path):
        """The --seed flag should be passed to the engine."""
        project_root = _make_project(tmp_path)
        _make_curriculum(tmp_path)

        mock_provider = _make_mock_provider(8.5)
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=project_root) as td:
            with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
                result = runner.invoke(
                    main,
                    ["agent", "onboard", "scout", "--seed", "12345"],
                )

            assert result.exit_code == 0, result.output
            # Verify seed in state
            state_path = Path(td) / "agents" / "scout" / ".onboarding" / "state.yaml"
            if state_path.exists():
                state = OnboardingState.load(state_path)
                assert state.seed == 12345

    def test_onboard_resume_flag(self, tmp_path):
        """The --resume flag should resume from saved state."""
        project_root = _make_project(tmp_path)
        _make_curriculum(tmp_path)

        # Create a partial state
        state_dir = project_root / "agents" / "scout" / ".onboarding"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_data = {
            "agent": "scout",
            "curriculum": "default",
            "status": "in_progress",
            "seed": 42,
            "traits": {"style": "methodical"},
            "current_phase": 0,
            "current_task": 0,
            "phases": [
                {
                    "name": "foundation",
                    "status": "pending",
                    "tasks": [
                        {"id": "t01", "status": "pending", "attempts": 0, "max_retries": 0},
                    ],
                },
            ],
        }
        (state_dir / "state.yaml").write_text(
            yaml.dump(state_data, default_flow_style=False, sort_keys=False)
        )

        mock_provider = _make_mock_provider(8.5)
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=project_root) as td:
            with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
                result = runner.invoke(
                    main,
                    ["agent", "onboard", "scout", "--resume"],
                )

            assert result.exit_code == 0, result.output


class TestOnboardNotInProject:
    """Test error when not in a claws project."""

    def test_not_in_project(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(
                main,
                ["agent", "onboard", "scout"],
            )
            assert result.exit_code != 0
            assert "not in a claws project" in result.output.lower() or "error" in result.output.lower()
