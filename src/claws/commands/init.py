"""claws init — create a new project."""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from claws.events import EventSpine, Event, PROJECT_INITIALIZED

console = Console()
TEMPLATES = Path(__file__).parent.parent / "templates"


@click.command()
@click.argument("project_name")
@click.option("--provider", default="anthropic", help="Default LLM provider type")
@click.option("--model", default=None, help="Default model name")
def init(project_name: str, provider: str, model: str | None):
    """Create a new claws project.

    Sets up the project directory with configuration, agent directory,
    and event spine. Ready for 'claws agent create' and 'claws run'.
    """
    project_dir = Path.cwd() / project_name

    if project_dir.exists():
        console.print(f"[red]Error:[/] Directory '{project_name}' already exists.")
        raise SystemExit(1)

    # Resolve default model for provider
    if model is None:
        model = _default_model(provider)

    console.print()
    console.print(f"[bold]Creating project:[/] {project_name}")
    console.print()

    # Create directories
    project_dir.mkdir(parents=True)
    (project_dir / "agents").mkdir()
    (project_dir / ".claws").mkdir()

    # Write claws.yaml
    config_template = (TEMPLATES / "claws.yaml").read_text()
    config_content = config_template.replace("{project_name}", project_name)
    # Update provider and model if non-default
    if provider != "anthropic":
        config_content = config_content.replace(
            "type: anthropic", f"type: {provider}"
        )
    if model:
        config_content = config_content.replace(
            "model: claude-sonnet-4-5-20250929", f"model: {model}"
        )
    (project_dir / "claws.yaml").write_text(config_content)

    # Write .gitignore
    gitignore = (TEMPLATES / "gitignore").read_text()
    (project_dir / ".gitignore").write_text(gitignore)

    # Emit init event
    spine = EventSpine(project_dir)
    spine.emit(Event(
        type=PROJECT_INITIALIZED,
        data={"project": project_name, "provider": provider, "model": model},
    ))

    # Print summary
    console.print("  [green]+[/] claws.yaml")
    console.print("  [green]+[/] .gitignore")
    console.print("  [green]+[/] agents/")
    console.print("  [green]+[/] .claws/events.jsonl")
    console.print()
    console.print(Panel.fit(
        f"[bold green]Project '{project_name}' created.[/]\n\n"
        f"Next steps:\n"
        f"  cd {project_name}\n"
        f"  claws agent create scout --role researcher\n"
        f"  claws run scout \"your first task\"",
        title="claws",
        border_style="green",
    ))


def _default_model(provider: str) -> str:
    defaults = {
        "anthropic": "claude-sonnet-4-5-20250929",
        "openai": "gpt-4o",
        "ollama": "llama3",
    }
    return defaults.get(provider, "")
