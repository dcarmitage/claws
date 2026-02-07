"""Shared fixtures for claws test suite."""

import pytest
import yaml
from pathlib import Path
from click.testing import CliRunner

from claws.config import (
    ProjectConfig,
    ProviderConfig,
    AgentConfig,
    EvalConfig,
    CONFIG_FILENAME,
)


@pytest.fixture
def cli_runner():
    """Return a Click CliRunner."""
    return CliRunner()


@pytest.fixture
def project_dir(tmp_path):
    """Create a valid claws project directory inside tmp_path.

    Returns the project root path with:
      - claws.yaml (valid config with a default anthropic provider)
      - agents/  directory
      - .claws/  directory
    """
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
    config_path = tmp_path / CONFIG_FILENAME
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    (tmp_path / "agents").mkdir()
    (tmp_path / ".claws").mkdir()
    return tmp_path


@pytest.fixture
def claws_config():
    """Return a valid ProjectConfig object for tests."""
    return ProjectConfig(
        project="test-project",
        version=2,
        providers={
            "default": ProviderConfig(
                name="default",
                type="anthropic",
                model="claude-sonnet-4-5-20250929",
            ),
        },
        agents={},
        eval=EvalConfig(
            judges=["logic", "consistency"],
            threshold=8.0,
        ),
    )
