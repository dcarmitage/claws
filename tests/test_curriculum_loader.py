"""Tests for claws.onboarding.curriculum_loader — YAML parsing, inheritance, listing."""

import pytest
import yaml
from pathlib import Path

from claws.onboarding.curriculum_loader import (
    CurriculumDef,
    PhaseDef,
    TaskDef,
    GateDef,
    TraitPool,
    PersonalityDef,
    ReflectionDef,
    CircularInheritanceError,
    load_curriculum,
    resolve_inheritance,
    list_curricula,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_curriculum_yaml(name="test", extends=None, phases=None, personality=None):
    """Build a minimal valid curriculum dict for YAML serialization."""
    data = {
        "name": name,
        "version": 1,
        "description": f"{name} curriculum",
        "defaults": {
            "eval_threshold": 8.0,
            "max_retries": 2,
            "retry_strategy": "reflect",
        },
    }
    if extends:
        data["extends"] = extends
    if personality:
        data["personality"] = personality
    if phases is None:
        phases = [
            {
                "name": "foundation",
                "description": "Foundation phase",
                "gate": {"min_passed": 1, "min_avg_score": 7.0},
                "tasks": [
                    {
                        "id": "f01",
                        "name": "Self-intro",
                        "template": "Introduce yourself as {agent_name}.",
                        "eval_focus": "authenticity",
                        "writes_to": "identity",
                    },
                ],
            },
        ]
    data["phases"] = phases
    return data


def _write_curriculum(base_dir: Path, name: str, data: dict):
    """Write a curriculum YAML file to the given directory."""
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"{name}.yaml"
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return path


# ---------------------------------------------------------------------------
# YAML Parsing
# ---------------------------------------------------------------------------

class TestYAMLParsing:
    def test_load_minimal_curriculum(self, tmp_path):
        """Minimal YAML should parse into a valid CurriculumDef."""
        data = _minimal_curriculum_yaml("basic")
        _write_curriculum(tmp_path, "basic", data)

        result = load_curriculum("basic", [tmp_path])

        assert result.name == "basic"
        assert result.version == 1
        assert result.description == "basic curriculum"
        assert len(result.phases) == 1
        assert result.phases[0].name == "foundation"
        assert len(result.phases[0].tasks) == 1
        assert result.phases[0].tasks[0].id == "f01"

    def test_task_fields_parsed(self, tmp_path):
        """All task fields should be parsed correctly."""
        data = _minimal_curriculum_yaml("fields")
        data["phases"][0]["tasks"][0]["scenario_pool"] = "test_pool"
        data["phases"][0]["tasks"][0]["eval_focus"] = "accuracy"
        data["phases"][0]["tasks"][0]["writes_to"] = "memory"
        _write_curriculum(tmp_path, "fields", data)

        result = load_curriculum("fields", [tmp_path])
        task = result.phases[0].tasks[0]

        assert task.scenario_pool == "test_pool"
        assert task.eval_focus == "accuracy"
        assert task.writes_to == "memory"

    def test_gate_defaults(self, tmp_path):
        """Gate min_avg_score should default to 7.5 if not specified."""
        data = _minimal_curriculum_yaml("gate-test")
        data["phases"][0]["gate"] = {"min_passed": 2}
        _write_curriculum(tmp_path, "gate-test", data)

        result = load_curriculum("gate-test", [tmp_path])
        assert result.phases[0].gate.min_avg_score == 7.5

    def test_gate_custom_score(self, tmp_path):
        """Gate min_avg_score should use the specified value."""
        data = _minimal_curriculum_yaml("gate-custom")
        data["phases"][0]["gate"] = {"min_passed": 1, "min_avg_score": 9.0}
        _write_curriculum(tmp_path, "gate-custom", data)

        result = load_curriculum("gate-custom", [tmp_path])
        assert result.phases[0].gate.min_avg_score == 9.0

    def test_personality_parsed(self, tmp_path):
        """Personality with traits and reflections should parse correctly."""
        personality = {
            "temperature_offset": 0.2,
            "seed": 42,
            "traits": {
                "style": {
                    "pick": 1,
                    "pool": ["methodical", "intuitive"],
                },
            },
            "reflections": [
                {
                    "phase": "foundation",
                    "after_task": 2,
                    "prompt": "Reflect on your work.",
                },
            ],
        }
        data = _minimal_curriculum_yaml("personality-test", personality=personality)
        _write_curriculum(tmp_path, "personality-test", data)

        result = load_curriculum("personality-test", [tmp_path])
        assert result.personality is not None
        assert result.personality.temperature_offset == 0.2
        assert result.personality.seed == 42
        assert "style" in result.personality.traits
        assert result.personality.traits["style"].pick == 1
        assert len(result.personality.traits["style"].pool) == 2
        assert len(result.personality.reflections) == 1
        assert result.personality.reflections[0].phase == "foundation"

    def test_multiple_phases(self, tmp_path):
        """Multiple phases should all be parsed in order."""
        phases = [
            {
                "name": "foundation",
                "description": "Phase 1",
                "gate": {"min_passed": 1},
                "tasks": [{"id": "f01", "name": "Task 1", "template": "Do thing 1."}],
            },
            {
                "name": "domain",
                "description": "Phase 2",
                "gate": {"min_passed": 2, "min_avg_score": 8.0},
                "tasks": [
                    {"id": "d01", "name": "Task 2", "template": "Do thing 2."},
                    {"id": "d02", "name": "Task 3", "template": "Do thing 3."},
                ],
            },
        ]
        data = _minimal_curriculum_yaml("multi-phase", phases=phases)
        _write_curriculum(tmp_path, "multi-phase", data)

        result = load_curriculum("multi-phase", [tmp_path])
        assert len(result.phases) == 2
        assert result.phases[0].name == "foundation"
        assert result.phases[1].name == "domain"
        assert len(result.phases[1].tasks) == 2

    def test_defaults_parsed(self, tmp_path):
        """Curriculum defaults should be parsed correctly."""
        data = _minimal_curriculum_yaml("defaults-test")
        data["defaults"]["eval_threshold"] = 9.5
        data["defaults"]["max_retries"] = 5
        _write_curriculum(tmp_path, "defaults-test", data)

        result = load_curriculum("defaults-test", [tmp_path])
        assert result.defaults["eval_threshold"] == 9.5
        assert result.defaults["max_retries"] == 5

    def test_missing_curriculum_raises(self, tmp_path):
        """Loading a nonexistent curriculum should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_curriculum("nonexistent", [tmp_path])


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------

class TestInheritance:
    def test_child_overrides_phase_by_name(self, tmp_path):
        """Child phase with same name should replace parent phase."""
        parent_data = _minimal_curriculum_yaml("parent")
        _write_curriculum(tmp_path, "parent", parent_data)

        child_phases = [
            {
                "name": "foundation",
                "description": "Overridden foundation",
                "gate": {"min_passed": 2, "min_avg_score": 8.5},
                "tasks": [
                    {"id": "f01", "name": "New task", "template": "New template."},
                    {"id": "f02", "name": "Extra task", "template": "Extra template."},
                ],
            },
        ]
        child_data = _minimal_curriculum_yaml("child", extends="parent", phases=child_phases)
        _write_curriculum(tmp_path, "child", child_data)

        result = load_curriculum("child", [tmp_path])
        assert len(result.phases) == 1
        assert result.phases[0].name == "foundation"
        assert result.phases[0].description == "Overridden foundation"
        assert len(result.phases[0].tasks) == 2
        assert result.phases[0].gate.min_avg_score == 8.5

    def test_parent_phases_preserved_if_not_overridden(self, tmp_path):
        """Parent phases not overridden by child should be kept."""
        parent_phases = [
            {
                "name": "foundation",
                "description": "Parent foundation",
                "gate": {"min_passed": 1},
                "tasks": [{"id": "f01", "name": "T1", "template": "T1."}],
            },
            {
                "name": "domain",
                "description": "Parent domain",
                "gate": {"min_passed": 1},
                "tasks": [{"id": "d01", "name": "T2", "template": "T2."}],
            },
        ]
        parent_data = _minimal_curriculum_yaml("parent", phases=parent_phases)
        _write_curriculum(tmp_path, "parent", parent_data)

        # Child only overrides foundation, domain comes from parent
        child_phases = [
            {
                "name": "foundation",
                "description": "Child foundation",
                "gate": {"min_passed": 2},
                "tasks": [{"id": "f01", "name": "New", "template": "New."}],
            },
        ]
        child_data = _minimal_curriculum_yaml("child", extends="parent", phases=child_phases)
        _write_curriculum(tmp_path, "child", child_data)

        result = load_curriculum("child", [tmp_path])
        assert len(result.phases) == 2
        assert result.phases[0].name == "foundation"
        assert result.phases[0].description == "Child foundation"
        assert result.phases[1].name == "domain"
        assert result.phases[1].description == "Parent domain"

    def test_child_adds_new_phases(self, tmp_path):
        """Child phases not in parent should be appended."""
        parent_data = _minimal_curriculum_yaml("parent")
        _write_curriculum(tmp_path, "parent", parent_data)

        child_phases = [
            {
                "name": "capstone",
                "description": "New capstone",
                "gate": {"min_passed": 1},
                "tasks": [{"id": "c01", "name": "Cap", "template": "Cap."}],
            },
        ]
        child_data = _minimal_curriculum_yaml("child", extends="parent", phases=child_phases)
        _write_curriculum(tmp_path, "child", child_data)

        result = load_curriculum("child", [tmp_path])
        assert len(result.phases) == 2
        assert result.phases[0].name == "foundation"  # from parent
        assert result.phases[1].name == "capstone"  # from child

    def test_personality_replaced_if_child_defines_it(self, tmp_path):
        """Child personality should fully replace parent personality."""
        parent_personality = {
            "traits": {"style": {"pick": 1, "pool": ["a", "b"]}},
            "reflections": [],
        }
        parent_data = _minimal_curriculum_yaml("parent", personality=parent_personality)
        _write_curriculum(tmp_path, "parent", parent_data)

        child_personality = {
            "traits": {"tone": {"pick": 1, "pool": ["x", "y", "z"]}},
            "reflections": [{"phase": "foundation", "after_task": 1, "prompt": "Reflect."}],
        }
        child_data = _minimal_curriculum_yaml("child", extends="parent", personality=child_personality)
        _write_curriculum(tmp_path, "child", child_data)

        result = load_curriculum("child", [tmp_path])
        assert result.personality is not None
        assert "tone" in result.personality.traits
        assert "style" not in result.personality.traits
        assert len(result.personality.reflections) == 1

    def test_parent_personality_used_if_child_omits(self, tmp_path):
        """If child does not define personality, parent's should be used."""
        parent_personality = {
            "traits": {"style": {"pick": 1, "pool": ["a", "b"]}},
            "reflections": [],
        }
        parent_data = _minimal_curriculum_yaml("parent", personality=parent_personality)
        _write_curriculum(tmp_path, "parent", parent_data)

        child_data = _minimal_curriculum_yaml("child", extends="parent")
        _write_curriculum(tmp_path, "child", child_data)

        result = load_curriculum("child", [tmp_path])
        assert result.personality is not None
        assert "style" in result.personality.traits

    def test_missing_parent_raises(self, tmp_path):
        """Extending a nonexistent parent should raise FileNotFoundError."""
        child_data = _minimal_curriculum_yaml("orphan", extends="nonexistent")
        _write_curriculum(tmp_path, "orphan", child_data)

        with pytest.raises(FileNotFoundError, match="nonexistent"):
            load_curriculum("orphan", [tmp_path])

    def test_circular_inheritance_detected(self, tmp_path):
        """Circular inheritance should raise CircularInheritanceError."""
        a_data = _minimal_curriculum_yaml("a", extends="b")
        b_data = _minimal_curriculum_yaml("b", extends="a")
        _write_curriculum(tmp_path, "a", a_data)
        _write_curriculum(tmp_path, "b", b_data)

        with pytest.raises(CircularInheritanceError):
            load_curriculum("a", [tmp_path])

    def test_self_referencing_inheritance_detected(self, tmp_path):
        """A curriculum extending itself should raise CircularInheritanceError."""
        data = _minimal_curriculum_yaml("self-ref", extends="self-ref")
        _write_curriculum(tmp_path, "self-ref", data)

        with pytest.raises(CircularInheritanceError):
            load_curriculum("self-ref", [tmp_path])

    def test_child_description_overrides_parent(self, tmp_path):
        """Child description should override parent's if provided."""
        parent_data = _minimal_curriculum_yaml("parent")
        parent_data["description"] = "Parent description"
        _write_curriculum(tmp_path, "parent", parent_data)

        child_data = _minimal_curriculum_yaml("child", extends="parent")
        child_data["description"] = "Child description"
        _write_curriculum(tmp_path, "child", child_data)

        result = load_curriculum("child", [tmp_path])
        assert result.description == "Child description"

    def test_child_inherits_parent_description_if_empty(self, tmp_path):
        """Child with empty description should use parent's."""
        parent_data = _minimal_curriculum_yaml("parent")
        parent_data["description"] = "Inherited desc"
        _write_curriculum(tmp_path, "parent", parent_data)

        child_data = _minimal_curriculum_yaml("child", extends="parent")
        child_data["description"] = ""
        _write_curriculum(tmp_path, "child", child_data)

        result = load_curriculum("child", [tmp_path])
        assert result.description == "Inherited desc"


# ---------------------------------------------------------------------------
# resolve_inheritance (unit tests on the function directly)
# ---------------------------------------------------------------------------

class TestResolveInheritance:
    def test_merge_defaults(self):
        """Child defaults should override parent defaults per-key."""
        parent = CurriculumDef(
            name="parent",
            defaults={"eval_threshold": 8.0, "max_retries": 2, "retry_strategy": "reflect"},
        )
        child = CurriculumDef(
            name="child",
            extends="parent",
            defaults={"eval_threshold": 9.0, "max_retries": 2, "retry_strategy": "reflect"},
        )
        result = resolve_inheritance(child, parent)
        assert result.defaults["eval_threshold"] == 9.0
        assert result.defaults["max_retries"] == 2

    def test_extends_cleared_after_resolve(self):
        """After resolution, extends should be None."""
        parent = CurriculumDef(name="parent")
        child = CurriculumDef(name="child", extends="parent")
        result = resolve_inheritance(child, parent)
        assert result.extends is None


# ---------------------------------------------------------------------------
# list_curricula
# ---------------------------------------------------------------------------

class TestListCurricula:
    def test_lists_yaml_files(self, tmp_path):
        """Should find all .yaml files and return their stems."""
        (tmp_path / "alpha.yaml").write_text("name: alpha\n")
        (tmp_path / "beta.yaml").write_text("name: beta\n")
        (tmp_path / "not-yaml.txt").write_text("ignored\n")

        result = list_curricula([tmp_path])
        assert "alpha" in result
        assert "beta" in result
        assert "not-yaml" not in result

    def test_deduplicates_across_paths(self, tmp_path):
        """Same name in multiple paths should appear only once."""
        dir1 = tmp_path / "local"
        dir2 = tmp_path / "global"
        dir1.mkdir()
        dir2.mkdir()
        (dir1 / "default.yaml").write_text("name: default\n")
        (dir2 / "default.yaml").write_text("name: default\n")

        result = list_curricula([dir1, dir2])
        assert result.count("default") == 1

    def test_project_local_first(self, tmp_path):
        """Project-local curricula should be listed before package ones."""
        local = tmp_path / "local"
        package = tmp_path / "package"
        local.mkdir()
        package.mkdir()
        (local / "custom.yaml").write_text("name: custom\n")
        (package / "default.yaml").write_text("name: default\n")

        result = list_curricula([local, package])
        assert result.index("custom") < result.index("default")

    def test_empty_search_paths(self, tmp_path):
        """No search paths should return empty list."""
        result = list_curricula([])
        assert result == []

    def test_nonexistent_directory_skipped(self, tmp_path):
        """Nonexistent directories in search paths should be skipped."""
        missing = tmp_path / "does_not_exist"
        result = list_curricula([missing])
        assert result == []

    def test_search_path_priority(self, tmp_path):
        """First search path should take precedence for dedup."""
        dir1 = tmp_path / "first"
        dir2 = tmp_path / "second"
        dir1.mkdir()
        dir2.mkdir()
        (dir1 / "shared.yaml").write_text("name: shared\nversion: 1\n")
        (dir2 / "shared.yaml").write_text("name: shared\nversion: 2\n")
        (dir2 / "extra.yaml").write_text("name: extra\n")

        result = list_curricula([dir1, dir2])
        assert "shared" in result
        assert "extra" in result
        assert len(result) == 2
