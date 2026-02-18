"""Trust Profiles — track agent evaluation history and quality trends.

A TrustProfile aggregates evaluation results from the event log
to provide per-agent quality metrics, judge-level breakdowns, and
directional trends over time.

Autonomy tiers map trust scores to permission levels:
- RESTRICTED (score < 7.0): Execute assigned tasks, report results.
- STANDARD (score 7.0–8.5): Propose actions, surface decisions, maintain working state.
- AUTONOMOUS (score > 8.5): Take independent action, push code, modify configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from claws.events import EventSpine, EVAL_COMPLETED


# --- Autonomy Tier System ---

# Tier boundary constants (configurable in future via claws.yaml)
TIER_STANDARD_THRESHOLD = 7.0
TIER_AUTONOMOUS_THRESHOLD = 8.5


class AutonomyTier(Enum):
    """Permission tiers derived from trust scores."""
    RESTRICTED = "restricted"
    STANDARD = "standard"
    AUTONOMOUS = "autonomous"


# Permissions granted at each tier
TIER_PERMISSIONS: dict[AutonomyTier, list[str]] = {
    AutonomyTier.RESTRICTED: [
        "execute assigned tasks",
        "report results",
        "read project files",
    ],
    AutonomyTier.STANDARD: [
        "execute assigned tasks",
        "report results",
        "read project files",
        "propose actions",
        "surface decisions",
        "maintain scratchpad",
        "update working memory",
    ],
    AutonomyTier.AUTONOMOUS: [
        "execute assigned tasks",
        "report results",
        "read project files",
        "propose actions",
        "surface decisions",
        "maintain scratchpad",
        "update working memory",
        "take independent action",
        "push code changes",
        "modify configurations",
        "run automated tasks",
    ],
}


def compute_tier(score: float | None) -> AutonomyTier:
    """Compute autonomy tier from average trust score."""
    if score is None:
        return AutonomyTier.RESTRICTED
    if score > TIER_AUTONOMOUS_THRESHOLD:
        return AutonomyTier.AUTONOMOUS
    if score >= TIER_STANDARD_THRESHOLD:
        return AutonomyTier.STANDARD
    return AutonomyTier.RESTRICTED


def tier_label(tier: AutonomyTier) -> str:
    """Human-readable label for a tier."""
    labels = {
        AutonomyTier.RESTRICTED: "Restricted",
        AutonomyTier.STANDARD: "Standard",
        AutonomyTier.AUTONOMOUS: "Autonomous",
    }
    return labels[tier]


def tier_permissions(tier: AutonomyTier) -> list[str]:
    """Return the list of permissions for a tier."""
    return list(TIER_PERMISSIONS[tier])


@dataclass
class TrustProfile:
    """Aggregated trust metrics for a single agent."""

    agent: str
    eval_count: int = 0
    scores_by_judge: dict[str, list[float]] = field(default_factory=dict)
    overall_scores: list[float] = field(default_factory=list)
    trend: str = "new"  # new, insufficient, improving, declining, stable

    @property
    def average(self) -> float | None:
        """Average of all overall scores, or None if no evals."""
        if not self.overall_scores:
            return None
        return sum(self.overall_scores) / len(self.overall_scores)

    @property
    def tier(self) -> AutonomyTier:
        """Compute autonomy tier from average score."""
        return compute_tier(self.average)

    @property
    def permissions(self) -> list[str]:
        """Return permissions for this agent's current tier."""
        return tier_permissions(self.tier)

    @property
    def judge_averages(self) -> dict[str, float]:
        """Per-judge average scores."""
        return {
            judge: sum(scores) / len(scores)
            for judge, scores in self.scores_by_judge.items()
            if scores
        }

    @classmethod
    def for_agent(cls, spine: EventSpine, agent: str) -> TrustProfile:
        """Build trust profile from event log for an agent."""
        eval_events = [
            e for e in spine.read_by_type(EVAL_COMPLETED)
            if e.agent == agent
        ]

        profile = cls(agent=agent, eval_count=len(eval_events))

        if not eval_events:
            profile.trend = "new"
            return profile

        for event in eval_events:
            results = event.data.get("results", {})
            for judge_name, judge_result in results.items():
                if judge_name not in profile.scores_by_judge:
                    profile.scores_by_judge[judge_name] = []
                overall = judge_result.get("overall", 0)
                profile.scores_by_judge[judge_name].append(overall)

            # Compute overall for this eval (average of judge overalls)
            judge_overalls = [
                r.get("overall", 0) for r in results.values()
            ]
            if judge_overalls:
                profile.overall_scores.append(
                    sum(judge_overalls) / len(judge_overalls)
                )

        # Compute trend
        if len(profile.overall_scores) < 3:
            profile.trend = "insufficient"
        else:
            overall_avg = sum(profile.overall_scores) / len(profile.overall_scores)
            recent_avg = sum(profile.overall_scores[-3:]) / 3
            delta = recent_avg - overall_avg
            if delta > 0.5:
                profile.trend = "improving"
            elif delta < -0.5:
                profile.trend = "declining"
            else:
                profile.trend = "stable"

        return profile
