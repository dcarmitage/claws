"""Shared evaluation logic for running judge prompts against task/response pairs.

This module contains the reusable evaluation primitives extracted from the
evaluate CLI command. Both the CLI and the onboarding engine can use these
functions without depending on Click, Rich, or the event spine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from claws.providers import Message

# Path to judge prompt templates relative to this package
TEMPLATES_DIR = Path(__file__).parent / "templates" / "prompts"

DEFAULT_JUDGES = ["logic", "consistency"]


def _load_prompt(judge_name: str) -> str:
    """Load a judge prompt template from the templates directory."""
    prompt_path = TEMPLATES_DIR / f"{judge_name}_judge.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Judge prompt not found: {prompt_path}")
    return prompt_path.read_text()


def _parse_output_file(content: str) -> tuple[str, str]:
    """Parse an agent output file into (task, response).

    Output files have the format:
        # Task

        <task text>

        # Response

        <response text>
    """
    marker = "# Response"
    if marker not in content:
        # Fallback: treat entire content as response, no task
        return "", content

    parts = content.split(marker, 1)
    task_section = parts[0]
    response_section = parts[1]

    # Strip the "# Task" header from task section
    task = task_section.replace("# Task", "", 1).strip()
    response = response_section.strip()

    return task, response


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response text.

    LLMs often add preamble or markdown fences around JSON.
    Find the first { and last } to extract the JSON object.
    """
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace == -1 or last_brace == -1 or last_brace <= first_brace:
        raise ValueError("No valid JSON object found in response")
    json_str = text[first_brace:last_brace + 1]
    return json.loads(json_str)


def _determine_tier(score: float) -> str:
    """Determine quality tier from overall score."""
    if score >= 9.0:
        return "excellent"
    elif score >= 7.0:
        return "good"
    elif score >= 5.0:
        return "acceptable"
    else:
        return "poor"


def _tier_color(tier: str) -> str:
    """Return a Rich color for the quality tier."""
    return {
        "excellent": "green",
        "good": "blue",
        "acceptable": "yellow",
        "poor": "red",
    }.get(tier, "white")


async def _run_judge(
    provider,
    judge_name: str,
    task: str,
    response: str,
) -> dict[str, Any] | None:
    """Run a single judge evaluation and return parsed results.

    Returns the parsed JSON dict from the judge, or None if parsing fails
    or the provider raises an error.
    """
    prompt_template = _load_prompt(judge_name)
    prompt = prompt_template.replace("{task}", task).replace("{response}", response)

    messages = [
        Message(role="user", content=prompt),
    ]

    result = None
    try:
        result = await provider.complete(messages, max_tokens=8192)
        parsed = _extract_json(result.content)
        return parsed
    except (ValueError, json.JSONDecodeError):
        return None
    except Exception:
        return None


async def evaluate_response(
    provider,
    task: str,
    response: str,
    judges: list[str] | None = None,
) -> dict[str, dict | None]:
    """Run judges on a task/response pair and return results dict.

    This is the high-level evaluation entry point that encapsulates the
    judge-running loop without any CLI, event, or display logic.

    Args:
        provider: An LLM provider instance with an async complete() method.
        task: The task description that was given to the agent.
        response: The agent's response to evaluate.
        judges: List of judge names to run. Defaults to ["logic", "consistency"].

    Returns:
        Dict mapping judge_name to result dict (with keys: scores, overall,
        tier, rationale) or None if that judge failed.
    """
    if judges is None:
        judges = list(DEFAULT_JUDGES)

    results: dict[str, dict | None] = {}
    for judge_name in judges:
        try:
            result = await _run_judge(provider, judge_name, task, response)
            results[judge_name] = result
        except FileNotFoundError:
            results[judge_name] = None

    return results
