"""Tests for autonomy tier system — trust scores mapping to permission levels."""

import pytest
import yaml
from pathlib import Path
from click.testing import CliRunner

from claws.cli import main
from claws.events import EventSpine, Event, EVAL_COMPLETED
from claws.trust import (
    TrustProfile,
    AutonomyTier,
    compute_tier,
    tier_label,
    tier_permissions,
    TIER_STANDARD_THRESHOLD,
    TIER_AUTONOMOUS_THRESHOLD,
    TIER_PERMISSIONS,
)


def _emit_eval(spine: EventSpine, agent: str, judge_scores: dict[str, float]):
    """Helper: emit an EVAL_COMPLETED event."""
    results = {}
    for judge_name, overall in judge_scores.items():
        results[judge_name] = {
            "scores": {"accuracy": overall, "clarity": overall},
            "overall": overall,
        }
    spine.emit(Event(
        type=EVAL_COMPLETED,
        agent=agent,
        data={"results": results, "all_passed": True, "elapsed_s": 1.0},
    ))


def _make_project(td_path: Path, agents=None):
    """Helper: create a project."""
    if agents is None:
        agents = {}
    config = {
        "project": "test-project",
        "version": 2,
        "providers": {
            "default": {"type": "anthropic", "model": "claude-sonnet-4-5-20250929"},
        },
        "agents": agents,
        "eval": {"judges": ["logic", "consistency"], "threshold": 8.0},
    }
    (td_path / "claws.yaml").write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False)
    )
    (td_path / "agents").mkdir(exist_ok=True)
    (td_path / ".claws").mkdir(exist_ok=True)


def _make_agent(td_path: Path, name: str, role: str = "researcher"):
    agent_dir = td_path / "agents" / name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "identity.md").write_text(f"# {name}\nRole: {role}\n")
    (agent_dir / "memory.md").write_text(f"# {name} Memory\n")
    config_path = td_path / "claws.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["agents"][name] = {"role": role, "provider": "default", "machine": "local"}
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))


# =============================================================================
# Core Tier Model Tests
# =============================================================================


class TestAutonomyTierEnum:
    def test_values(self):
        assert AutonomyTier.RESTRICTED.value == "restricted"
        assert AutonomyTier.STANDARD.value == "standard"
        assert AutonomyTier.AUTONOMOUS.value == "autonomous"

    def test_is_enum(self):
        assert len(AutonomyTier) == 3


class TestComputeTier:
    def test_none_score_is_restricted(self):
        assert compute_tier(None) == AutonomyTier.RESTRICTED

    def test_low_score_is_restricted(self):
        assert compute_tier(5.0) == AutonomyTier.RESTRICTED

    def test_below_standard_threshold(self):
        assert compute_tier(6.9) == AutonomyTier.RESTRICTED

    def test_at_standard_threshold(self):
        assert compute_tier(TIER_STANDARD_THRESHOLD) == AutonomyTier.STANDARD

    def test_mid_standard_range(self):
        assert compute_tier(7.5) == AutonomyTier.STANDARD

    def test_at_standard_ceiling(self):
        assert compute_tier(8.5) == AutonomyTier.STANDARD

    def test_above_autonomous_threshold(self):
        assert compute_tier(8.6) == AutonomyTier.AUTONOMOUS

    def test_high_score_is_autonomous(self):
        assert compute_tier(9.5) == AutonomyTier.AUTONOMOUS

    def test_perfect_score(self):
        assert compute_tier(10.0) == AutonomyTier.AUTONOMOUS

    def test_zero_score(self):
        assert compute_tier(0.0) == AutonomyTier.RESTRICTED


class TestTierLabel:
    def test_restricted(self):
        assert tier_label(AutonomyTier.RESTRICTED) == "Restricted"

    def test_standard(self):
        assert tier_label(AutonomyTier.STANDARD) == "Standard"

    def test_autonomous(self):
        assert tier_label(AutonomyTier.AUTONOMOUS) == "Autonomous"


class TestTierPermissions:
    def test_restricted_permissions(self):
        perms = tier_permissions(AutonomyTier.RESTRICTED)
        assert "execute assigned tasks" in perms
        assert "report results" in perms
        assert "push code changes" not in perms
        assert "maintain scratchpad" not in perms

    def test_standard_permissions(self):
        perms = tier_permissions(AutonomyTier.STANDARD)
        assert "execute assigned tasks" in perms
        assert "propose actions" in perms
        assert "surface decisions" in perms
        assert "maintain scratchpad" in perms
        assert "push code changes" not in perms

    def test_autonomous_permissions(self):
        perms = tier_permissions(AutonomyTier.AUTONOMOUS)
        assert "execute assigned tasks" in perms
        assert "propose actions" in perms
        assert "push code changes" in perms
        assert "take independent action" in perms
        assert "modify configurations" in perms

    def test_permissions_are_cumulative(self):
        """Higher tiers have all lower tier permissions plus more."""
        r = set(tier_permissions(AutonomyTier.RESTRICTED))
        s = set(tier_permissions(AutonomyTier.STANDARD))
        a = set(tier_permissions(AutonomyTier.AUTONOMOUS))
        assert r.issubset(s)
        assert s.issubset(a)

    def test_returns_new_list(self):
        """Should return a copy, not the original."""
        p1 = tier_permissions(AutonomyTier.RESTRICTED)
        p2 = tier_permissions(AutonomyTier.RESTRICTED)
        assert p1 == p2
        assert p1 is not p2


# =============================================================================
# TrustProfile Tier Integration
# =============================================================================


class TestTrustProfileTier:
    def test_no_evals_is_restricted(self, tmp_path):
        spine = EventSpine(tmp_path)
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.tier == AutonomyTier.RESTRICTED

    def test_low_score_is_restricted(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 5.0, "consistency": 5.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.tier == AutonomyTier.RESTRICTED

    def test_mid_score_is_standard(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 7.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.tier == AutonomyTier.STANDARD

    def test_high_score_is_autonomous(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 9.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.tier == AutonomyTier.AUTONOMOUS

    def test_permissions_match_tier(self, tmp_path):
        spine = EventSpine(tmp_path)
        _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 7.0})
        profile = TrustProfile.for_agent(spine, "scout")
        assert profile.permissions == tier_permissions(AutonomyTier.STANDARD)


# =============================================================================
# CLI Command Tests
# =============================================================================


class TestAgentTierCommand:
    def test_tier_restricted(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            result = runner.invoke(main, ["agent", "tier", "scout"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Restricted" in result.output
            assert "no evaluations" in result.output

    def test_tier_standard(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            spine = EventSpine(Path(td))
            _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 7.0})
            result = runner.invoke(main, ["agent", "tier", "scout"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Standard" in result.output
            assert "propose actions" in result.output

    def test_tier_autonomous(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            spine = EventSpine(Path(td))
            _emit_eval(spine, "scout", {"logic": 9.0, "consistency": 9.0})
            result = runner.invoke(main, ["agent", "tier", "scout"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Autonomous" in result.output
            assert "push code changes" in result.output

    def test_tier_shows_score(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            spine = EventSpine(Path(td))
            _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
            result = runner.invoke(main, ["agent", "tier", "scout"], catch_exceptions=False)
            assert "8.0" in result.output

    def test_tier_nonexistent_agent(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            result = runner.invoke(main, ["agent", "tier", "ghost"])
            assert result.exit_code != 0
            assert "not found" in result.output.lower()

    def test_tier_no_project(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["agent", "tier", "scout"])
            assert result.exit_code != 0


class TestAgentInfoShowsTier:
    def test_info_includes_tier(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _make_project(Path(td))
            _make_agent(Path(td), "scout")
            spine = EventSpine(Path(td))
            _emit_eval(spine, "scout", {"logic": 8.0, "consistency": 8.0})
            result = runner.invoke(main, ["agent", "info", "scout"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Tier:" in result.output


class TestStatusShowsTier:
    def test_status_has_tier_column(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            agents = {
                "scout": {"role": "researcher", "provider": "default", "machine": "local"},
            }
            _make_project(Path(td), agents=agents)
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Tier" in result.output

    def test_status_shows_restricted_for_new_agent(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            agents = {
                "scout": {"role": "researcher", "provider": "default", "machine": "local"},
            }
            _make_project(Path(td), agents=agents)
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Restricted" in result.output

    def test_status_shows_autonomous_for_high_trust(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            agents = {
                "scout": {"role": "researcher", "provider": "default", "machine": "local"},
            }
            _make_project(Path(td), agents=agents)
            spine = EventSpine(Path(td))
            _emit_eval(spine, "scout", {"logic": 9.5, "consistency": 9.0})
            result = runner.invoke(main, ["status"], catch_exceptions=False)
            assert result.exit_code == 0
            assert "Autonomous" in result.output
