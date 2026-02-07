"""Personality system — trait selection and reflection handling.

Selects personality traits from pools (optionally with a seed for
determinism) and checks when reflection prompts should fire.
"""

from __future__ import annotations

import random

from claws.onboarding.curriculum_loader import PersonalityDef


def select_traits(
    personality: PersonalityDef, seed: int | None = None
) -> dict[str, str]:
    """Select traits from each category's pool.

    For each trait category, randomly picks `pool.pick` items.
    If seed is provided, uses random.Random(seed) for determinism.
    When pick is 1, the value is a single string; otherwise a
    comma-separated string of selected traits.

    Returns a dict mapping category name to selected trait string.
    """
    rng = random.Random(seed) if seed is not None else random.Random()

    traits: dict[str, str] = {}
    for category, pool in personality.traits.items():
        if not pool.pool:
            continue
        k = min(pool.pick, len(pool.pool))
        selected = rng.sample(pool.pool, k)
        traits[category] = selected[0] if k == 1 else ", ".join(selected)

    return traits


def format_traits_for_identity(traits: dict[str, str]) -> str:
    """Render selected traits as markdown for injection into identity.md.

    Produces a section like:
    ## Personality Traits
    - **cognitive_style:** methodical — works through problems step by step
    - **communication:** concise — says exactly what is needed
    """
    if not traits:
        return ""

    lines = ["## Personality Traits"]
    for category, trait in traits.items():
        label = category.replace("_", " ").title()
        lines.append(f"- **{label}:** {trait}")

    return "\n".join(lines) + "\n"


def get_reflection_prompt(
    personality: PersonalityDef,
    phase: str,
    tasks_completed: int,
) -> str | None:
    """Check if a reflection prompt should fire.

    Returns the prompt text if a reflection is configured for the
    given phase and tasks_completed count, otherwise None.
    """
    for reflection in personality.reflections:
        if reflection.phase == phase and reflection.after_task == tasks_completed:
            return reflection.prompt
    return None
