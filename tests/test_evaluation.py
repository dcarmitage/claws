"""Tests for the shared evaluation module (claws.evaluation)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from claws.evaluation import (
    _extract_json,
    _determine_tier,
    _parse_output_file,
    _tier_color,
    _run_judge,
    evaluate_response,
    DEFAULT_JUDGES,
)


# --- _extract_json ---


class TestExtractJson:
    def test_valid_json(self):
        text = '{"judge": "logic", "overall": 8.5}'
        result = _extract_json(text)
        assert result["judge"] == "logic"
        assert result["overall"] == 8.5

    def test_json_in_markdown_fence(self):
        text = '```json\n{"judge": "logic", "overall": 8.5}\n```'
        result = _extract_json(text)
        assert result["judge"] == "logic"
        assert result["overall"] == 8.5

    def test_json_with_preamble(self):
        text = (
            "Here is my evaluation of the response:\n\n"
            '{"judge": "logic", "overall": 7.0}\n\n'
            "That concludes my review."
        )
        result = _extract_json(text)
        assert result["judge"] == "logic"
        assert result["overall"] == 7.0

    def test_no_json(self):
        with pytest.raises(ValueError, match="No valid JSON"):
            _extract_json("No JSON here at all, just plain text.")

    def test_nested_json(self):
        text = json.dumps({
            "judge": "logic",
            "scores": {
                "reasoning": 8.0,
                "accuracy": 9.0,
            },
            "overall": 8.5,
        })
        result = _extract_json(text)
        assert result["judge"] == "logic"
        assert result["scores"]["reasoning"] == 8.0
        assert result["scores"]["accuracy"] == 9.0
        assert result["overall"] == 8.5


# --- _determine_tier ---


class TestDetermineTier:
    def test_boundary_excellent(self):
        assert _determine_tier(9.0) == "excellent"

    def test_boundary_good(self):
        assert _determine_tier(7.0) == "good"

    def test_boundary_acceptable(self):
        assert _determine_tier(5.0) == "acceptable"

    def test_boundary_poor(self):
        assert _determine_tier(4.9) == "poor"

    def test_above_excellent(self):
        assert _determine_tier(10.0) == "excellent"

    def test_zero(self):
        assert _determine_tier(0.0) == "poor"


# --- _parse_output_file ---


class TestParseOutputFile:
    def test_standard_format(self):
        content = "# Task\n\nDo something useful\n\n# Response\n\nHere is the result."
        task, response = _parse_output_file(content)
        assert task == "Do something useful"
        assert response == "Here is the result."

    def test_no_response_marker(self):
        content = "Just some text without any markers at all."
        task, response = _parse_output_file(content)
        assert task == ""
        assert response == content

    def test_empty_content(self):
        content = ""
        task, response = _parse_output_file(content)
        assert task == ""
        assert response == ""

    def test_response_marker_only(self):
        content = "# Response\n\nOnly a response, no task header."
        task, response = _parse_output_file(content)
        assert task == ""
        assert response == "Only a response, no task header."

    def test_multiline(self):
        content = "# Task\n\nLine 1\nLine 2\n\n# Response\n\nResult 1\nResult 2"
        task, response = _parse_output_file(content)
        assert "Line 1" in task
        assert "Line 2" in task
        assert "Result 1" in response
        assert "Result 2" in response


# --- _tier_color ---


class TestTierColor:
    def test_known_tiers(self):
        assert _tier_color("excellent") == "green"
        assert _tier_color("good") == "blue"
        assert _tier_color("acceptable") == "yellow"
        assert _tier_color("poor") == "red"

    def test_unknown_tier(self):
        assert _tier_color("unknown") == "white"


# --- _run_judge (async) ---


class TestRunJudge:
    @pytest.mark.asyncio
    async def test_successful_judge(self, tmp_path, monkeypatch):
        """Test _run_judge returns parsed JSON on success."""
        judge_response = json.dumps({
            "judge": "logic",
            "scores": {"reasoning": 8.0},
            "overall": 8.0,
            "tier": "good",
            "rationale": "Solid reasoning.",
        })

        mock_result = MagicMock()
        mock_result.content = judge_response

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_result)

        # Monkeypatch _load_prompt so we don't need real template files
        monkeypatch.setattr(
            "claws.evaluation._load_prompt",
            lambda name: "Evaluate: {task}\n\n{response}",
        )

        result = await _run_judge(mock_provider, "logic", "Do something", "I did it")
        assert result is not None
        assert result["judge"] == "logic"
        assert result["overall"] == 8.0

    @pytest.mark.asyncio
    async def test_judge_returns_garbage(self, monkeypatch):
        """Test _run_judge returns None when LLM returns non-JSON."""
        mock_result = MagicMock()
        mock_result.content = "I cannot provide a structured evaluation."

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_result)

        monkeypatch.setattr(
            "claws.evaluation._load_prompt",
            lambda name: "Evaluate: {task}\n\n{response}",
        )

        result = await _run_judge(mock_provider, "logic", "Do something", "I did it")
        assert result is None

    @pytest.mark.asyncio
    async def test_judge_provider_error(self, monkeypatch):
        """Test _run_judge returns None when provider raises."""
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=RuntimeError("API down"))

        monkeypatch.setattr(
            "claws.evaluation._load_prompt",
            lambda name: "Evaluate: {task}\n\n{response}",
        )

        result = await _run_judge(mock_provider, "logic", "Do something", "I did it")
        assert result is None


# --- evaluate_response (async, high-level) ---


def _make_judge_response(judge: str, overall: float = 8.5) -> str:
    """Create a mock judge JSON response string."""
    scores = {
        "dim_a": overall,
        "dim_b": overall,
    }
    tier = (
        "excellent" if overall >= 9.0
        else "good" if overall >= 7.0
        else "acceptable" if overall >= 5.0
        else "poor"
    )
    return json.dumps({
        "judge": judge,
        "scores": scores,
        "overall": overall,
        "tier": tier,
        "rationale": f"Test rationale for {judge}.",
    })


class TestEvaluateResponse:
    @pytest.mark.asyncio
    async def test_default_judges(self, monkeypatch):
        """Test that default judges are logic and consistency."""
        call_log = []

        logic_result = MagicMock()
        logic_result.content = _make_judge_response("logic", 8.5)
        consistency_result = MagicMock()
        consistency_result.content = _make_judge_response("consistency", 9.0)

        responses = iter([logic_result, consistency_result])

        async def mock_complete(messages, **kwargs):
            resp = next(responses)
            return resp

        mock_provider = MagicMock()
        mock_provider.complete = mock_complete

        monkeypatch.setattr(
            "claws.evaluation._load_prompt",
            lambda name: (call_log.append(name) or "") + "Evaluate: {task}\n\n{response}",
        )

        results = await evaluate_response(mock_provider, "Do task", "Here is result")

        assert set(results.keys()) == {"logic", "consistency"}
        assert call_log == ["logic", "consistency"]
        assert results["logic"]["overall"] == 8.5
        assert results["consistency"]["overall"] == 9.0

    @pytest.mark.asyncio
    async def test_custom_judges(self, monkeypatch):
        """Test passing custom judge list."""
        custom_result = MagicMock()
        custom_result.content = _make_judge_response("custom", 7.5)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=custom_result)

        monkeypatch.setattr(
            "claws.evaluation._load_prompt",
            lambda name: "Evaluate: {task}\n\n{response}",
        )

        results = await evaluate_response(
            mock_provider, "Do task", "Here is result", judges=["custom"]
        )

        assert list(results.keys()) == ["custom"]
        assert results["custom"]["overall"] == 7.5

    @pytest.mark.asyncio
    async def test_partial_failure(self, monkeypatch):
        """Test that one judge failing doesn't stop the other."""
        good_result = MagicMock()
        good_result.content = _make_judge_response("consistency", 8.0)

        bad_result = MagicMock()
        bad_result.content = "Not valid JSON at all."

        call_count = 0

        async def mock_complete(messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return bad_result
            return good_result

        mock_provider = MagicMock()
        mock_provider.complete = mock_complete

        monkeypatch.setattr(
            "claws.evaluation._load_prompt",
            lambda name: "Evaluate: {task}\n\n{response}",
        )

        results = await evaluate_response(mock_provider, "Do task", "Here is result")

        assert results["logic"] is None
        assert results["consistency"] is not None
        assert results["consistency"]["overall"] == 8.0

    @pytest.mark.asyncio
    async def test_result_structure(self, monkeypatch):
        """Verify result dict has expected keys."""
        judge_result = MagicMock()
        judge_result.content = _make_judge_response("logic", 9.0)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=judge_result)

        monkeypatch.setattr(
            "claws.evaluation._load_prompt",
            lambda name: "Evaluate: {task}\n\n{response}",
        )

        results = await evaluate_response(
            mock_provider, "Do task", "Result", judges=["logic"]
        )

        logic = results["logic"]
        assert logic is not None
        assert "scores" in logic
        assert "overall" in logic
        assert "tier" in logic
        assert "rationale" in logic

    @pytest.mark.asyncio
    async def test_does_not_mutate_default_judges(self, monkeypatch):
        """Ensure calling with None judges doesn't mutate DEFAULT_JUDGES."""
        original = list(DEFAULT_JUDGES)

        mock_result = MagicMock()
        mock_result.content = _make_judge_response("logic", 8.0)

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=mock_result)

        monkeypatch.setattr(
            "claws.evaluation._load_prompt",
            lambda name: "Evaluate: {task}\n\n{response}",
        )

        await evaluate_response(mock_provider, "task", "response")
        assert DEFAULT_JUDGES == original
