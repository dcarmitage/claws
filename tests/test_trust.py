"""Tests for claws.trust — TrustProfile computation from event log."""

import pytest

from claws.events import EventSpine, Event, EVAL_COMPLETED, DEPLOY_COMPLETED
from claws.trust import TrustProfile


def _emit_eval(spine: EventSpine, agent: str, judge_scores: dict[str, float]):
    """Helper: emit an EVAL_COMPLETED event with given judge overall scores.

    judge_scores maps judge name to overall score, e.g. {"logic": 8.5, "consistency": 7.0}.
    """
    results = {}
    for judge_name, overall in judge_scores.items():
        results[judge_name] = {
            "scores": {"accuracy": overall, "clarity": overall},
            "overall": overall,
        }
    spine.emit(Event(
        type=EVAL_COMPLETED,
        agent=agent,
        data={
            "results": results,
            "all_passed": all(s >= 8.0 for s in judge_scores.values()),
            "elapsed_s": 1.0,
        },
    ))


class TestTrustProfileNoEvals:
    """TrustProfile with zero evaluations."""

    def test_trend_is_new(self, tmp_path):
        spine = EventSpine(tmp_path)
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.trend == "new"

    def test_average_is_none(self, tmp_path):
        spine = EventSpine(tmp_path)
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.average is None

    def test_eval_count_zero(self, tmp_path):
        spine = EventSpine(tmp_path)
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.eval_count == 0

    def test_empty_judge_averages(self, tmp_path):
        spine = EventSpine(tmp_path)
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.judge_averages == {}

    def test_empty_overall_scores(self, tmp_path):
        spine = EventSpine(tmp_path)
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.overall_scores == []


class TestTrustProfileOneEval:
    """TrustProfile with a single evaluation."""

    def test_trend_is_insufficient(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 8.5, "consistency": 7.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.trend == "insufficient"

    def test_has_average(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 6.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.average is not None
        assert profile.average == pytest.approx(7.0)

    def test_eval_count_one(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 9.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.eval_count == 1

    def test_judge_averages(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 8.5, "consistency": 7.0})
        profile = TrustProfile.for_agent(spine, "scout")
        avgs = profile.judge_averages
        assert avgs["logic"] == pytest.approx(8.5)
        assert avgs["consistency"] == pytest.approx(7.0)


class TestTrustProfileTwoEvals:
    """TrustProfile with two evaluations — still insufficient data for trend."""

    def test_trend_is_insufficient(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 7.0})
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 8.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.trend == "insufficient"

    def test_eval_count_two(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 7.0})
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 8.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.eval_count == 2


class TestTrustProfileStable:
    """TrustProfile with 3+ evals showing stable trend."""

    def test_stable_trend(self, tmp_path):
        spine = EventSpine(tmp_path)
        # All scores similar — delta should be within [-0.5, 0.5]
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.trend == "stable"

    def test_eval_count(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.eval_count == 3

    def test_average(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.average == pytest.approx(8.0)


class TestTrustProfileImproving:
    """TrustProfile with 3+ evals showing improving trend."""

    def test_improving_trend(self, tmp_path):
        spine = EventSpine(tmp_path)
        # Start low, end high — recent average should exceed overall by > 0.5
        _emit_eval(spine, "scout", {"logic": 5.0, "consistency": 5.0})
        _emit_eval(spine, "scout", {"logic": 5.0, "consistency": 5.0})
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 9.0})
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 9.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.trend == "improving"

    def test_improving_average_reflects_all(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 5.0, "consistency": 5.0})
        _emit_eval(spine, "scout", {"logic": 5.0, "consistency": 5.0})
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 9.0})
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 9.0})
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 9.0})
        profile = TrustProfile.for_agent(spine, "scout")
        # Average of [5, 5, 9, 9, 9] = 7.4
        assert profile.average == pytest.approx(7.4)


class TestTrustProfileDeclining:
    """TrustProfile with 3+ evals showing declining trend."""

    def test_declining_trend(self, tmp_path):
        spine = EventSpine(tmp_path)
        # Start high, end low — recent average should be below overall by > 0.5
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 9.0})
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 9.0})
        _emit_eval(spine, "scout", {"logic": 5.0, "consistency": 5.0})
        _emit_eval(spine, "scout", {"logic": 5.0, "consistency": 5.0})
        _emit_eval(spine, "scout", {"logic": 5.0, "consistency": 5.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.trend == "declining"


class TestTrustProfileJudgeAverages:
    """Test judge_averages property across multiple evals."""

    def test_multi_eval_judge_averages(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 6.0})
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 7.0})
        _emit_eval(spine, "scout", {"logic": 7.0, "consistency": 8.0})
        profile = TrustProfile.for_agent(spine, "scout")
        avgs = profile.judge_averages
        assert avgs["logic"] == pytest.approx(8.0)
        assert avgs["consistency"] == pytest.approx(7.0)


class TestTrustProfileAgentIsolation:
    """Events from other agents should not affect the target agent's profile."""

    def test_ignores_other_agents(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 9.0})
        _emit_eval(spine, "builder", {"logic": 3.0, "consistency": 3.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.eval_count == 1
        assert profile.average == pytest.approx(9.0)


class TestDeployCompletedEventType:
    """DEPLOY_COMPLETED event type constant exists in events module."""

    def test_deploy_completed_exists(self):
        assert DEPLOY_COMPLETED == "deploy.completed"

    def test_deploy_completed_is_string(self):
        assert isinstance(DEPLOY_COMPLETED, str)
