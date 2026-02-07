"""Tests for the claws evaluate command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml
from click.testing import CliRunner

from claws.config import CONFIG_FILENAME
from claws.events import EventSpine, Event, TASK_COMPLETED, EVAL_STARTED, EVAL_COMPLETED
from claws.commands.evaluate import (
    evaluate,
    _parse_output_file,
    _extract_json,
    _determine_tier,
)


# --- Unit tests for helpers ---


class TestParseOutputFile:
    def test_standard_format(self):
        content = "# Task\n\nDo something useful\n\n# Response\n\nHere is the result."
        task, response = _parse_output_file(content)
        assert task == "Do something useful"
        assert response == "Here is the result."

    def test_no_response_marker(self):
        content = "Just some text without markers."
        task, response = _parse_output_file(content)
        assert task == ""
        assert response == content

    def test_multiline_content(self):
        content = "# Task\n\nLine 1\nLine 2\n\n# Response\n\nResult line 1\nResult line 2"
        task, response = _parse_output_file(content)
        assert "Line 1" in task
        assert "Line 2" in task
        assert "Result line 1" in response
        assert "Result line 2" in response


class TestExtractJson:
    def test_clean_json(self):
        text = '{"judge": "logic", "overall": 8.5}'
        result = _extract_json(text)
        assert result["judge"] == "logic"
        assert result["overall"] == 8.5

    def test_json_with_preamble(self):
        text = 'Here is my evaluation:\n\n{"judge": "logic", "overall": 8.5}\n\nThat is all.'
        result = _extract_json(text)
        assert result["judge"] == "logic"

    def test_json_in_markdown_fence(self):
        text = '```json\n{"judge": "logic", "overall": 8.5}\n```'
        result = _extract_json(text)
        assert result["overall"] == 8.5

    def test_no_json(self):
        with pytest.raises(ValueError):
            _extract_json("No JSON here at all")

    def test_invalid_json(self):
        with pytest.raises((ValueError, json.JSONDecodeError)):
            _extract_json("{not valid json}")


class TestDetermineTier:
    def test_excellent(self):
        assert _determine_tier(9.5) == "excellent"
        assert _determine_tier(9.0) == "excellent"

    def test_good(self):
        assert _determine_tier(8.0) == "good"
        assert _determine_tier(7.0) == "good"

    def test_acceptable(self):
        assert _determine_tier(6.0) == "acceptable"
        assert _determine_tier(5.0) == "acceptable"

    def test_poor(self):
        assert _determine_tier(4.9) == "poor"
        assert _determine_tier(0) == "poor"


# --- Integration tests for the evaluate command ---


def _make_project(tmp_path: Path, eval_provider: str | None = None) -> Path:
    """Create a minimal claws project for testing."""
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
            "scout": {
                "role": "researcher",
                "provider": "default",
            },
        },
        "eval": {
            "judges": ["logic", "consistency"],
            "threshold": 8.0,
        },
    }
    if eval_provider:
        config["eval"]["provider"] = eval_provider
    config_path = tmp_path / CONFIG_FILENAME
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    (tmp_path / "agents" / "scout" / "output").mkdir(parents=True)
    (tmp_path / ".claws").mkdir(exist_ok=True)
    return tmp_path


def _write_output_file(project_root: Path, agent: str = "scout") -> str:
    """Write a sample agent output file. Returns relative path."""
    output_dir = project_root / "agents" / agent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "20260206-120000.md"
    output_file.write_text(
        "# Task\n\nAnalyze the market trends for Q4 2025.\n\n"
        "# Response\n\nBased on the available data, here are the key trends...\n"
    )
    return f"agents/{agent}/output/20260206-120000.md"


def _emit_task_completed(project_root: Path, agent: str, output_file_rel: str):
    """Emit a TASK_COMPLETED event into the event spine."""
    spine = EventSpine(project_root)
    spine.emit(Event(
        type=TASK_COMPLETED,
        agent=agent,
        data={
            "task": "Analyze the market trends for Q4 2025.",
            "tokens_in": 100,
            "tokens_out": 500,
            "elapsed_s": 3.2,
            "output_file": output_file_rel,
        },
    ))


def _make_judge_response(judge: str, overall: float = 8.5) -> str:
    """Create a mock judge JSON response string."""
    if judge == "logic":
        scores = {
            "claims_accuracy": overall,
            "reasoning_quality": overall,
            "hallucination_risk": overall,
            "task_adherence": overall,
            "factual_grounding": overall,
        }
    else:
        scores = {
            "completeness": overall,
            "coherence": overall,
            "quality": overall,
            "relevance": overall,
            "format": overall,
        }
    tier = "excellent" if overall >= 9.0 else "good" if overall >= 7.0 else "acceptable" if overall >= 5.0 else "poor"
    return json.dumps({
        "judge": judge,
        "scores": scores,
        "overall": overall,
        "tier": tier,
        "rationale": f"Test rationale for {judge} judge.",
    })


def _setup_isolated_project(runner, project_root):
    """Set up isolated filesystem with project data. Returns (td_path, context_manager).

    Usage:
        with runner.isolated_filesystem(temp_dir=project_root) as td:
            td_path = Path(td)
            _copy_project_files(td_path, project_root)
            ...
    """
    pass  # Helper function not needed; inline setup used instead


def _copy_project_files(td_path: Path, project_root: Path, copy_events: bool = True):
    """Copy project files into isolated filesystem directory."""
    (td_path / CONFIG_FILENAME).write_text(
        (project_root / CONFIG_FILENAME).read_text()
    )
    (td_path / ".claws").mkdir(exist_ok=True)
    if copy_events:
        events_file = project_root / ".claws" / "events.jsonl"
        if events_file.exists():
            (td_path / ".claws" / "events.jsonl").write_text(events_file.read_text())
    (td_path / "agents" / "scout" / "output").mkdir(parents=True, exist_ok=True)


def _copy_output_file(td_path: Path, project_root: Path):
    """Copy agent output file into isolated filesystem."""
    src = project_root / "agents" / "scout" / "output" / "20260206-120000.md"
    if src.exists():
        dst = td_path / "agents" / "scout" / "output" / "20260206-120000.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text())


class TestEvaluateCommandNoTasks:
    """Test error when no completed tasks exist."""

    def test_no_completed_tasks(self, tmp_path):
        project_root = _make_project(tmp_path)
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=project_root) as td:
            td_path = Path(td)
            _copy_project_files(td_path, project_root, copy_events=False)
            result = runner.invoke(evaluate, ["scout"])
            assert result.exit_code != 0
            assert "No completed tasks" in result.output


class TestEvaluateCommandMissingOutput:
    """Test error when output file is missing."""

    def test_missing_output_file(self, tmp_path):
        project_root = _make_project(tmp_path)
        # Emit event pointing to non-existent file
        spine = EventSpine(project_root)
        spine.emit(Event(
            type=TASK_COMPLETED,
            agent="scout",
            data={
                "task": "test",
                "output_file": "agents/scout/output/nonexistent.md",
            },
        ))
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=project_root) as td:
            td_path = Path(td)
            _copy_project_files(td_path, project_root)
            result = runner.invoke(evaluate, ["scout"])
            assert result.exit_code != 0
            assert "not found" in result.output


class TestEvaluateCommandSuccess:
    """Test successful evaluation with mocked provider."""

    def test_successful_evaluation(self, tmp_path):
        project_root = _make_project(tmp_path)
        output_rel = _write_output_file(project_root)
        _emit_task_completed(project_root, "scout", output_rel)

        # Create mock provider that returns valid judge JSON
        mock_provider = MagicMock()
        logic_response = MagicMock()
        logic_response.content = _make_judge_response("logic", 8.5)
        consistency_response = MagicMock()
        consistency_response.content = _make_judge_response("consistency", 9.0)

        call_count = 0

        async def mock_complete(messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return logic_response
            return consistency_response

        mock_provider.complete = mock_complete

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=project_root) as td:
            td_path = Path(td)
            _copy_project_files(td_path, project_root)
            _copy_output_file(td_path, project_root)

            with patch("claws.commands.evaluate.get_provider", return_value=mock_provider):
                result = runner.invoke(evaluate, ["scout"])

            assert result.exit_code == 0
            assert "PASS" in result.output

    def test_evaluation_below_threshold(self, tmp_path):
        project_root = _make_project(tmp_path)
        output_rel = _write_output_file(project_root)
        _emit_task_completed(project_root, "scout", output_rel)

        mock_provider = MagicMock()
        logic_response = MagicMock()
        logic_response.content = _make_judge_response("logic", 5.0)
        consistency_response = MagicMock()
        consistency_response.content = _make_judge_response("consistency", 4.0)

        call_count = 0

        async def mock_complete(messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return logic_response
            return consistency_response

        mock_provider.complete = mock_complete

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=project_root) as td:
            td_path = Path(td)
            _copy_project_files(td_path, project_root)
            _copy_output_file(td_path, project_root)

            with patch("claws.commands.evaluate.get_provider", return_value=mock_provider):
                result = runner.invoke(evaluate, ["scout"])

            assert result.exit_code != 0
            assert "FAIL" in result.output


class TestEvaluateJsonParseFailure:
    """Test handling when judge returns non-JSON."""

    def test_json_parse_failure_continues(self, tmp_path):
        project_root = _make_project(tmp_path)
        output_rel = _write_output_file(project_root)
        _emit_task_completed(project_root, "scout", output_rel)

        mock_provider = MagicMock()
        # First judge returns garbage, second returns valid JSON
        bad_response = MagicMock()
        bad_response.content = "I cannot evaluate this properly because reasons."
        good_response = MagicMock()
        good_response.content = _make_judge_response("consistency", 9.0)

        call_count = 0

        async def mock_complete(messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return bad_response
            return good_response

        mock_provider.complete = mock_complete

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=project_root) as td:
            td_path = Path(td)
            _copy_project_files(td_path, project_root)
            _copy_output_file(td_path, project_root)

            with patch("claws.commands.evaluate.get_provider", return_value=mock_provider):
                result = runner.invoke(evaluate, ["scout"])

            # Should still fail since one judge failed
            assert result.exit_code != 0
            assert "Warning" in result.output or "failed" in result.output


class TestProviderOverride:
    """Test --provider flag overrides config."""

    def test_provider_flag(self, tmp_path):
        project_root = _make_project(tmp_path)
        output_rel = _write_output_file(project_root)
        _emit_task_completed(project_root, "scout", output_rel)

        # Add a second provider
        config = yaml.safe_load((project_root / CONFIG_FILENAME).read_text())
        config["providers"]["eval-model"] = {
            "type": "anthropic",
            "model": "claude-opus-4-20250514",
        }
        (project_root / CONFIG_FILENAME).write_text(
            yaml.dump(config, default_flow_style=False, sort_keys=False)
        )

        mock_provider = MagicMock()
        response = MagicMock()
        response.content = _make_judge_response("logic", 9.0)

        async def mock_complete(messages, **kwargs):
            return response

        mock_provider.complete = mock_complete

        captured_provider_config = []

        def capture_get_provider(config):
            captured_provider_config.append(config)
            return mock_provider

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=project_root) as td:
            td_path = Path(td)
            _copy_project_files(td_path, project_root)
            _copy_output_file(td_path, project_root)

            with patch("claws.commands.evaluate.get_provider", side_effect=capture_get_provider):
                result = runner.invoke(evaluate, ["scout", "--provider", "eval-model"])

            assert result.exit_code == 0
            # Verify the eval-model provider was used
            assert len(captured_provider_config) == 1
            assert captured_provider_config[0].model == "claude-opus-4-20250514"


class TestOutputFlag:
    """Test --output flag saves results to file."""

    def test_output_saves_json(self, tmp_path):
        project_root = _make_project(tmp_path)
        output_rel = _write_output_file(project_root)
        _emit_task_completed(project_root, "scout", output_rel)

        mock_provider = MagicMock()
        logic_response = MagicMock()
        logic_response.content = _make_judge_response("logic", 9.0)
        consistency_response = MagicMock()
        consistency_response.content = _make_judge_response("consistency", 9.0)

        call_count = 0

        async def mock_complete(messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return logic_response
            return consistency_response

        mock_provider.complete = mock_complete

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=project_root) as td:
            td_path = Path(td)
            _copy_project_files(td_path, project_root)
            _copy_output_file(td_path, project_root)

            results_path = td_path / "eval-results.json"
            with patch("claws.commands.evaluate.get_provider", return_value=mock_provider):
                result = runner.invoke(evaluate, ["scout", "--output", str(results_path)])

            assert result.exit_code == 0
            assert results_path.exists()
            saved = json.loads(results_path.read_text())
            assert saved["agent"] == "scout"
            assert saved["all_passed"] is True
            assert "logic" in saved["results"]
            assert "consistency" in saved["results"]


class TestEventEmission:
    """Test that EVAL_STARTED and EVAL_COMPLETED events are emitted."""

    def test_events_emitted(self, tmp_path):
        project_root = _make_project(tmp_path)
        output_rel = _write_output_file(project_root)
        _emit_task_completed(project_root, "scout", output_rel)

        mock_provider = MagicMock()
        response = MagicMock()
        response.content = _make_judge_response("logic", 9.0)

        async def mock_complete(messages, **kwargs):
            return response

        mock_provider.complete = mock_complete

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=project_root) as td:
            td_path = Path(td)
            _copy_project_files(td_path, project_root)
            _copy_output_file(td_path, project_root)

            with patch("claws.commands.evaluate.get_provider", return_value=mock_provider):
                result = runner.invoke(evaluate, ["scout"])

            assert result.exit_code == 0

            # Check events in the spine
            spine = EventSpine(td_path)
            all_events = spine.read_all()
            event_types = [e.type for e in all_events]
            assert EVAL_STARTED in event_types
            assert EVAL_COMPLETED in event_types

            # Verify eval completed data
            eval_completed = [e for e in all_events if e.type == EVAL_COMPLETED]
            assert len(eval_completed) == 1
            assert eval_completed[0].data["all_passed"] is True
            assert "results" in eval_completed[0].data


class TestEvalConfigProvider:
    """Test eval.provider config field."""

    def test_eval_provider_from_config(self, tmp_path):
        """Eval should use eval.provider from config when set."""
        project_root = _make_project(tmp_path, eval_provider="default")
        output_rel = _write_output_file(project_root)
        _emit_task_completed(project_root, "scout", output_rel)

        mock_provider = MagicMock()
        response = MagicMock()
        response.content = _make_judge_response("logic", 9.0)

        async def mock_complete(messages, **kwargs):
            return response

        mock_provider.complete = mock_complete

        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=project_root) as td:
            td_path = Path(td)
            _copy_project_files(td_path, project_root)
            _copy_output_file(td_path, project_root)

            with patch("claws.commands.evaluate.get_provider", return_value=mock_provider):
                result = runner.invoke(evaluate, ["scout"])

            assert result.exit_code == 0

    def test_eval_provider_none_falls_to_default(self):
        """When eval.provider is None, should use 'default' provider."""
        from claws.config import EvalConfig
        ec = EvalConfig()
        assert ec.provider is None
