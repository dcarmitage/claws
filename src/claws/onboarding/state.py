"""Onboarding state persistence — tracks agent progress through curriculum.

State files live at agents/<name>/.onboarding/state.yaml and record
the current position, task scores, and failure reflections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class TaskState:
    """State of a single task attempt."""
    id: str
    status: str = "pending"          # pending, in_progress, passed, failed, skipped
    attempts: int = 0
    max_retries: int = 2
    scores: list[float] = field(default_factory=list)
    scenario: str | None = None
    reflection: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "id": self.id,
            "status": self.status,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
        }
        if self.scores:
            d["scores"] = self.scores
        if self.scenario is not None:
            d["scenario"] = self.scenario
        if self.reflection is not None:
            d["reflection"] = self.reflection
        return d


@dataclass
class PhaseState:
    """State of a phase containing multiple tasks."""
    name: str
    status: str = "pending"          # pending, in_progress, passed, failed
    tasks: list[TaskState] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "tasks": [t.to_dict() for t in self.tasks],
        }


@dataclass
class OnboardingState:
    """Full onboarding state for an agent."""
    agent: str
    curriculum: str
    status: str = "pending"          # pending, in_progress, completed, failed
    seed: int | None = None
    traits: dict[str, str] = field(default_factory=dict)
    phases: list[PhaseState] = field(default_factory=list)
    current_phase: int = 0
    current_task: int = 0

    @classmethod
    def load(cls, state_path: Path) -> OnboardingState:
        """Load onboarding state from a YAML file."""
        with open(state_path) as f:
            raw = yaml.safe_load(f) or {}

        phases = []
        for phase_raw in raw.get("phases", []):
            tasks = []
            for task_raw in phase_raw.get("tasks", []):
                tasks.append(TaskState(
                    id=task_raw["id"],
                    status=task_raw.get("status", "pending"),
                    attempts=task_raw.get("attempts", 0),
                    max_retries=task_raw.get("max_retries", 2),
                    scores=task_raw.get("scores", []),
                    scenario=task_raw.get("scenario"),
                    reflection=task_raw.get("reflection"),
                ))
            phases.append(PhaseState(
                name=phase_raw["name"],
                status=phase_raw.get("status", "pending"),
                tasks=tasks,
            ))

        return cls(
            agent=raw["agent"],
            curriculum=raw["curriculum"],
            status=raw.get("status", "pending"),
            seed=raw.get("seed"),
            traits=raw.get("traits", {}),
            phases=phases,
            current_phase=raw.get("current_phase", 0),
            current_task=raw.get("current_task", 0),
        )

    def save(self, state_path: Path) -> None:
        """Save onboarding state to a YAML file."""
        state_path.parent.mkdir(parents=True, exist_ok=True)

        data: dict = {
            "agent": self.agent,
            "curriculum": self.curriculum,
            "status": self.status,
            "current_phase": self.current_phase,
            "current_task": self.current_task,
        }
        if self.seed is not None:
            data["seed"] = self.seed
        if self.traits:
            data["traits"] = self.traits
        data["phases"] = [p.to_dict() for p in self.phases]

        with open(state_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def next_task(self) -> tuple[int, int] | None:
        """Find the next pending or failed-but-retriable task.

        Returns (phase_idx, task_idx) or None if all tasks are done.
        Scans from current_phase/current_task forward.
        """
        for pi in range(self.current_phase, len(self.phases)):
            phase = self.phases[pi]
            start_ti = self.current_task if pi == self.current_phase else 0
            for ti in range(start_ti, len(phase.tasks)):
                task = phase.tasks[ti]
                if task.status == "pending":
                    return (pi, ti)
                if task.status == "failed" and task.attempts < task.max_retries:
                    return (pi, ti)
        return None
