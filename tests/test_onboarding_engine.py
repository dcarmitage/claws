"""Tests for the OnboardingEngine — curriculum-driven agent onboarding."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import yaml

from claws.config import CONFIG_FILENAME
from claws.events import (
    EventSpine,
    ONBOARD_STARTED,
    ONBOARD_PHASE_STARTED,
    ONBOARD_TASK_COMPLETED,
    ONBOARD_TASK_FAILED,
    ONBOARD_PHASE_COMPLETED,
    ONBOARD_COMPLETED,
    TASK_STARTED,
    TASK_COMPLETED,
    EVAL_STARTED,
    EVAL_COMPLETED,
)
from claws.onboarding.engine import OnboardingEngine
from claws.onboarding.state import OnboardingState


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal claws project with an agent for testing."""
    config = {
        "project": "test-project",
        "version": 2,
        "providers": {
            "default": {
                "type": "openai-compatible",
                "model": "test-model",
                "base_url": "http://localhost:9999/v1",
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
            "threshold": 8.0,
        },
    }
    (tmp_path / CONFIG_FILENAME).write_text(
        yaml.dump(config, default_flow_style=False, sort_keys=False)
    )
    (tmp_path / "agents" / "scout" / "output").mkdir(parents=True)
    (tmp_path / "agents" / "scout" / "identity.md").write_text("# scout\n\n## Role\nresearcher\n")
    (tmp_path / "agents" / "scout" / "memory.md").write_text("# Memory -- scout\n")
    (tmp_path / ".claws").mkdir(exist_ok=True)
    return tmp_path


def _make_simple_curriculum(tmp_path: Path, **overrides) -> Path:
    """Create a minimal curriculum YAML for testing."""
    curriculum = {
        "name": "test-curriculum",
        "version": 1,
        "description": "Test curriculum",
        "defaults": {
            "eval_threshold": overrides.get("eval_threshold", 7.0),
            "max_retries": overrides.get("max_retries", 1),
            "retry_strategy": "reflect",
        },
        "personality": {
            "temperature_offset": 0.1,
            "traits": {
                "style": {
                    "pick": 1,
                    "pool": ["methodical", "intuitive"],
                },
            },
            "reflections": overrides.get("reflections", []),
        },
        "phases": overrides.get("phases", [
            {
                "name": "foundation",
                "description": "Basic tasks",
                "gate": {"min_passed": 1, "min_avg_score": 7.0},
                "tasks": [
                    {
                        "id": "t01",
                        "name": "Test task",
                        "template": "Complete this: {scenario}",
                    },
                ],
            },
        ]),
    }
    curricula_dir = tmp_path / "curricula"
    curricula_dir.mkdir(exist_ok=True)
    path = curricula_dir / "test-curriculum.yaml"
    path.write_text(yaml.dump(curriculum, default_flow_style=False, sort_keys=False))
    return path


def _make_judge_response(judge: str, overall: float) -> str:
    """Create a mock judge JSON response string."""
    return json.dumps({
        "judge": judge,
        "scores": {"dim_a": overall, "dim_b": overall},
        "overall": overall,
        "tier": "excellent" if overall >= 9.0 else "good" if overall >= 7.0 else "poor",
        "rationale": f"Test rationale for {judge}.",
    })


def _make_mock_provider(overall_score: float = 8.5):
    """Create a mock provider that returns a response and then judge scores."""
    mock_provider = MagicMock()
    call_count = 0

    async def mock_complete(messages, **kwargs):
        nonlocal call_count
        call_count += 1

        result = MagicMock()
        # First call is the task execution, subsequent calls alternate
        # between judges (logic, consistency) and other calls
        # Pattern: task response, logic judge, consistency judge, ...
        if call_count % 3 == 1:
            result.content = "This is the agent's response to the task."
        elif call_count % 3 == 2:
            result.content = _make_judge_response("logic", overall_score)
        else:
            result.content = _make_judge_response("consistency", overall_score)
        return result

    mock_provider.complete = mock_complete
    return mock_provider


class TestOnboardingEngineBasic:
    """Test basic engine creation and initialization."""

    def test_engine_init(self, tmp_path):
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)
        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )
        assert engine.agent_name == "scout"
        assert engine.curriculum_name == "test-curriculum"
        assert engine.seed == 42

    def test_engine_init_missing_agent(self, tmp_path):
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)
        # Engine creation succeeds; failure happens at run time
        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="ghost",
            curriculum_name="test-curriculum",
        )
        assert engine.agent_name == "ghost"


class TestTaskProgression:
    """Test that the engine progresses through tasks correctly."""

    @pytest.mark.asyncio
    async def test_single_task_pass(self, tmp_path):
        """A single task above threshold should pass the phase."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)

        mock_provider = _make_mock_provider(overall_score=8.5)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state = await engine.run()

        assert state.status == "completed"
        assert state.phases[0].status == "passed"
        assert state.phases[0].tasks[0].status == "passed"

    @pytest.mark.asyncio
    async def test_multi_task_pass(self, tmp_path):
        """Multiple tasks that all pass should complete the phase."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path, phases=[
            {
                "name": "foundation",
                "description": "Basic tasks",
                "gate": {"min_passed": 2, "min_avg_score": 7.0},
                "tasks": [
                    {"id": "t01", "name": "Task 1", "template": "Do thing 1"},
                    {"id": "t02", "name": "Task 2", "template": "Do thing 2"},
                ],
            },
        ])

        mock_provider = _make_mock_provider(overall_score=8.0)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state = await engine.run()

        assert state.status == "completed"
        assert all(t.status == "passed" for t in state.phases[0].tasks)

    @pytest.mark.asyncio
    async def test_multi_phase_pass(self, tmp_path):
        """Multiple phases that all pass should complete onboarding."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path, phases=[
            {
                "name": "phase1",
                "description": "First phase",
                "gate": {"min_passed": 1, "min_avg_score": 7.0},
                "tasks": [
                    {"id": "p1t01", "name": "Phase 1 Task", "template": "Do p1"},
                ],
            },
            {
                "name": "phase2",
                "description": "Second phase",
                "gate": {"min_passed": 1, "min_avg_score": 7.0},
                "tasks": [
                    {"id": "p2t01", "name": "Phase 2 Task", "template": "Do p2"},
                ],
            },
        ])

        mock_provider = _make_mock_provider(overall_score=8.0)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state = await engine.run()

        assert state.status == "completed"
        assert state.phases[0].status == "passed"
        assert state.phases[1].status == "passed"


class TestPhaseGating:
    """Test that phase gates work correctly."""

    @pytest.mark.asyncio
    async def test_phase_gate_failure_stops_onboarding(self, tmp_path):
        """When a phase gate fails, onboarding should stop."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path, eval_threshold=7.0, max_retries=0, phases=[
            {
                "name": "foundation",
                "description": "Basic",
                "gate": {"min_passed": 2, "min_avg_score": 7.0},
                "tasks": [
                    {"id": "t01", "name": "Task 1", "template": "Do thing 1"},
                    {"id": "t02", "name": "Task 2", "template": "Do thing 2"},
                ],
            },
            {
                "name": "advanced",
                "description": "Should not reach",
                "gate": {"min_passed": 1, "min_avg_score": 7.0},
                "tasks": [
                    {"id": "t03", "name": "Task 3", "template": "Do thing 3"},
                ],
            },
        ])

        # Score below threshold -- all tasks fail
        mock_provider = _make_mock_provider(overall_score=4.0)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state = await engine.run()

        assert state.status == "failed"
        assert state.phases[0].status == "failed"
        # Second phase should not have started
        assert state.phases[1].status == "pending"

    @pytest.mark.asyncio
    async def test_phase_gate_passes_with_enough_tasks(self, tmp_path):
        """Phase gate should pass if min_passed tasks succeed, even if some fail."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path, eval_threshold=7.0, max_retries=0, phases=[
            {
                "name": "foundation",
                "description": "Basic",
                "gate": {"min_passed": 1, "min_avg_score": 7.0},
                "tasks": [
                    {"id": "t01", "name": "Task 1", "template": "Do thing 1"},
                    {"id": "t02", "name": "Task 2", "template": "Do thing 2"},
                ],
            },
        ])

        call_count = 0
        mock_provider = MagicMock()

        async def mock_complete(messages, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            # Task 1: response, then two failing judges
            # Task 2: response, then two passing judges
            if call_count <= 3:
                # First task chain -- failing
                if call_count == 1:
                    result.content = "Response to task 1."
                elif call_count == 2:
                    result.content = _make_judge_response("logic", 4.0)
                else:
                    result.content = _make_judge_response("consistency", 4.0)
            else:
                # Second task chain -- passing
                if call_count == 4:
                    result.content = "Response to task 2."
                elif call_count == 5:
                    result.content = _make_judge_response("logic", 8.0)
                else:
                    result.content = _make_judge_response("consistency", 8.0)
            return result

        mock_provider.complete = mock_complete

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state = await engine.run()

        assert state.status == "completed"
        assert state.phases[0].tasks[0].status == "failed"
        assert state.phases[0].tasks[1].status == "passed"
        assert state.phases[0].status == "passed"


class TestRetries:
    """Test retry behavior with reflection."""

    @pytest.mark.asyncio
    async def test_retry_after_failure(self, tmp_path):
        """Task should retry after failure with reflection."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path, eval_threshold=7.0, max_retries=1)

        call_count = 0
        mock_provider = MagicMock()

        async def mock_complete(messages, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            # Attempt 1: task, logic fail, consistency fail, reflection
            # Attempt 2: task, logic pass, consistency pass
            if call_count == 1:
                result.content = "First attempt response."
            elif call_count == 2:
                result.content = _make_judge_response("logic", 4.0)
            elif call_count == 3:
                result.content = _make_judge_response("consistency", 4.0)
            elif call_count == 4:
                result.content = "I should have been more specific."  # reflection
            elif call_count == 5:
                result.content = "Second attempt response."
            elif call_count == 6:
                result.content = _make_judge_response("logic", 8.0)
            else:
                result.content = _make_judge_response("consistency", 8.0)
            return result

        mock_provider.complete = mock_complete

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state = await engine.run()

        assert state.status == "completed"
        task_state = state.phases[0].tasks[0]
        assert task_state.status == "passed"
        assert task_state.attempts == 2
        assert len(task_state.scores) == 2

    @pytest.mark.asyncio
    async def test_exhausted_retries(self, tmp_path):
        """When retries are exhausted, the task should fail."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path, eval_threshold=7.0, max_retries=1, phases=[
            {
                "name": "foundation",
                "description": "Basic",
                "gate": {"min_passed": 1, "min_avg_score": 7.0},
                "tasks": [
                    {"id": "t01", "name": "Test task", "template": "Do thing"},
                ],
            },
        ])

        # Always fail
        mock_provider = MagicMock()

        async def mock_complete(messages, **kwargs):
            result = MagicMock()
            # Detect if this is a judge call or task call
            content = messages[-1].content if messages else ""
            if "reflect" in content.lower() or "Reflect" in content or "scored below" in content:
                result.content = "I should try harder."
            elif isinstance(content, str) and len(content) > 100:
                # Likely a judge prompt
                result.content = _make_judge_response("logic", 3.0)
            else:
                result.content = "Bad response."
            return result

        mock_provider.complete = mock_complete

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state = await engine.run()

        assert state.status == "failed"
        task_state = state.phases[0].tasks[0]
        assert task_state.status == "failed"
        assert task_state.attempts == 2  # initial + 1 retry


class TestReflectionTriggers:
    """Test that reflections fire at the right time."""

    @pytest.mark.asyncio
    async def test_reflection_fires_after_correct_task_count(self, tmp_path):
        """Reflection should fire after the configured number of tasks."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path, eval_threshold=7.0, phases=[
            {
                "name": "foundation",
                "description": "Basic",
                "gate": {"min_passed": 2, "min_avg_score": 7.0},
                "tasks": [
                    {"id": "t01", "name": "Task 1", "template": "Do thing 1"},
                    {"id": "t02", "name": "Task 2", "template": "Do thing 2"},
                ],
            },
        ], reflections=[
            {
                "phase": "foundation",
                "after_task": 2,
                "prompt": "Reflect on your work so far.",
            },
        ])

        call_log = []
        mock_provider = MagicMock()

        async def mock_complete(messages, **kwargs):
            content = messages[-1].content if messages else ""
            call_log.append(content[:50])
            result = MagicMock()
            if "Reflect" in content:
                result.content = "I have learned a lot."
            elif "{" in content and "judge" in content:
                result.content = _make_judge_response("logic", 8.5)
            else:
                result.content = "Task response."
            return result

        mock_provider.complete = mock_complete

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state = await engine.run()

        assert state.status == "completed"
        # Check that reflection was written to identity.md
        identity_text = (project_root / "agents" / "scout" / "identity.md").read_text()
        assert "Reflection" in identity_text


class TestStateResumeability:
    """Test that state can be saved and resumed."""

    @pytest.mark.asyncio
    async def test_state_saved_after_each_task(self, tmp_path):
        """State should be saved after each task for resumability."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path, phases=[
            {
                "name": "foundation",
                "description": "Basic",
                "gate": {"min_passed": 1, "min_avg_score": 7.0},
                "tasks": [
                    {"id": "t01", "name": "Task 1", "template": "Do thing 1"},
                ],
            },
        ])

        mock_provider = _make_mock_provider(overall_score=8.5)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state = await engine.run()

        # State file should exist
        state_path = project_root / "agents" / "scout" / ".onboarding" / "state.yaml"
        assert state_path.exists()

        # Load it and verify
        loaded = OnboardingState.load(state_path)
        assert loaded.status == "completed"
        assert loaded.phases[0].tasks[0].status == "passed"

    @pytest.mark.asyncio
    async def test_resume_from_saved_state(self, tmp_path):
        """Engine should resume from saved state when resume=True."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path, phases=[
            {
                "name": "foundation",
                "description": "Basic",
                "gate": {"min_passed": 2, "min_avg_score": 7.0},
                "tasks": [
                    {"id": "t01", "name": "Task 1", "template": "Do thing 1"},
                    {"id": "t02", "name": "Task 2", "template": "Do thing 2"},
                ],
            },
        ])

        # Create a saved state where t01 is already passed
        state_dir = project_root / "agents" / "scout" / ".onboarding"
        state_dir.mkdir(parents=True, exist_ok=True)
        state = OnboardingState(
            agent="scout",
            curriculum="test-curriculum",
            status="in_progress",
            seed=42,
            traits={"style": "methodical"},
            phases=[
                {
                    "name": "foundation",
                    "status": "in_progress",
                    "tasks": [
                        {"id": "t01", "status": "passed", "attempts": 1, "max_retries": 1, "scores": [8.5]},
                        {"id": "t02", "status": "pending", "attempts": 0, "max_retries": 1},
                    ],
                },
            ],
            current_phase=0,
            current_task=1,
        )
        # Use raw YAML save since the phases are dicts here
        state_data = {
            "agent": "scout",
            "curriculum": "test-curriculum",
            "status": "in_progress",
            "seed": 42,
            "traits": {"style": "methodical"},
            "current_phase": 0,
            "current_task": 1,
            "phases": [
                {
                    "name": "foundation",
                    "status": "in_progress",
                    "tasks": [
                        {"id": "t01", "status": "passed", "attempts": 1, "max_retries": 1, "scores": [8.5]},
                        {"id": "t02", "status": "pending", "attempts": 0, "max_retries": 1},
                    ],
                },
            ],
        }
        (state_dir / "state.yaml").write_text(
            yaml.dump(state_data, default_flow_style=False, sort_keys=False)
        )

        mock_provider = _make_mock_provider(overall_score=8.0)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
            resume=True,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            result_state = await engine.run()

        assert result_state.status == "completed"
        assert result_state.phases[0].tasks[0].status == "passed"
        assert result_state.phases[0].tasks[1].status == "passed"


class TestPersonalityTraits:
    """Test personality trait injection."""

    @pytest.mark.asyncio
    async def test_traits_injected_into_identity(self, tmp_path):
        """Personality traits should be written to identity.md."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)

        mock_provider = _make_mock_provider(overall_score=8.5)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state = await engine.run()

        identity = (project_root / "agents" / "scout" / "identity.md").read_text()
        assert "Personality Traits" in identity
        assert state.traits  # Should have selected traits

    @pytest.mark.asyncio
    async def test_seed_produces_deterministic_traits(self, tmp_path):
        """Same seed should produce same traits."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)

        mock_provider = _make_mock_provider(overall_score=8.5)

        # First run
        engine1 = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state1 = await engine1.run()

        # Reset agent files for second run
        (project_root / "agents" / "scout" / "identity.md").write_text("# scout\n\n## Role\nresearcher\n")
        (project_root / "agents" / "scout" / "memory.md").write_text("# Memory -- scout\n")
        import shutil
        onboarding_dir = project_root / "agents" / "scout" / ".onboarding"
        if onboarding_dir.exists():
            shutil.rmtree(onboarding_dir)

        mock_provider2 = _make_mock_provider(overall_score=8.5)

        engine2 = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider2):
            state2 = await engine2.run()

        assert state1.traits == state2.traits


class TestMemoryUpdates:
    """Test that memory.md is updated during onboarding."""

    @pytest.mark.asyncio
    async def test_memory_updated_with_task_learnings(self, tmp_path):
        """Memory.md should be updated when tasks specify writes_to."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path, phases=[
            {
                "name": "foundation",
                "description": "Basic",
                "gate": {"min_passed": 1, "min_avg_score": 7.0},
                "tasks": [
                    {
                        "id": "t01",
                        "name": "Learning task",
                        "template": "Learn something",
                        "writes_to": "memory",
                    },
                ],
            },
        ])

        mock_provider = _make_mock_provider(overall_score=8.5)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            state = await engine.run()

        memory = (project_root / "agents" / "scout" / "memory.md").read_text()
        assert "Learning task" in memory


class TestEvents:
    """Test that events are emitted correctly."""

    @pytest.mark.asyncio
    async def test_onboard_started_event(self, tmp_path):
        """ONBOARD_STARTED event should be emitted."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)

        mock_provider = _make_mock_provider(overall_score=8.5)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            await engine.run()

        spine = EventSpine(project_root)
        events = spine.read_all()
        event_types = [e.type for e in events]
        assert ONBOARD_STARTED in event_types

    @pytest.mark.asyncio
    async def test_all_event_types_emitted_on_success(self, tmp_path):
        """All expected event types should be emitted on successful onboarding."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)

        mock_provider = _make_mock_provider(overall_score=8.5)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            await engine.run()

        spine = EventSpine(project_root)
        events = spine.read_all()
        event_types = set(e.type for e in events)

        assert ONBOARD_STARTED in event_types
        assert ONBOARD_PHASE_STARTED in event_types
        assert TASK_STARTED in event_types
        assert TASK_COMPLETED in event_types
        assert EVAL_STARTED in event_types
        assert EVAL_COMPLETED in event_types
        assert ONBOARD_TASK_COMPLETED in event_types
        assert ONBOARD_PHASE_COMPLETED in event_types
        assert ONBOARD_COMPLETED in event_types

    @pytest.mark.asyncio
    async def test_task_failed_event_on_failure(self, tmp_path):
        """ONBOARD_TASK_FAILED event should be emitted when a task fails."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path, eval_threshold=7.0, max_retries=0, phases=[
            {
                "name": "foundation",
                "description": "Basic",
                "gate": {"min_passed": 1, "min_avg_score": 7.0},
                "tasks": [
                    {"id": "t01", "name": "Test task", "template": "Do thing"},
                ],
            },
        ])

        mock_provider = _make_mock_provider(overall_score=3.0)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            await engine.run()

        spine = EventSpine(project_root)
        events = spine.read_all()
        event_types = [e.type for e in events]
        assert ONBOARD_TASK_FAILED in event_types

    @pytest.mark.asyncio
    async def test_onboard_completed_event_data(self, tmp_path):
        """ONBOARD_COMPLETED event should contain correct status."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)

        mock_provider = _make_mock_provider(overall_score=8.5)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            await engine.run()

        spine = EventSpine(project_root)
        completed_events = spine.read_by_type(ONBOARD_COMPLETED)
        assert len(completed_events) == 1
        assert completed_events[0].data["status"] == "completed"
        assert completed_events[0].agent == "scout"


class TestGraduationSummary:
    """Test that graduation summary is written correctly."""

    @pytest.mark.asyncio
    async def test_graduation_written_to_identity(self, tmp_path):
        """Graduation summary should be written to identity.md."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)

        mock_provider = _make_mock_provider(overall_score=8.5)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            await engine.run()

        identity = (project_root / "agents" / "scout" / "identity.md").read_text()
        assert "Graduation" in identity

    @pytest.mark.asyncio
    async def test_graduation_written_to_memory(self, tmp_path):
        """Graduation summary should be written to memory.md."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)

        mock_provider = _make_mock_provider(overall_score=8.5)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            await engine.run()

        memory = (project_root / "agents" / "scout" / "memory.md").read_text()
        assert "Graduation" in memory


class TestOutputFiles:
    """Test that output files are created correctly."""

    @pytest.mark.asyncio
    async def test_output_file_created(self, tmp_path):
        """Output files should be created for each task attempt."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)

        mock_provider = _make_mock_provider(overall_score=8.5)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            await engine.run()

        output_dir = project_root / "agents" / "scout" / "output"
        output_files = list(output_dir.glob("onboard-*.md"))
        assert len(output_files) >= 1

    @pytest.mark.asyncio
    async def test_output_file_format(self, tmp_path):
        """Output files should have # Task and # Response sections."""
        project_root = _make_project(tmp_path)
        _make_simple_curriculum(tmp_path)

        mock_provider = _make_mock_provider(overall_score=8.5)

        engine = OnboardingEngine(
            project_root=project_root,
            agent_name="scout",
            curriculum_name="test-curriculum",
            seed=42,
        )

        with patch("claws.onboarding.engine.get_provider", return_value=mock_provider):
            await engine.run()

        output_dir = project_root / "agents" / "scout" / "output"
        output_files = list(output_dir.glob("onboard-*.md"))
        content = output_files[0].read_text()
        assert "# Task" in content
        assert "# Response" in content
