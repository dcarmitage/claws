"""claws curriculum — list, show, and create curricula."""

from __future__ import annotations

from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table

from claws.config import find_project_root
from claws.onboarding.curriculum_loader import load_curriculum, list_curricula

console = Console()

PACKAGE_CURRICULA = Path(__file__).parent.parent / "templates" / "curricula"


def _get_search_paths(project_root: Path | None = None) -> list[Path]:
    """Build curriculum search paths: project-local first, then package."""
    paths = []
    if project_root:
        paths.append(project_root / "curricula")
    paths.append(PACKAGE_CURRICULA)
    return paths


@click.group()
def curriculum():
    """List, show, and create curricula."""


@curriculum.command("list")
def list_cmd():
    """List available curricula."""
    project_root = find_project_root()
    search_paths = _get_search_paths(project_root)

    names = list_curricula(search_paths)

    if not names:
        console.print("No curricula found.")
        console.print("Create one with: [bold]claws curriculum create <name>[/]")
        return

    table = Table(title="Available Curricula")
    table.add_column("Name", style="bold")
    table.add_column("Source")
    table.add_column("Description")

    for name in names:
        # Determine source
        if project_root and (project_root / "curricula" / f"{name}.yaml").exists():
            source = "project"
        else:
            source = "built-in"

        # Try loading for description
        try:
            curr = load_curriculum(name, search_paths)
            desc = curr.description[:60] + "..." if len(curr.description) > 60 else curr.description
        except Exception:
            desc = "[dim]error loading[/]"

        table.add_row(name, source, desc)

    console.print(table)


@curriculum.command()
@click.argument("name")
def show(name: str):
    """Display details of a curriculum."""
    project_root = find_project_root()
    search_paths = _get_search_paths(project_root)

    try:
        curr = load_curriculum(name, search_paths)
    except FileNotFoundError:
        console.print(f"[red]Error:[/] Curriculum '{name}' not found.")
        raise SystemExit(1)

    console.print()
    console.print(f"[bold]{curr.name}[/] v{curr.version}")
    if curr.description:
        console.print(f"[dim]{curr.description}[/]")
    if curr.target_role:
        console.print(f"Target role: {curr.target_role}")
    if curr.extends:
        console.print(f"Extends: {curr.extends}")

    # Defaults
    console.print()
    console.print("[bold]Defaults:[/]")
    for key, value in curr.defaults.items():
        console.print(f"  {key}: {value}")

    # Phases
    for phase in curr.phases:
        console.print()
        table = Table(title=f"Phase: {phase.name}")
        table.add_column("ID", style="bold")
        table.add_column("Task")
        table.add_column("Pool")
        table.add_column("Focus")
        table.add_column("Writes To")

        for task in phase.tasks:
            table.add_row(
                task.id,
                task.name,
                task.scenario_pool or "-",
                task.eval_focus or "-",
                task.writes_to or "-",
            )

        console.print(table)
        console.print(
            f"  Gate: min_passed={phase.gate.min_passed}, "
            f"min_avg_score={phase.gate.min_avg_score}"
        )

    # Personality traits
    if curr.personality and curr.personality.traits:
        console.print()
        console.print("[bold]Personality Trait Pools:[/]")
        for category, pool in curr.personality.traits.items():
            label = category.replace("_", " ").title()
            console.print(f"  {label} (pick {pool.pick}):")
            for trait in pool.pool:
                short = trait.split(" — ")[0] if " — " in trait else trait
                console.print(f"    - {short}")

    # Reflections
    if curr.personality and curr.personality.reflections:
        console.print()
        console.print("[bold]Reflections:[/]")
        for ref in curr.personality.reflections:
            console.print(f"  Phase '{ref.phase}' after task {ref.after_task}")


@curriculum.command()
@click.argument("name")
def create(name: str):
    """Scaffold a new curriculum YAML file in curricula/."""
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project. Run 'claws init' first.")
        raise SystemExit(1)

    curricula_dir = project_root / "curricula"
    curricula_dir.mkdir(exist_ok=True)

    output_path = curricula_dir / f"{name}.yaml"
    if output_path.exists():
        console.print(f"[red]Error:[/] Curriculum '{name}' already exists at {output_path}.")
        raise SystemExit(1)

    template = {
        "name": name,
        "version": 1,
        "description": f"Custom curriculum: {name}",
        "target_role": None,
        "defaults": {
            "eval_threshold": 8.0,
            "max_retries": 2,
            "retry_strategy": "reflect",
        },
        "personality": {
            "temperature_offset": 0.15,
            "traits": {
                "cognitive_style": {
                    "pick": 1,
                    "pool": [
                        "methodical -- works through problems step by step",
                        "intuitive -- jumps to patterns quickly",
                    ],
                },
            },
            "reflections": [],
        },
        "phases": [
            {
                "name": "foundation",
                "description": "Core skills for this curriculum.",
                "gate": {
                    "min_passed": 1,
                    "min_avg_score": 7.5,
                },
                "tasks": [
                    {
                        "id": "t01",
                        "name": "First task",
                        "template": "Complete the following: {scenario}",
                        "scenario_pool": None,
                        "eval_focus": "overall quality",
                    },
                ],
            },
        ],
    }

    with open(output_path, "w") as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False)

    console.print(f"[green]Created curriculum:[/] {output_path.relative_to(project_root)}")
    console.print("Edit the file to define your phases, tasks, and personality traits.")
