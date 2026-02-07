"""Tests for claws.onboarding.state — save/load, next_task, transitions."""

import pytest
import yaml
from pathlib import Path

from claws.onboarding.state import (
    TaskState,
    PhaseState,
    OnboardingState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(
    agent="scout",
    curriculum="default",
    status="pending",
    seed=42,
    phases=None,
    current_phase=0,
    current_task=0,
):
    """Build an OnboardingState for testing."""
    if phases is None:
        phases = [
            PhaseState(
                name="foundation",
                status="pending",
                tasks=[
                    TaskState(id="f01", status="pending"),
                    TaskState(id="f02", status="pending"),
                ],
            ),
            PhaseState(
                name="domain",
                status="pending",
                tasks=[
                    TaskState(id="d01", status="pending"),
                ],
            ),
        ]
    return OnboardingState(
        agent=agent,
        curriculum=curriculum,
        status=status,
        seed=seed,
        traits={"cognitive_style": "methodical"},
        phases=phases,
        current_phase=current_phase,
        current_task=current_task,
    )


# ---------------------------------------------------------------------------
# Save / Load Round-trip
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_round_trip(self, tmp_path):
        """Save then load should produce identical state."""
        state = _make_state()
        path = tmp_path / ".onboarding" / "state.yaml"

        state.save(path)
        loaded = OnboardingState.load(path)

        assert loaded.agent == state.agent
        assert loaded.curriculum == state.curriculum
        assert loaded.status == state.status
        assert loaded.seed == state.seed
        assert loaded.traits == state.traits
        assert loaded.current_phase == state.current_phase
        assert loaded.current_task == state.current_task
        assert len(loaded.phases) == len(state.phases)

    def test_round_trip_tasks(self, tmp_path):
        """Task details should survive save/load."""
        state = _make_state()
        state.phases[0].tasks[0].status = "passed"
        state.phases[0].tasks[0].attempts = 1
        state.phases[0].tasks[0].scores = [8.5, 9.0]
        state.phases[0].tasks[0].scenario = "Test scenario"
        state.phases[0].tasks[0].reflection = "I learned something."

        path = tmp_path / "state.yaml"
        state.save(path)
        loaded = OnboardingState.load(path)

        task = loaded.phases[0].tasks[0]
        assert task.status == "passed"
        assert task.attempts == 1
        assert task.scores == [8.5, 9.0]
        assert task.scenario == "Test scenario"
        assert task.reflection == "I learned something."

    def test_creates_parent_directory(self, tmp_path):
        """save() should create parent directories if they don't exist."""
        state = _make_state()
        path = tmp_path / "deep" / "nested" / "state.yaml"

        state.save(path)
        assert path.exists()

    def test_save_produces_valid_yaml(self, tmp_path):
        """Saved file should be valid, human-readable YAML."""
        state = _make_state()
        path = tmp_path / "state.yaml"

        state.save(path)
        raw = yaml.safe_load(path.read_text())

        assert raw["agent"] == "scout"
        assert raw["curriculum"] == "default"
        assert isinstance(raw["phases"], list)

    def test_load_missing_optional_fields(self, tmp_path):
        """Loading YAML with missing optional fields should use defaults."""
        raw = {
            "agent": "minimal",
            "curriculum": "default",
            "phases": [
                {
                    "name": "foundation",
                    "tasks": [{"id": "f01"}],
                },
            ],
        }
        path = tmp_path / "state.yaml"
        path.write_text(yaml.dump(raw, default_flow_style=False))

        loaded = OnboardingState.load(path)
        assert loaded.status == "pending"
        assert loaded.seed is None
        assert loaded.traits == {}
        assert loaded.current_phase == 0
        assert loaded.phases[0].status == "pending"
        assert loaded.phases[0].tasks[0].status == "pending"
        assert loaded.phases[0].tasks[0].attempts == 0

    def test_seed_none_not_saved(self, tmp_path):
        """When seed is None, it should not appear in the YAML."""
        state = _make_state(seed=None)
        path = tmp_path / "state.yaml"

        state.save(path)
        raw = yaml.safe_load(path.read_text())

        assert "seed" not in raw

    def test_empty_scores_not_saved(self, tmp_path):
        """Tasks with empty scores should not include scores key."""
        state = _make_state()
        path = tmp_path / "state.yaml"

        state.save(path)
        raw = yaml.safe_load(path.read_text())

        task_raw = raw["phases"][0]["tasks"][0]
        assert "scores" not in task_raw


# ---------------------------------------------------------------------------
# next_task
# ---------------------------------------------------------------------------

class TestNextTask:
    def test_first_task(self):
        """Fresh state should return (0, 0)."""
        state = _make_state()
        assert state.next_task() == (0, 0)

    def test_advances_within_phase(self):
        """After first task passes, should return second task."""
        state = _make_state()
        state.phases[0].tasks[0].status = "passed"
        state.current_task = 1

        assert state.next_task() == (0, 1)

    def test_advances_to_next_phase(self):
        """After all tasks in phase pass, should move to next phase."""
        state = _make_state()
        state.phases[0].tasks[0].status = "passed"
        state.phases[0].tasks[1].status = "passed"
        state.current_phase = 1
        state.current_task = 0

        assert state.next_task() == (1, 0)

    def test_none_when_all_done(self):
        """After all tasks pass, should return None."""
        state = _make_state()
        for phase in state.phases:
            for task in phase.tasks:
                task.status = "passed"
        state.current_phase = 1
        state.current_task = 1  # past the last task

        assert state.next_task() is None

    def test_failed_with_retries_available(self):
        """Failed task with retries left should be returned."""
        state = _make_state()
        state.phases[0].tasks[0].status = "failed"
        state.phases[0].tasks[0].attempts = 1
        state.phases[0].tasks[0].max_retries = 2

        assert state.next_task() == (0, 0)

    def test_failed_exhausted_retries_skipped(self):
        """Failed task with no retries left should be skipped."""
        state = _make_state()
        state.phases[0].tasks[0].status = "failed"
        state.phases[0].tasks[0].attempts = 2
        state.phases[0].tasks[0].max_retries = 2

        assert state.next_task() == (0, 1)

    def test_skipped_tasks_skipped(self):
        """Skipped tasks should not be returned."""
        state = _make_state()
        state.phases[0].tasks[0].status = "skipped"

        assert state.next_task() == (0, 1)

    def test_in_progress_skipped(self):
        """In-progress tasks should not be returned (they are being worked on)."""
        state = _make_state()
        state.phases[0].tasks[0].status = "in_progress"

        assert state.next_task() == (0, 1)

    def test_mixed_statuses(self):
        """Should find the next actionable task across mixed statuses."""
        state = _make_state()
        state.phases[0].tasks[0].status = "passed"
        state.phases[0].tasks[1].status = "failed"
        state.phases[0].tasks[1].attempts = 3
        state.phases[0].tasks[1].max_retries = 2
        # Both foundation tasks done/exhausted, domain task pending
        state.current_phase = 0
        state.current_task = 0

        result = state.next_task()
        assert result == (1, 0)


# ---------------------------------------------------------------------------
# TaskState
# ---------------------------------------------------------------------------

class TestTaskState:
    def test_default_values(self):
        """TaskState should have sensible defaults."""
        t = TaskState(id="f01")
        assert t.status == "pending"
        assert t.attempts == 0
        assert t.max_retries == 2
        assert t.scores == []
        assert t.scenario is None
        assert t.reflection is None

    def test_to_dict_minimal(self):
        """to_dict should exclude None/empty optional fields."""
        t = TaskState(id="f01")
        d = t.to_dict()
        assert d["id"] == "f01"
        assert d["status"] == "pending"
        assert "scores" not in d
        assert "scenario" not in d
        assert "reflection" not in d

    def test_to_dict_full(self):
        """to_dict should include all non-empty fields."""
        t = TaskState(
            id="f01",
            status="passed",
            attempts=2,
            max_retries=3,
            scores=[7.5, 8.0],
            scenario="Test scenario",
            reflection="I learned things.",
        )
        d = t.to_dict()
        assert d["scores"] == [7.5, 8.0]
        assert d["scenario"] == "Test scenario"
        assert d["reflection"] == "I learned things."


# ---------------------------------------------------------------------------
# PhaseState
# ---------------------------------------------------------------------------

class TestPhaseState:
    def test_default_values(self):
        """PhaseState should have sensible defaults."""
        p = PhaseState(name="foundation")
        assert p.status == "pending"
        assert p.tasks == []

    def test_to_dict(self):
        """to_dict should serialize phase and its tasks."""
        p = PhaseState(
            name="foundation",
            status="in_progress",
            tasks=[TaskState(id="f01"), TaskState(id="f02")],
        )
        d = p.to_dict()
        assert d["name"] == "foundation"
        assert d["status"] == "in_progress"
        assert len(d["tasks"]) == 2


# ---------------------------------------------------------------------------
# OnboardingState
# ---------------------------------------------------------------------------

class TestOnboardingState:
    def test_default_values(self):
        """OnboardingState should have sensible defaults."""
        s = OnboardingState(agent="test", curriculum="default")
        assert s.status == "pending"
        assert s.seed is None
        assert s.traits == {}
        assert s.phases == []
        assert s.current_phase == 0
        assert s.current_task == 0
