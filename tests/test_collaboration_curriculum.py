"""Tests for the collaboration curriculum."""

import pytest
from pathlib import Path

from claws.onboarding.curriculum_loader import (
    load_curriculum,
    list_curricula,
    CurriculumDef,
)


BUILTIN_CURRICULA = Path(__file__).parent.parent / "src" / "claws" / "templates" / "curricula"


class TestCollaborationCurriculumLoads:
    def test_loads_without_error(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        assert curriculum.name == "collaboration"

    def test_has_description(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        assert "collaboration" in curriculum.description.lower()

    def test_extends_default(self):
        """After resolution, extends should be None (resolved)."""
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        assert curriculum.extends is None

    def test_version(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        assert curriculum.version == 1


class TestCollaborationPhases:
    def test_has_expected_phases(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        phase_names = [p.name for p in curriculum.phases]
        assert "foundation" in phase_names
        assert "working_memory" in phase_names
        assert "collaboration" in phase_names
        assert "capstone" in phase_names

    def test_inherits_foundation_from_default(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        foundation = next(p for p in curriculum.phases if p.name == "foundation")
        task_ids = [t.id for t in foundation.tasks]
        assert "f01" in task_ids  # inherited from default
        assert "f02" in task_ids

    def test_working_memory_phase_tasks(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        wm = next(p for p in curriculum.phases if p.name == "working_memory")
        assert len(wm.tasks) == 4
        task_ids = [t.id for t in wm.tasks]
        assert "wm01" in task_ids
        assert "wm02" in task_ids
        assert "wm03" in task_ids
        assert "wm04" in task_ids

    def test_working_memory_gate(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        wm = next(p for p in curriculum.phases if p.name == "working_memory")
        assert wm.gate.min_passed == 3
        assert wm.gate.min_avg_score == 7.5

    def test_collaboration_phase_tasks(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        collab = next(p for p in curriculum.phases if p.name == "collaboration")
        assert len(collab.tasks) == 4
        task_ids = [t.id for t in collab.tasks]
        assert "co01" in task_ids
        assert "co02" in task_ids
        assert "co03" in task_ids
        assert "co04" in task_ids

    def test_collaboration_gate(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        collab = next(p for p in curriculum.phases if p.name == "collaboration")
        assert collab.gate.min_passed == 3

    def test_inherits_capstone_from_default(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        capstone = next(p for p in curriculum.phases if p.name == "capstone")
        assert len(capstone.tasks) >= 1
        assert capstone.tasks[0].id == "c01"

    def test_phase_order(self):
        """Phases should be ordered: foundation, working_memory, domain, collaboration, capstone."""
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        phase_names = [p.name for p in curriculum.phases]
        # foundation inherited first, then domain (from default), then new phases appended
        assert phase_names.index("foundation") < phase_names.index("capstone")


class TestCollaborationPersonality:
    def test_has_personality(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        assert curriculum.personality is not None

    def test_has_collaboration_style_trait(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        assert "collaboration_style" in curriculum.personality.traits

    def test_has_trust_calibration_trait(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        assert "trust_calibration" in curriculum.personality.traits

    def test_collaboration_style_pool(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        pool = curriculum.personality.traits["collaboration_style"]
        assert pool.pick == 1
        assert len(pool.pool) == 3

    def test_trust_calibration_pool(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        pool = curriculum.personality.traits["trust_calibration"]
        assert pool.pick == 1
        assert len(pool.pool) == 3

    def test_has_reflections(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        assert len(curriculum.personality.reflections) >= 4
        phases_with_reflections = [r.phase for r in curriculum.personality.reflections]
        assert "working_memory" in phases_with_reflections
        assert "collaboration" in phases_with_reflections


class TestCollaborationTaskContent:
    def test_working_memory_tasks_have_templates(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        wm = next(p for p in curriculum.phases if p.name == "working_memory")
        for task in wm.tasks:
            assert task.template, f"Task {task.id} has no template"
            assert len(task.template) > 50, f"Task {task.id} template too short"

    def test_collaboration_tasks_have_templates(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        collab = next(p for p in curriculum.phases if p.name == "collaboration")
        for task in collab.tasks:
            assert task.template, f"Task {task.id} has no template"
            assert len(task.template) > 50, f"Task {task.id} template too short"

    def test_tasks_have_eval_focus(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        for phase in curriculum.phases:
            for task in phase.tasks:
                assert task.eval_focus, f"Task {task.id} missing eval_focus"

    def test_scenario_pools_reference_existing_files(self):
        """Tasks with scenario_pool should reference pools that exist."""
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        pools_dir = BUILTIN_CURRICULA / "pools"
        for phase in curriculum.phases:
            for task in phase.tasks:
                if task.scenario_pool and not task.scenario_pool.startswith("{"):
                    pool_file = pools_dir / f"{task.scenario_pool}.yaml"
                    assert pool_file.exists(), (
                        f"Task {task.id} references pool '{task.scenario_pool}' "
                        f"but {pool_file} does not exist"
                    )


class TestCollaborationDefaults:
    def test_eval_threshold(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        assert curriculum.defaults["eval_threshold"] == 8.0

    def test_max_retries(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        assert curriculum.defaults["max_retries"] == 2

    def test_retry_strategy(self):
        curriculum = load_curriculum("collaboration", [BUILTIN_CURRICULA])
        assert curriculum.defaults["retry_strategy"] == "reflect"


class TestCollaborationInListing:
    def test_listed_in_curricula(self):
        curricula = list_curricula([BUILTIN_CURRICULA])
        assert "collaboration" in curricula

    def test_default_still_listed(self):
        curricula = list_curricula([BUILTIN_CURRICULA])
        assert "default" in curricula
