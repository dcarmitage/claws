"""claws agent onboard — run an agent through a curriculum."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click
from rich.console import Console

from claws.config import find_project_root, load_config
from claws.onboarding.engine import OnboardingEngine
from claws.onboarding.state import OnboardingState

console = Console()


@click.command()
@click.argument("name")
@click.option("--curriculum", default="default", help="Curriculum name to use")
@click.option("--resume", is_flag=True, help="Resume interrupted onboarding")
@click.option("--seed", type=int, default=None, help="Random seed for determinism")
@click.option("--force", is_flag=True, help="Re-onboard even if already completed")
def onboard(name: str, curriculum: str, resume: bool, seed: int | None, force: bool):
    """Run an agent through an onboarding curriculum.

    Executes curriculum tasks, evaluates responses, and tracks progress.
    The agent's identity and memory are updated throughout the process.
    """
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project. Run 'claws init' first.")
        raise SystemExit(1)

    agent_dir = project_root / "agents" / name
    if not agent_dir.exists():
        console.print(f"[red]Error:[/] Agent '{name}' not found. Create with: claws agent create {name} --role <role>")
        raise SystemExit(1)

    # Check if already onboarded
    state_path = agent_dir / ".onboarding" / "state.yaml"
    if state_path.exists() and not resume and not force:
        state = OnboardingState.load(state_path)
        if state.status == "completed":
            console.print(f"[yellow]Agent '{name}' has already completed onboarding.[/]")
            console.print("Use --force to re-onboard or --resume to continue.")
            raise SystemExit(1)

    engine = OnboardingEngine(
        project_root=project_root,
        agent_name=name,
        curriculum_name=curriculum,
        seed=seed,
        resume=resume,
    )

    state = asyncio.run(engine.run())

    if state.status != "completed":
        raise SystemExit(1)
