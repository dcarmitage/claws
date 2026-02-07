"""Tests for claws.config — YAML loading, path resolution, dataclasses."""

import os
import pytest
import yaml
from pathlib import Path

from claws.config import (
    ProviderConfig,
    EvalConfig,
    AgentConfig,
    ProjectConfig,
    find_project_root,
    load_config,
    CONFIG_FILENAME,
)


# ---------------------------------------------------------------------------
# ProviderConfig
# ---------------------------------------------------------------------------

class TestProviderConfig:
    def test_api_key_from_env_var(self, monkeypatch):
        """api_key_env should resolve via os.environ."""
        monkeypatch.setenv("MY_KEY", "secret-123")
        cfg = ProviderConfig(name="p", type="anthropic", model="m", api_key_env="MY_KEY")
        assert cfg.api_key == "secret-123"

    def test_api_key_auto_anthropic(self, monkeypatch):
        """Anthropic type auto-discovers ANTHROPIC_API_KEY."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
        cfg = ProviderConfig(name="p", type="anthropic", model="m")
        assert cfg.api_key == "ant-key"

    def test_api_key_auto_openai(self, monkeypatch):
        """OpenAI type auto-discovers OPENAI_API_KEY."""
        monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
        cfg = ProviderConfig(name="p", type="openai", model="m")
        assert cfg.api_key == "oai-key"

    def test_api_key_auto_openai_compatible(self, monkeypatch):
        """openai-compatible type auto-discovers OPENAI_API_KEY."""
        monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
        cfg = ProviderConfig(name="p", type="openai-compatible", model="m")
        assert cfg.api_key == "oai-key"

    def test_api_key_none_for_ollama(self, monkeypatch):
        """Ollama type returns None (no standard env var)."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        cfg = ProviderConfig(name="p", type="ollama", model="m")
        assert cfg.api_key is None

    def test_api_key_env_takes_precedence(self, monkeypatch):
        """Explicit api_key_env should be used even for anthropic type."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fallback")
        monkeypatch.setenv("CUSTOM_KEY", "custom-val")
        cfg = ProviderConfig(name="p", type="anthropic", model="m", api_key_env="CUSTOM_KEY")
        assert cfg.api_key == "custom-val"

    def test_base_url_default_none(self):
        cfg = ProviderConfig(name="p", type="anthropic", model="m")
        assert cfg.base_url is None


# ---------------------------------------------------------------------------
# EvalConfig
# ---------------------------------------------------------------------------

class TestEvalConfig:
    def test_defaults(self):
        cfg = EvalConfig()
        assert cfg.judges == ["logic", "consistency"]
        assert cfg.threshold == 8.0

    def test_custom_values(self):
        cfg = EvalConfig(judges=["style"], threshold=7.5)
        assert cfg.judges == ["style"]
        assert cfg.threshold == 7.5


# ---------------------------------------------------------------------------
# AgentConfig
# ---------------------------------------------------------------------------

class TestAgentConfig:
    def test_defaults(self):
        cfg = AgentConfig(name="scout", role="researcher")
        assert cfg.provider == "default"
        assert cfg.machine == "local"

    def test_custom(self):
        cfg = AgentConfig(name="a", role="r", provider="fast", machine="remote")
        assert cfg.provider == "fast"
        assert cfg.machine == "remote"


# ---------------------------------------------------------------------------
# ProjectConfig
# ---------------------------------------------------------------------------

class TestProjectConfig:
    def test_construction(self, claws_config):
        assert claws_config.project == "test-project"
        assert claws_config.version == 2

    def test_default_provider(self, claws_config):
        dp = claws_config.default_provider
        assert dp is not None
        assert dp.type == "anthropic"

    def test_default_provider_missing(self):
        cfg = ProjectConfig(project="x", providers={})
        assert cfg.default_provider is None


# ---------------------------------------------------------------------------
# find_project_root
# ---------------------------------------------------------------------------

class TestFindProjectRoot:
    def test_finds_in_current_dir(self, project_dir):
        assert find_project_root(project_dir) == project_dir

    def test_finds_in_parent(self, project_dir):
        child = project_dir / "a" / "b"
        child.mkdir(parents=True)
        assert find_project_root(child) == project_dir

    def test_returns_none_when_missing(self, tmp_path):
        assert find_project_root(tmp_path) is None


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_valid_yaml(self, project_dir):
        cfg = load_config(project_dir)
        assert cfg.project == "test-project"
        assert "default" in cfg.providers
        assert cfg.providers["default"].type == "anthropic"

    def test_missing_config_raises(self, tmp_path):
        """Passing a dir without claws.yaml should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path)

    def test_empty_yaml(self, tmp_path):
        """An empty YAML file should still return a ProjectConfig."""
        (tmp_path / CONFIG_FILENAME).write_text("")
        cfg = load_config(tmp_path)
        assert cfg.project == tmp_path.name
        assert cfg.providers == {}
        assert cfg.agents == {}

    def test_agents_in_config(self, project_dir):
        """Agents defined in YAML should be parsed."""
        config_path = project_dir / CONFIG_FILENAME
        raw = yaml.safe_load(config_path.read_text())
        raw["agents"] = {
            "scout": {"role": "researcher", "provider": "default", "machine": "local"},
        }
        config_path.write_text(yaml.dump(raw, default_flow_style=False))
        cfg = load_config(project_dir)
        assert "scout" in cfg.agents
        assert cfg.agents["scout"].role == "researcher"

    def test_provider_base_url(self, project_dir):
        config_path = project_dir / CONFIG_FILENAME
        raw = yaml.safe_load(config_path.read_text())
        raw["providers"]["custom"] = {
            "type": "openai-compatible",
            "model": "foo",
            "base_url": "http://localhost:8080/v1",
            "api_key_env": "MY_KEY",
        }
        config_path.write_text(yaml.dump(raw, default_flow_style=False))
        cfg = load_config(project_dir)
        assert cfg.providers["custom"].base_url == "http://localhost:8080/v1"
        assert cfg.providers["custom"].api_key_env == "MY_KEY"
