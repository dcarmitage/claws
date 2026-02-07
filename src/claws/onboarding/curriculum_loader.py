"""Curriculum loader — parse and resolve curriculum YAML files.

Curricula define a sequence of phases, tasks, and evaluation gates
that an agent must complete during onboarding. Supports single
inheritance: a child curriculum can extend a parent, overriding
phases by name and replacing personality definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class GateDef:
    """Phase gate — minimum requirements to pass a phase."""
    min_passed: int
    min_avg_score: float = 7.5


@dataclass
class TaskDef:
    """A single task within a phase."""
    id: str
    name: str
    template: str
    scenario_pool: str | None = None
    eval_focus: str | None = None
    writes_to: str | None = None


@dataclass
class PhaseDef:
    """A phase containing ordered tasks and a gate."""
    name: str
    description: str
    tasks: list[TaskDef]
    gate: GateDef


@dataclass
class TraitPool:
    """A pool of personality traits to sample from."""
    pick: int = 1
    pool: list[str] = field(default_factory=list)


@dataclass
class ReflectionDef:
    """A reflection prompt triggered at a specific point in onboarding."""
    phase: str
    after_task: int
    prompt: str


@dataclass
class PersonalityDef:
    """Personality configuration — trait pools and reflection prompts."""
    traits: dict[str, TraitPool] = field(default_factory=dict)
    reflections: list[ReflectionDef] = field(default_factory=list)
    temperature_offset: float = 0.15
    seed: int | None = None


@dataclass
class CurriculumDef:
    """Full curriculum definition loaded from YAML."""
    name: str
    version: int = 1
    extends: str | None = None
    description: str = ""
    target_role: str | None = None
    defaults: dict = field(default_factory=lambda: {
        "eval_threshold": 8.0,
        "max_retries": 2,
        "retry_strategy": "reflect",
    })
    personality: PersonalityDef | None = None
    phases: list[PhaseDef] = field(default_factory=list)


class CircularInheritanceError(Exception):
    """Raised when curriculum inheritance forms a cycle."""
    pass


def _parse_gate(raw: dict) -> GateDef:
    """Parse a gate definition from raw YAML dict."""
    return GateDef(
        min_passed=raw["min_passed"],
        min_avg_score=raw.get("min_avg_score", 7.5),
    )


def _parse_task(raw: dict) -> TaskDef:
    """Parse a task definition from raw YAML dict."""
    return TaskDef(
        id=raw["id"],
        name=raw["name"],
        template=raw["template"],
        scenario_pool=raw.get("scenario_pool"),
        eval_focus=raw.get("eval_focus"),
        writes_to=raw.get("writes_to"),
    )


def _parse_phase(raw: dict) -> PhaseDef:
    """Parse a phase definition from raw YAML dict."""
    return PhaseDef(
        name=raw["name"],
        description=raw.get("description", ""),
        tasks=[_parse_task(t) for t in raw.get("tasks", [])],
        gate=_parse_gate(raw["gate"]),
    )


def _parse_trait_pool(raw: dict) -> TraitPool:
    """Parse a trait pool from raw YAML dict."""
    return TraitPool(
        pick=raw.get("pick", 1),
        pool=raw.get("pool", []),
    )


def _parse_reflection(raw: dict) -> ReflectionDef:
    """Parse a reflection definition from raw YAML dict."""
    return ReflectionDef(
        phase=raw["phase"],
        after_task=raw["after_task"],
        prompt=raw["prompt"],
    )


def _parse_personality(raw: dict) -> PersonalityDef:
    """Parse a personality definition from raw YAML dict."""
    traits = {}
    for category, pool_raw in raw.get("traits", {}).items():
        traits[category] = _parse_trait_pool(pool_raw)

    reflections = [_parse_reflection(r) for r in raw.get("reflections", [])]

    return PersonalityDef(
        traits=traits,
        reflections=reflections,
        temperature_offset=raw.get("temperature_offset", 0.15),
        seed=raw.get("seed"),
    )


def _parse_curriculum(raw: dict) -> CurriculumDef:
    """Parse a full curriculum from raw YAML dict."""
    defaults_raw = raw.get("defaults", {})
    defaults = {
        "eval_threshold": defaults_raw.get("eval_threshold", 8.0),
        "max_retries": defaults_raw.get("max_retries", 2),
        "retry_strategy": defaults_raw.get("retry_strategy", "reflect"),
    }

    personality = None
    if "personality" in raw:
        personality = _parse_personality(raw["personality"])

    phases = [_parse_phase(p) for p in raw.get("phases", [])]

    return CurriculumDef(
        name=raw["name"],
        version=raw.get("version", 1),
        extends=raw.get("extends"),
        description=raw.get("description", ""),
        target_role=raw.get("target_role"),
        defaults=defaults,
        personality=personality,
        phases=phases,
    )


def _find_curriculum_file(name: str, search_paths: list[Path]) -> Path | None:
    """Find a curriculum YAML file by name in search paths."""
    for base in search_paths:
        candidate = base / f"{name}.yaml"
        if candidate.exists():
            return candidate
    return None


def resolve_inheritance(child: CurriculumDef, parent: CurriculumDef) -> CurriculumDef:
    """Merge child curriculum onto parent.

    Rules:
    - Child phases override parent phases by name.
    - Parent phases not overridden by child are kept.
    - If child defines personality, it fully replaces parent personality.
    - Child defaults override parent defaults per-key.
    - Other scalar fields use child value if set.
    """
    # Merge phases: child overrides parent by name
    parent_phases_by_name = {p.name: p for p in parent.phases}
    child_phase_names = {p.name for p in child.phases}

    merged_phases = []
    # First, include parent phases (in parent order), replacing with child if overridden
    for pp in parent.phases:
        if pp.name in child_phase_names:
            # Find the child override
            for cp in child.phases:
                if cp.name == pp.name:
                    merged_phases.append(cp)
                    break
        else:
            merged_phases.append(pp)

    # Then add any child phases not in parent (new phases, appended at end)
    for cp in child.phases:
        if cp.name not in parent_phases_by_name:
            merged_phases.append(cp)

    # Merge defaults
    merged_defaults = dict(parent.defaults)
    merged_defaults.update(child.defaults)

    # Personality: child fully replaces if defined
    personality = child.personality if child.personality is not None else parent.personality

    return CurriculumDef(
        name=child.name,
        version=child.version,
        extends=None,  # inheritance resolved
        description=child.description or parent.description,
        target_role=child.target_role or parent.target_role,
        defaults=merged_defaults,
        personality=personality,
        phases=merged_phases,
    )


def load_curriculum(name: str, search_paths: list[Path]) -> CurriculumDef:
    """Load a curriculum by name, resolving inheritance.

    Search paths are checked in order: project curricula/ first,
    then package templates/curricula/.

    Raises FileNotFoundError if curriculum is not found.
    Raises CircularInheritanceError if inheritance forms a cycle.
    """
    seen: set[str] = set()
    return _load_with_inheritance(name, search_paths, seen)


def _load_with_inheritance(
    name: str, search_paths: list[Path], seen: set[str]
) -> CurriculumDef:
    """Recursive loader with cycle detection."""
    if name in seen:
        raise CircularInheritanceError(
            f"Circular inheritance detected: {name!r} already in chain {seen}"
        )
    seen.add(name)

    path = _find_curriculum_file(name, search_paths)
    if path is None:
        raise FileNotFoundError(
            f"Curriculum {name!r} not found in search paths: {search_paths}"
        )

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    curriculum = _parse_curriculum(raw)

    if curriculum.extends:
        parent = _load_with_inheritance(curriculum.extends, search_paths, seen)
        curriculum = resolve_inheritance(curriculum, parent)

    return curriculum


def list_curricula(search_paths: list[Path]) -> list[str]:
    """Find all curriculum names across search paths.

    Returns deduplicated list of curriculum names (without .yaml extension),
    with project-local curricula listed first.
    """
    seen: set[str] = set()
    result: list[str] = []

    for base in search_paths:
        if not base.is_dir():
            continue
        for yaml_file in sorted(base.glob("*.yaml")):
            name = yaml_file.stem
            if name not in seen:
                seen.add(name)
                result.append(name)

    return result
