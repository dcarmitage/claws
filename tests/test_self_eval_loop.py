"""Tests for the closed self-eval loop.

Verifies that:
1. claws run --eval emits EVAL_STARTED and EVAL_COMPLETED events
2. Eval events feed into TrustProfile (trust system sees run --eval results)
3. Score improvement is tracked across retry attempts
4. --learn flag persists reflection insights to memory.md
5. The full loop: run → eval → reflect → retry → trust update
"""

import json
import yaml
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from click.testing import CliRunner

from claws.cli import main
from claws.events import EventSpine, EVAL_STARTED, EVAL_COMPLETED, TASK_STARTED, TASK_COMPLETED
from claws.providers.base import Response
from claws.trust import TrustProfile, AutonomyTier


def _make_project(td_path: Path, threshold=7.0):
    """Helper: create a project with one agent and eval config."""
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
                "machine": "local",
            },
        },
        "eval": {
            "judges": ["logic", "consistency"],
            "threshold": threshold,
        },
    }
    (td_path / "claws.yaml").write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False)
    )
    (td_path / "agents").mkdir(exist_ok=True)
    agent_dir = td_path / "agents" / "scout"
    agent_dir.mkdir(exist_ok=True)
    (agent_dir / "output").mkdir(exist_ok=True)
    (agent_dir / "identity.md").write_text("# scout\n\n## Role\nresearcher\n")
    (agent_dir / "memory.md").write_text("# Memory -- scout\n")
    (td_path / ".claws").mkdir(exist_ok=True)


def _mock_provider(response_text="Mock answer from agent."):
    """Return a mock provider that returns a fixed response."""
    mock_prov = MagicMock()
    mock_prov.complete = AsyncMock(
        return_value=Response(
            content=response_text,
            model="mock-model",
            tokens_in=10,
            tokens_out=20,
        )
    )

    async def mock_stream(messages, **kwargs):
        for chunk in [response_text]:
            yield chunk

    mock_prov.stream = MagicMock(side_effect=mock_stream)
    return mock_prov


def _good_eval():
    return {
        "logic": {
            "overall": 8.5,
            "tier": "good",
            "rationale": "Clear and accurate reasoning.",
            "scores": {"accuracy": 8.5, "reasoning": 8.5},
        },
        "consistency": {
            "overall": 8.5,
            "tier": "good",
            "rationale": "Complete and coherent response.",
            "scores": {"completeness": 8.5, "coherence": 8.5},
        },
    }


def _bad_eval():
    return {
        "logic": {
            "overall": 4.0,
            "tier": "poor",
            "rationale": "Contains factual errors and weak reasoning.",
            "scores": {"accuracy": 3.5, "reasoning": 4.5},
        },
        "consistency": {
            "overall": 4.0,
            "tier": "poor",
            "rationale": "Incomplete and contradictory.",
            "scores": {"completeness": 3.5, "coherence": 4.5},
        },
    }


def _read_events(td_path: Path) -> list[dict]:
    """Read all events from event log."""
    events_file = Path(td_path) / ".claws" / "events.jsonl"
    if not events_file.exists():
        return []
    lines = events_file.read_text().strip().split("\n")
    return [json.loads(l) for l in lines if l.strip()]


class TestEvalEventsEmitted:
    """Verify that run --eval emits EVAL_STARTED and EVAL_COMPLETED events."""

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_pass_emits_eval_events(self, mock_get_prov, mock_eval, tmp_path):
        mock_get_prov.return_value = _mock_provider()
        mock_eval.return_value = _good_eval()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            events = _read_events(td)
            types = [e["type"] for e in events]
            assert "eval.started" in types
            assert "eval.completed" in types

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_eval_started_has_correct_data(self, mock_get_prov, mock_eval, tmp_path):
        mock_get_prov.return_value = _mock_provider()
        mock_eval.return_value = _good_eval()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval"],
                catch_exceptions=False,
            )
            events = _read_events(td)
            eval_started = [e for e in events if e["type"] == "eval.started"][0]
            assert eval_started["agent"] == "scout"
            assert "judges" in eval_started["data"]
            assert eval_started["data"]["attempt"] == 1

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_eval_completed_has_score_and_results(self, mock_get_prov, mock_eval, tmp_path):
        mock_get_prov.return_value = _mock_provider()
        mock_eval.return_value = _good_eval()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval"],
                catch_exceptions=False,
            )
            events = _read_events(td)
            eval_completed = [e for e in events if e["type"] == "eval.completed"][0]
            assert eval_completed["agent"] == "scout"
            assert eval_completed["data"]["all_passed"] is True
            assert eval_completed["data"]["average_score"] == 8.5
            assert eval_completed["data"]["threshold"] == 7.0  # default from _make_project
            assert "logic" in eval_completed["data"]["results"]
            assert "consistency" in eval_completed["data"]["results"]

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_fail_also_emits_eval_completed(self, mock_get_prov, mock_eval, tmp_path):
        """Even failing evals should emit EVAL_COMPLETED for trust tracking."""
        mock_get_prov.return_value = _mock_provider()
        mock_eval.return_value = _bad_eval()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--retries", "0"],
            )
            assert result.exit_code != 0
            events = _read_events(td)
            eval_completed = [e for e in events if e["type"] == "eval.completed"]
            assert len(eval_completed) == 1
            assert eval_completed[0]["data"]["all_passed"] is False
            assert eval_completed[0]["data"]["average_score"] == 4.0


class TestEvalRetryEvents:
    """Verify eval events across retry attempts."""

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_retry_emits_multiple_eval_events(self, mock_get_prov, mock_eval, tmp_path):
        mock_get_prov.return_value = _mock_provider()
        mock_eval.side_effect = [_bad_eval(), _good_eval()]
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--retries", "2"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            events = _read_events(td)
            eval_started = [e for e in events if e["type"] == "eval.started"]
            eval_completed = [e for e in events if e["type"] == "eval.completed"]
            assert len(eval_started) == 2
            assert len(eval_completed) == 2
            assert eval_completed[0]["data"]["attempt"] == 1
            assert eval_completed[1]["data"]["attempt"] == 2

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_improvement_tracked_in_events(self, mock_get_prov, mock_eval, tmp_path):
        mock_get_prov.return_value = _mock_provider()
        mock_eval.side_effect = [_bad_eval(), _good_eval()]
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--retries", "2"],
                catch_exceptions=False,
            )
            events = _read_events(td)
            eval_completed = [e for e in events if e["type"] == "eval.completed"]
            # First attempt: no improvement data
            assert eval_completed[0]["data"]["improvement"] is None
            # Second attempt: improvement = 8.5 - 4.0 = 4.5
            assert eval_completed[1]["data"]["improvement"] == 4.5

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_retry_shows_improvement_message(self, mock_get_prov, mock_eval, tmp_path):
        mock_get_prov.return_value = _mock_provider()
        mock_eval.side_effect = [_bad_eval(), _good_eval()]
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--retries", "2"],
                catch_exceptions=False,
            )
            assert "Improved" in result.output
            assert "4.0" in result.output
            assert "8.5" in result.output


class TestTrustIntegration:
    """Verify that run --eval results feed into TrustProfile."""

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_trust_profile_sees_run_eval(self, mock_get_prov, mock_eval, tmp_path):
        """The critical test: TrustProfile.for_agent() should include run --eval results."""
        mock_get_prov.return_value = _mock_provider()
        mock_eval.return_value = _good_eval()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval"],
                catch_exceptions=False,
            )
            # Now build trust profile from the event log
            spine = EventSpine(Path(td))
            profile = TrustProfile.for_agent(spine, "scout")
            assert profile.eval_count == 1
            assert profile.average is not None
            assert profile.average == 8.5

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_multiple_runs_accumulate_trust(self, mock_get_prov, mock_eval, tmp_path):
        mock_get_prov.return_value = _mock_provider()
        mock_eval.return_value = _good_eval()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            # Run 3 tasks with eval
            for i in range(3):
                runner.invoke(
                    main,
                    ["run", "scout", f"task {i}", "--no-stream", "--eval"],
                    catch_exceptions=False,
                )
            spine = EventSpine(Path(td))
            profile = TrustProfile.for_agent(spine, "scout")
            assert profile.eval_count == 3
            assert profile.average == 8.5

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_retry_both_evals_in_trust(self, mock_get_prov, mock_eval, tmp_path):
        """Both the failed and successful eval should appear in trust."""
        mock_get_prov.return_value = _mock_provider()
        mock_eval.side_effect = [_bad_eval(), _good_eval()]
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--retries", "2"],
                catch_exceptions=False,
            )
            spine = EventSpine(Path(td))
            profile = TrustProfile.for_agent(spine, "scout")
            # Both evals recorded
            assert profile.eval_count == 2
            # Average of 4.0 and 8.5 = 6.25
            assert profile.average == pytest.approx(6.25, abs=0.01)

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_trust_tier_from_run_eval(self, mock_get_prov, mock_eval, tmp_path):
        """Verify autonomy tier is correct based on run --eval scores."""
        mock_get_prov.return_value = _mock_provider()
        mock_eval.return_value = _good_eval()  # 8.5 → STANDARD tier
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval"],
                catch_exceptions=False,
            )
            spine = EventSpine(Path(td))
            profile = TrustProfile.for_agent(spine, "scout")
            assert profile.tier == AutonomyTier.STANDARD


class TestLearnFlag:
    """Verify --learn persists reflection insights to memory.md."""

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_learn_updates_memory_on_retry(self, mock_get_prov, mock_eval, tmp_path):
        mock_get_prov.return_value = _mock_provider()
        mock_eval.side_effect = [_bad_eval(), _good_eval()]
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--learn", "--retries", "2"],
                catch_exceptions=False,
            )
            assert result.exit_code == 0
            memory = (Path(td) / "agents" / "scout" / "memory.md").read_text()
            assert "Reflection" in memory
            assert "Score trajectory" in memory
            assert "4.0" in memory
            assert "8.5" in memory

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_learn_not_written_without_flag(self, mock_get_prov, mock_eval, tmp_path):
        mock_get_prov.return_value = _mock_provider()
        mock_eval.side_effect = [_bad_eval(), _good_eval()]
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--retries", "2"],
                catch_exceptions=False,
            )
            memory = (Path(td) / "agents" / "scout" / "memory.md").read_text()
            assert "Reflection" not in memory

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_learn_not_written_on_first_pass(self, mock_get_prov, mock_eval, tmp_path):
        """No reflection needed if the agent passes on first try."""
        mock_get_prov.return_value = _mock_provider()
        mock_eval.return_value = _good_eval()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--learn"],
                catch_exceptions=False,
            )
            memory = (Path(td) / "agents" / "scout" / "memory.md").read_text()
            # No retry happened, so no reflection to record
            assert "Reflection" not in memory

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_learn_writes_on_final_failure(self, mock_get_prov, mock_eval, tmp_path):
        """Even exhausted retries should save learning if --learn is set."""
        mock_get_prov.return_value = _mock_provider()
        mock_eval.return_value = _bad_eval()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--learn", "--retries", "1"],
            )
            assert result.exit_code != 0
            memory = (Path(td) / "agents" / "scout" / "memory.md").read_text()
            assert "Reflection" in memory
            assert "Key feedback" in memory

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_learn_preserves_existing_memory(self, mock_get_prov, mock_eval, tmp_path):
        """--learn should append, not overwrite existing memory."""
        mock_get_prov.return_value = _mock_provider()
        mock_eval.side_effect = [_bad_eval(), _good_eval()]
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            # Write some existing memory content
            memory_path = Path(td) / "agents" / "scout" / "memory.md"
            memory_path.write_text("# Memory -- scout\n\nPrevious important context.\n")

            runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--learn", "--retries", "2"],
                catch_exceptions=False,
            )
            memory = memory_path.read_text()
            assert "Previous important context" in memory
            assert "Reflection" in memory

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_learn_includes_feedback(self, mock_get_prov, mock_eval, tmp_path):
        mock_get_prov.return_value = _mock_provider()
        mock_eval.side_effect = [_bad_eval(), _good_eval()]
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--learn", "--retries", "2"],
                catch_exceptions=False,
            )
            memory = (Path(td) / "agents" / "scout" / "memory.md").read_text()
            # Should include judge feedback
            assert "Logic Judge" in memory or "Consistency Judge" in memory


class TestFullLoop:
    """End-to-end: run → eval → reflect → retry → trust update → memory."""

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_complete_self_eval_loop(self, mock_get_prov, mock_eval, tmp_path):
        """The full DGM loop: task → eval → fail → reflect → retry → pass → trust + learn."""
        mock_get_prov.return_value = _mock_provider()
        mock_eval.side_effect = [_bad_eval(), _good_eval()]
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream", "--eval", "--learn", "--retries", "2"],
                catch_exceptions=False,
            )

            # 1. Task completed
            assert result.exit_code == 0

            # 2. Events emitted correctly
            events = _read_events(td)
            types = [e["type"] for e in events]
            assert types.count("task.started") == 2
            assert types.count("task.completed") == 2
            assert types.count("eval.started") == 2
            assert types.count("eval.completed") == 2

            # 3. Trust profile updated
            spine = EventSpine(Path(td))
            profile = TrustProfile.for_agent(spine, "scout")
            assert profile.eval_count == 2
            assert len(profile.overall_scores) == 2

            # 4. Memory updated with learning
            memory = (Path(td) / "agents" / "scout" / "memory.md").read_text()
            assert "Reflection" in memory
            assert "Score trajectory" in memory

            # 5. Output includes improvement narrative
            assert "FAIL" in result.output
            assert "PASS" in result.output
            assert "Improved" in result.output

    @patch("claws.commands.run.evaluate_response")
    @patch("claws.commands.run.get_provider")
    def test_no_eval_no_events(self, mock_get_prov, mock_eval, tmp_path):
        """Without --eval, no eval events should be emitted."""
        mock_get_prov.return_value = _mock_provider()
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            runner.invoke(
                main,
                ["run", "scout", "explain X", "--no-stream"],
                catch_exceptions=False,
            )
            events = _read_events(td)
            types = [e["type"] for e in events]
            assert "eval.started" not in types
            assert "eval.completed" not in types
            # evaluate_response should never have been called
            mock_eval.assert_not_called()

            # Trust profile should be empty
            spine = EventSpine(Path(td))
            profile = TrustProfile.for_agent(spine, "scout")
            assert profile.eval_count == 0
            assert profile.trend == "new"
