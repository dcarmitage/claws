"""Tests for claws.onboarding.personality — trait selection, formatting, reflections."""

import pytest

from claws.onboarding.curriculum_loader import (
    PersonalityDef,
    TraitPool,
    ReflectionDef,
)
from claws.onboarding.personality import (
    select_traits,
    format_traits_for_identity,
    get_reflection_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_personality(
    traits=None,
    reflections=None,
    seed=None,
    temperature_offset=0.15,
):
    """Build a PersonalityDef for testing."""
    if traits is None:
        traits = {
            "cognitive_style": TraitPool(pick=1, pool=["methodical", "intuitive", "adversarial"]),
            "communication": TraitPool(pick=1, pool=["concise", "thorough", "direct"]),
        }
    if reflections is None:
        reflections = []
    return PersonalityDef(
        traits=traits,
        reflections=reflections,
        temperature_offset=temperature_offset,
        seed=seed,
    )


# ---------------------------------------------------------------------------
# select_traits
# ---------------------------------------------------------------------------

class TestSelectTraits:
    def test_returns_one_per_category(self):
        """With pick=1, should return exactly one trait per category."""
        p = _make_personality()
        traits = select_traits(p, seed=42)

        assert len(traits) == 2
        assert "cognitive_style" in traits
        assert "communication" in traits

    def test_trait_from_pool(self):
        """Selected trait must come from the category's pool."""
        p = _make_personality()
        traits = select_traits(p, seed=42)

        assert traits["cognitive_style"] in ["methodical", "intuitive", "adversarial"]
        assert traits["communication"] in ["concise", "thorough", "direct"]

    def test_deterministic_with_seed(self):
        """Same seed should produce same traits."""
        p = _make_personality()

        traits_a = select_traits(p, seed=123)
        traits_b = select_traits(p, seed=123)

        assert traits_a == traits_b

    def test_different_seeds_can_differ(self):
        """Different seeds should (usually) produce different traits."""
        p = _make_personality()

        # With enough categories and options, different seeds should diverge.
        # Use many seeds to find at least one that differs.
        results = set()
        for seed in range(50):
            traits = select_traits(p, seed=seed)
            results.add(frozenset(traits.items()))

        assert len(results) > 1, "Expected different seeds to produce different traits"

    def test_pick_multiple(self):
        """With pick > 1, should return comma-separated traits."""
        traits_def = {
            "style": TraitPool(pick=2, pool=["a", "b", "c", "d"]),
        }
        p = _make_personality(traits=traits_def)
        traits = select_traits(p, seed=42)

        assert "style" in traits
        parts = traits["style"].split(", ")
        assert len(parts) == 2

    def test_pick_exceeds_pool_size(self):
        """If pick > pool size, should select all available items."""
        traits_def = {
            "tiny": TraitPool(pick=5, pool=["only_one", "only_two"]),
        }
        p = _make_personality(traits=traits_def)
        traits = select_traits(p, seed=42)

        parts = traits["tiny"].split(", ")
        assert len(parts) == 2

    def test_empty_pool_skipped(self):
        """Categories with empty pools should be skipped."""
        traits_def = {
            "empty": TraitPool(pick=1, pool=[]),
            "full": TraitPool(pick=1, pool=["something"]),
        }
        p = _make_personality(traits=traits_def)
        traits = select_traits(p, seed=42)

        assert "empty" not in traits
        assert "full" in traits

    def test_without_seed_still_works(self):
        """Without a seed, selection should still return valid traits."""
        p = _make_personality()
        traits = select_traits(p)

        assert len(traits) == 2
        assert traits["cognitive_style"] in ["methodical", "intuitive", "adversarial"]


# ---------------------------------------------------------------------------
# format_traits_for_identity
# ---------------------------------------------------------------------------

class TestFormatTraitsForIdentity:
    def test_markdown_output(self):
        """Should produce markdown with header and bullet points."""
        traits = {
            "cognitive_style": "methodical — works through problems step by step",
            "communication": "concise — says exactly what is needed",
        }
        result = format_traits_for_identity(traits)

        assert result.startswith("## Personality Traits\n")
        assert "**Cognitive Style:**" in result
        assert "**Communication:**" in result
        assert "methodical" in result
        assert "concise" in result

    def test_empty_traits_returns_empty_string(self):
        """Empty traits dict should return empty string."""
        result = format_traits_for_identity({})
        assert result == ""

    def test_underscores_replaced(self):
        """Underscores in category names should become spaces with title case."""
        traits = {"work_ethic": "efficient"}
        result = format_traits_for_identity(traits)
        assert "Work Ethic" in result

    def test_ends_with_newline(self):
        """Formatted output should end with a newline."""
        traits = {"style": "fast"}
        result = format_traits_for_identity(traits)
        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# get_reflection_prompt
# ---------------------------------------------------------------------------

class TestGetReflectionPrompt:
    def test_matching_reflection_returned(self):
        """Should return prompt when phase and after_task match."""
        reflections = [
            ReflectionDef(phase="foundation", after_task=2, prompt="Reflect on foundation."),
            ReflectionDef(phase="domain", after_task=1, prompt="Reflect on domain."),
        ]
        p = _make_personality(reflections=reflections)

        result = get_reflection_prompt(p, "foundation", 2)
        assert result == "Reflect on foundation."

    def test_no_match_returns_none(self):
        """Should return None when no reflection matches."""
        reflections = [
            ReflectionDef(phase="foundation", after_task=2, prompt="Reflect."),
        ]
        p = _make_personality(reflections=reflections)

        assert get_reflection_prompt(p, "foundation", 1) is None
        assert get_reflection_prompt(p, "domain", 2) is None

    def test_empty_reflections(self):
        """Personality with no reflections should always return None."""
        p = _make_personality(reflections=[])

        assert get_reflection_prompt(p, "foundation", 0) is None
        assert get_reflection_prompt(p, "foundation", 2) is None

    def test_multiple_reflections_first_match(self):
        """If multiple reflections match (unusual), return the first one."""
        reflections = [
            ReflectionDef(phase="foundation", after_task=2, prompt="First match."),
            ReflectionDef(phase="foundation", after_task=2, prompt="Second match."),
        ]
        p = _make_personality(reflections=reflections)

        result = get_reflection_prompt(p, "foundation", 2)
        assert result == "First match."

    def test_after_task_zero(self):
        """Reflection at after_task=0 should fire before any tasks in the phase."""
        reflections = [
            ReflectionDef(phase="capstone", after_task=0, prompt="Pre-capstone reflection."),
        ]
        p = _make_personality(reflections=reflections)

        result = get_reflection_prompt(p, "capstone", 0)
        assert result == "Pre-capstone reflection."
