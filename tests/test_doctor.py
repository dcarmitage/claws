"""Tests for the claws doctor command."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import yaml
from click.testing import CliRunner

from claws.config import CONFIG_FILENAME
from claws.commands.doctor import (
    doctor,
    _check_project,
    _check_provider,
    _check_api_key,
    _check_connectivity,
    _get_expected_env_var,
    _get_help_url,
)


def _make_config(
    tmp_path: Path,
    provider_type: str = "anthropic",
    model: str = "claude-sonnet-4-5-20250929",
    base_url: str | None = None,
    api_key_env: str | None = None,
    include_provider: bool = True,
) -> Path:
    """Create a minimal claws.yaml. Returns project root path."""
    config: dict = {
        "project": "test-project",
        "version": 2,
    }
    if include_provider:
        provider_cfg: dict = {
            "type": provider_type,
            "model": model,
        }
        if base_url:
            provider_cfg["base_url"] = base_url
        if api_key_env:
            provider_cfg["api_key_env"] = api_key_env
        config["providers"] = {"default": provider_cfg}

    (tmp_path / CONFIG_FILENAME).write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False)
    )
    (tmp_path / ".claws").mkdir(exist_ok=True)
    return tmp_path


# --- Unit tests for check functions ---


class TestCheckProject:
    """Test _check_project function."""

    def test_no_project(self, tmp_path):
        """No claws.yaml should report fail."""
        with patch("claws.commands.doctor.find_project_root", return_value=None):
            ok, detail, root = _check_project()
            assert ok is False
            assert root is None
            assert "No claws.yaml" in detail

    def test_with_project(self, tmp_path):
        """With claws.yaml should report pass."""
        with patch("claws.commands.doctor.find_project_root", return_value=tmp_path):
            ok, detail, root = _check_project()
            assert ok is True
            assert root == tmp_path


class TestCheckProvider:
    """Test _check_provider function."""

    def test_no_provider(self, tmp_path):
        """No provider configured should report fail."""
        _make_config(tmp_path, include_provider=False)
        ok, detail, cfg = _check_provider(tmp_path)
        assert ok is False
        assert "No providers" in detail
        assert cfg is None

    def test_with_provider(self, tmp_path):
        """Configured provider should report pass."""
        _make_config(tmp_path)
        ok, detail, cfg = _check_provider(tmp_path)
        assert ok is True
        assert "anthropic" in detail
        assert cfg is not None
        assert cfg.type == "anthropic"

    def test_with_openai_provider(self, tmp_path):
        """OpenAI-compatible provider should report pass with details."""
        _make_config(tmp_path, provider_type="openai-compatible", model="gpt-4o",
                     base_url="https://api.openai.com/v1")
        ok, detail, cfg = _check_provider(tmp_path)
        assert ok is True
        assert "openai-compatible" in detail
        assert "gpt-4o" in detail


class TestCheckApiKey:
    """Test _check_api_key function."""

    def test_key_available_via_env(self, tmp_path):
        """API key available via env var should report pass."""
        from claws.config import ProviderConfig
        cfg = ProviderConfig(name="default", type="anthropic", model="claude-sonnet-4-5-20250929")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}):
            ok, detail = _check_api_key(cfg)
            assert ok is True
            assert "Found" in detail

    def test_key_missing_anthropic(self):
        """Missing Anthropic key should report fail with helpful message."""
        from claws.config import ProviderConfig
        cfg = ProviderConfig(name="default", type="anthropic", model="claude-sonnet-4-5-20250929")
        with patch.dict(os.environ, {}, clear=True):
            # Remove ANTHROPIC_API_KEY if present
            env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            with patch.dict(os.environ, env, clear=True):
                ok, detail = _check_api_key(cfg)
                assert ok is False
                assert "ANTHROPIC_API_KEY" in detail
                assert "console.anthropic.com" in detail

    def test_key_missing_openai(self):
        """Missing OpenAI key should report fail with correct env var."""
        from claws.config import ProviderConfig
        cfg = ProviderConfig(
            name="default", type="openai-compatible", model="gpt-4o",
            base_url="https://api.openai.com/v1",
        )
        with patch.dict(os.environ, {}, clear=True):
            env = {k: v for k, v in os.environ.items()
                   if k not in ("OPENAI_API_KEY", "OPENROUTER_API_KEY")}
            with patch.dict(os.environ, env, clear=True):
                ok, detail = _check_api_key(cfg)
                assert ok is False
                assert "OPENAI_API_KEY" in detail

    def test_key_missing_openrouter(self):
        """Missing OpenRouter key should report fail with correct env var."""
        from claws.config import ProviderConfig
        cfg = ProviderConfig(
            name="default", type="openai-compatible", model="anthropic/claude-3-haiku",
            base_url="https://openrouter.ai/api/v1",
        )
        with patch.dict(os.environ, {}, clear=True):
            env = {k: v for k, v in os.environ.items()
                   if k not in ("OPENAI_API_KEY", "OPENROUTER_API_KEY")}
            with patch.dict(os.environ, env, clear=True):
                ok, detail = _check_api_key(cfg)
                assert ok is False
                assert "OPENROUTER_API_KEY" in detail

    def test_local_provider_no_key_needed(self):
        """Local provider (localhost) should pass without key."""
        from claws.config import ProviderConfig
        cfg = ProviderConfig(
            name="default", type="openai-compatible", model="llama3",
            base_url="http://localhost:11434/v1",
        )
        ok, detail = _check_api_key(cfg)
        assert ok is True
        assert "Local provider" in detail

    def test_key_via_custom_env(self):
        """Custom api_key_env should be checked."""
        from claws.config import ProviderConfig
        cfg = ProviderConfig(
            name="default", type="openai-compatible", model="test",
            api_key_env="MY_CUSTOM_KEY",
        )
        with patch.dict(os.environ, {"MY_CUSTOM_KEY": "test-key-123"}):
            ok, detail = _check_api_key(cfg)
            assert ok is True


class TestCheckConnectivity:
    """Test _check_connectivity function."""

    def test_connectivity_pass(self):
        """Successful provider call should report pass."""
        from claws.config import ProviderConfig
        from claws.providers.base import Response

        mock_provider = MagicMock()
        mock_response = Response(content="Hello", model="test", tokens_in=5, tokens_out=1)

        async def mock_complete(messages, **kwargs):
            return mock_response

        mock_provider.complete = mock_complete

        cfg = ProviderConfig(name="default", type="anthropic", model="test")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("claws.commands.doctor._get_provider", return_value=mock_provider):
                ok, detail = _check_connectivity(cfg)
                assert ok is True
                assert "tokens" in detail

    def test_connectivity_fail_exception(self):
        """Provider error should report fail."""
        from claws.config import ProviderConfig

        mock_provider = MagicMock()

        async def mock_complete(messages, **kwargs):
            raise ConnectionError("Connection refused")

        mock_provider.complete = mock_complete

        cfg = ProviderConfig(name="default", type="anthropic", model="test")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("claws.commands.doctor._get_provider", return_value=mock_provider):
                ok, detail = _check_connectivity(cfg)
                assert ok is False
                assert "Connection" in detail

    def test_connectivity_empty_response(self):
        """Empty response should report fail."""
        from claws.config import ProviderConfig
        from claws.providers.base import Response

        mock_provider = MagicMock()
        mock_response = Response(content="", model="test", tokens_in=5, tokens_out=0)

        async def mock_complete(messages, **kwargs):
            return mock_response

        mock_provider.complete = mock_complete

        cfg = ProviderConfig(name="default", type="anthropic", model="test")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("claws.commands.doctor._get_provider", return_value=mock_provider):
                ok, detail = _check_connectivity(cfg)
                assert ok is False
                assert "Empty response" in detail

    def test_connectivity_provider_init_fail(self):
        """Provider init failure should report fail."""
        from claws.config import ProviderConfig

        cfg = ProviderConfig(name="default", type="anthropic", model="test")
        with patch("claws.commands.doctor._get_provider", side_effect=ValueError("No API key")):
            ok, detail = _check_connectivity(cfg)
            assert ok is False
            assert "Provider init failed" in detail


class TestGetExpectedEnvVar:
    """Test _get_expected_env_var helper."""

    def test_anthropic(self):
        from claws.config import ProviderConfig
        cfg = ProviderConfig(name="default", type="anthropic", model="test")
        assert _get_expected_env_var(cfg) == "ANTHROPIC_API_KEY"

    def test_openai_compatible_openai(self):
        from claws.config import ProviderConfig
        cfg = ProviderConfig(name="default", type="openai-compatible", model="test",
                             base_url="https://api.openai.com/v1")
        assert _get_expected_env_var(cfg) == "OPENAI_API_KEY"

    def test_openai_compatible_openrouter(self):
        from claws.config import ProviderConfig
        cfg = ProviderConfig(name="default", type="openai-compatible", model="test",
                             base_url="https://openrouter.ai/api/v1")
        assert _get_expected_env_var(cfg) == "OPENROUTER_API_KEY"

    def test_custom_env_var(self):
        from claws.config import ProviderConfig
        cfg = ProviderConfig(name="default", type="anthropic", model="test",
                             api_key_env="MY_KEY")
        assert _get_expected_env_var(cfg) == "MY_KEY"

    def test_unknown_openai_compat(self):
        from claws.config import ProviderConfig
        cfg = ProviderConfig(name="default", type="openai-compatible", model="test",
                             base_url="https://some-provider.com/v1")
        assert _get_expected_env_var(cfg) is None


class TestGetHelpUrl:
    """Test _get_help_url helper."""

    def test_anthropic(self):
        from claws.config import ProviderConfig
        cfg = ProviderConfig(name="default", type="anthropic", model="test")
        assert "console.anthropic.com" in _get_help_url(cfg)

    def test_openai(self):
        from claws.config import ProviderConfig
        cfg = ProviderConfig(name="default", type="openai-compatible", model="test",
                             base_url="https://api.openai.com/v1")
        assert "platform.openai.com" in _get_help_url(cfg)

    def test_openrouter(self):
        from claws.config import ProviderConfig
        cfg = ProviderConfig(name="default", type="openai-compatible", model="test",
                             base_url="https://openrouter.ai/api/v1")
        assert "openrouter.ai" in _get_help_url(cfg)

    def test_unknown(self):
        from claws.config import ProviderConfig
        cfg = ProviderConfig(name="default", type="openai-compatible", model="test",
                             base_url="https://some-provider.com/v1")
        assert _get_help_url(cfg) is None


# --- CLI integration tests ---


class TestDoctorCLINoProject:
    """Test doctor command with no project."""

    def test_no_project_fails(self, tmp_path):
        """Doctor should fail when no claws.yaml exists."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(doctor)
            assert result.exit_code != 0
            assert "Fail" in result.output
            assert "Skipped" in result.output

    def test_no_project_shows_init_hint(self, tmp_path):
        """Doctor should suggest claws init when no project."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(doctor)
            assert "claws init" in result.output


class TestDoctorCLINoProvider:
    """Test doctor command with project but no provider."""

    def test_no_provider_fails(self, tmp_path):
        """Doctor should fail when no provider is configured."""
        _make_config(tmp_path, include_provider=False)
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            (td_path / CONFIG_FILENAME).write_text(
                (tmp_path / CONFIG_FILENAME).read_text()
            )
            (td_path / ".claws").mkdir(exist_ok=True)
            result = runner.invoke(doctor)
            assert result.exit_code != 0
            assert "Fail" in result.output


class TestDoctorCLIProviderConfigured:
    """Test doctor command with provider configured."""

    def test_provider_passes(self, tmp_path):
        """Doctor should pass provider check when configured."""
        _make_config(tmp_path)
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            (td_path / CONFIG_FILENAME).write_text(
                (tmp_path / CONFIG_FILENAME).read_text()
            )
            (td_path / ".claws").mkdir(exist_ok=True)
            # Will fail at API key check since no env var set
            with patch.dict(os.environ, {}, clear=True):
                env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
                with patch.dict(os.environ, env, clear=True):
                    result = runner.invoke(doctor)
                    # Provider should show pass even if key fails
                    assert "Pass" in result.output
                    assert "anthropic" in result.output


class TestDoctorCLIApiKey:
    """Test doctor command API key checks."""

    def test_api_key_available(self, tmp_path):
        """Doctor should pass API key check when env var is set."""
        _make_config(tmp_path)
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            (td_path / CONFIG_FILENAME).write_text(
                (tmp_path / CONFIG_FILENAME).read_text()
            )
            (td_path / ".claws").mkdir(exist_ok=True)

            mock_provider = MagicMock()
            from claws.providers.base import Response
            mock_response = Response(content="Hello", model="test", tokens_in=5, tokens_out=1)

            async def mock_complete(messages, **kwargs):
                return mock_response

            mock_provider.complete = mock_complete

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}):
                with patch("claws.commands.doctor._get_provider", return_value=mock_provider):
                    result = runner.invoke(doctor)
                    # All checks should pass
                    assert result.exit_code == 0

    def test_api_key_missing_shows_help(self, tmp_path):
        """Doctor should show helpful message when key is missing."""
        _make_config(tmp_path)
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            (td_path / CONFIG_FILENAME).write_text(
                (tmp_path / CONFIG_FILENAME).read_text()
            )
            (td_path / ".claws").mkdir(exist_ok=True)
            with patch.dict(os.environ, {}, clear=True):
                env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
                with patch.dict(os.environ, env, clear=True):
                    result = runner.invoke(doctor)
                    assert result.exit_code != 0
                    assert "ANTHROPIC_API_KEY" in result.output


class TestDoctorCLIConnectivity:
    """Test doctor command connectivity checks."""

    def test_connectivity_pass(self, tmp_path):
        """Doctor should pass connectivity when provider responds."""
        _make_config(tmp_path)
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            (td_path / CONFIG_FILENAME).write_text(
                (tmp_path / CONFIG_FILENAME).read_text()
            )
            (td_path / ".claws").mkdir(exist_ok=True)

            mock_provider = MagicMock()
            from claws.providers.base import Response
            mock_response = Response(content="Hello", model="test", tokens_in=5, tokens_out=1)

            async def mock_complete(messages, **kwargs):
                return mock_response

            mock_provider.complete = mock_complete

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}):
                with patch("claws.commands.doctor._get_provider", return_value=mock_provider):
                    result = runner.invoke(doctor)
                    assert result.exit_code == 0
                    assert "Pass" in result.output

    def test_connectivity_fail(self, tmp_path):
        """Doctor should fail connectivity when provider errors."""
        _make_config(tmp_path)
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            (td_path / CONFIG_FILENAME).write_text(
                (tmp_path / CONFIG_FILENAME).read_text()
            )
            (td_path / ".claws").mkdir(exist_ok=True)

            mock_provider = MagicMock()

            async def mock_complete(messages, **kwargs):
                raise ConnectionError("Connection refused")

            mock_provider.complete = mock_complete

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}):
                with patch("claws.commands.doctor._get_provider", return_value=mock_provider):
                    result = runner.invoke(doctor)
                    assert result.exit_code != 0
                    assert "Fail" in result.output


class TestDoctorSkipsBehavior:
    """Test that downstream checks are skipped when upstream fails."""

    def test_skips_all_when_no_project(self, tmp_path):
        """All downstream checks should be skipped when project check fails."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(doctor)
            # Should see "Skipped" for provider, api key, and connectivity
            assert result.output.count("Skipped") == 3

    def test_skips_key_and_conn_when_no_provider(self, tmp_path):
        """API key and connectivity should be skipped when no provider."""
        _make_config(tmp_path, include_provider=False)
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            (td_path / CONFIG_FILENAME).write_text(
                (tmp_path / CONFIG_FILENAME).read_text()
            )
            (td_path / ".claws").mkdir(exist_ok=True)
            result = runner.invoke(doctor)
            # Provider fails, then API key and connectivity skipped
            assert result.output.count("Skipped") == 2

    def test_skips_conn_when_no_key(self, tmp_path):
        """Connectivity should be skipped when API key is missing."""
        _make_config(tmp_path)
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            (td_path / CONFIG_FILENAME).write_text(
                (tmp_path / CONFIG_FILENAME).read_text()
            )
            (td_path / ".claws").mkdir(exist_ok=True)
            with patch.dict(os.environ, {}, clear=True):
                env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
                with patch.dict(os.environ, env, clear=True):
                    result = runner.invoke(doctor)
                    # API key fails, connectivity skipped
                    assert "Skipped" in result.output
                    assert "needs API key" in result.output


class TestDoctorOutputFormat:
    """Test that output includes expected indicators."""

    def test_pass_indicator(self, tmp_path):
        """Output should include pass indicator for passing checks."""
        _make_config(tmp_path)
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            td_path = Path(td)
            (td_path / CONFIG_FILENAME).write_text(
                (tmp_path / CONFIG_FILENAME).read_text()
            )
            (td_path / ".claws").mkdir(exist_ok=True)

            mock_provider = MagicMock()
            from claws.providers.base import Response
            mock_response = Response(content="Hello", model="test", tokens_in=5, tokens_out=1)

            async def mock_complete(messages, **kwargs):
                return mock_response

            mock_provider.complete = mock_complete

            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test-key"}):
                with patch("claws.commands.doctor._get_provider", return_value=mock_provider):
                    result = runner.invoke(doctor)
                    assert "Pass" in result.output

    def test_fail_indicator(self, tmp_path):
        """Output should include fail indicator for failing checks."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(doctor)
            assert "Fail" in result.output

    def test_setup_check_header(self, tmp_path):
        """Output should include Setup Check header."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(doctor)
            assert "Setup Check" in result.output

    def test_status_header(self, tmp_path):
        """Output should include Status header."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(doctor)
            assert "Status" in result.output
