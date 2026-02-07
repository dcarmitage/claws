"""claws init — create a new project with guided setup."""

from __future__ import annotations

import os
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from claws.events import EventSpine, Event, PROJECT_INITIALIZED

console = Console()
TEMPLATES = Path(__file__).parent.parent / "templates"

# Provider presets: label, type, model, api_key_env, base_url, help_url
PROVIDERS = {
    "1": {
        "label": "Anthropic",
        "type": "anthropic",
        "model": "claude-opus-4-6",
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": None,
        "help_url": "https://console.anthropic.com",
    },
    "2": {
        "label": "OpenAI",
        "type": "openai-compatible",
        "model": "codex-5.3",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "help_url": "https://platform.openai.com/api-keys",
    },
    "3": {
        "label": "OpenRouter",
        "type": "openai-compatible",
        "model": "anthropic/claude-opus-4-6",
        "api_key_env": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "help_url": "https://openrouter.ai/keys",
    },
}


def _interactive_setup() -> dict:
    """Run the interactive provider setup wizard. Returns a preset dict."""
    console.print()
    console.print("[bold]Which LLM provider?[/]")
    console.print()
    console.print("  [bold]1[/]  Anthropic [dim](recommended)[/]")
    console.print("  [bold]2[/]  OpenAI")
    console.print("  [bold]3[/]  OpenRouter")
    console.print()

    choice = click.prompt(
        "Choose",
        type=click.Choice(["1", "2", "3"]),
        default="1",
        show_choices=False,
    )

    preset = PROVIDERS[choice]

    console.print()
    console.print(f"  [bold]Provider:[/] {preset['label']}")
    console.print(f"  [bold]Model:[/]    {preset['model']}")
    console.print()

    # Check if API key is already set
    key_value = os.environ.get(preset["api_key_env"])
    if key_value:
        console.print(f"  [green]\u2713[/] {preset['api_key_env']} detected")
    else:
        console.print("  Set your API key:")
        console.print(f"    [bold]export {preset['api_key_env']}=your-key[/]")
        console.print(f"    \u2192 Get one at: {preset['help_url']}")
        console.print()
        console.print("  [dim]Set it now or later \u2014 run [bold]claws doctor[/bold] to verify.[/]")

    return preset


def _build_config(
    project: str,
    provider_type: str,
    model: str,
    api_key_env: str | None = None,
    base_url: str | None = None,
) -> str:
    """Build claws.yaml content."""
    lines = [
        f"project: {project}",
        "version: 2",
        "",
        "providers:",
        "  default:",
        f"    type: {provider_type}",
        f"    model: {model}",
    ]
    if base_url:
        lines.append(f"    base_url: {base_url}")
    if api_key_env:
        lines.append(f"    api_key_env: {api_key_env}")
    lines.extend([
        "",
        "agents: {}",
        "",
        "eval:",
        "  judges:",
        "    - logic",
        "    - consistency",
        "  threshold: 8.0",
        "",
    ])
    return "\n".join(lines) + "\n"


@click.command()
@click.argument("project_name")
@click.option("--provider", default=None, help="Provider type (skips guided setup)")
@click.option("--model", default=None, help="Model name (skips guided setup)")
def init(project_name: str, provider: str | None, model: str | None):
    """Create a new claws project.

    Sets up the project directory with configuration, agent directory,
    and event log. Includes guided provider setup when run interactively.
    """
    project_dir = Path.cwd() / project_name

    if project_dir.exists():
        console.print(f"[red]Error:[/] Directory '{project_name}' already exists.")
        raise SystemExit(1)

    console.print()
    console.print(f"[bold]Creating project:[/] {project_name}")

    # Decide: interactive wizard or direct flags
    if provider is not None or model is not None:
        # Direct mode: user specified flags
        provider_type = provider or "anthropic"
        model_name = model or _default_model(provider_type)
        api_key_env = None
        base_url = None
    else:
        # Interactive wizard
        try:
            preset = _interactive_setup()
            provider_type = preset["type"]
            model_name = preset["model"]
            api_key_env = preset["api_key_env"]
            base_url = preset["base_url"]
        except (EOFError, click.Abort):
            # No interactive input available — use Anthropic defaults
            provider_type = "anthropic"
            model_name = _default_model("anthropic")
            api_key_env = None
            base_url = None

    console.print()

    # Create directories
    project_dir.mkdir(parents=True)
    (project_dir / "agents").mkdir()
    (project_dir / ".claws").mkdir()

    # Write claws.yaml
    config_content = _build_config(
        project_name, provider_type, model_name, api_key_env, base_url,
    )
    (project_dir / "claws.yaml").write_text(config_content)

    # Write .gitignore
    gitignore = (TEMPLATES / "gitignore").read_text()
    (project_dir / ".gitignore").write_text(gitignore)

    # Emit init event
    spine = EventSpine(project_dir)
    spine.emit(Event(
        type=PROJECT_INITIALIZED,
        data={"project": project_name, "provider": provider_type, "model": model_name},
    ))

    # Print summary
    console.print("  [green]\u2713[/] claws.yaml")
    console.print("  [green]\u2713[/] .gitignore")
    console.print("  [green]\u2713[/] agents/")
    console.print("  [green]\u2713[/] .claws/events.jsonl")
    console.print()
    console.print(Panel.fit(
        f"[bold green]Project '{project_name}' created.[/]\n\n"
        f"Next steps:\n"
        f"  cd {project_name}\n"
        f"  claws doctor                                [dim]# verify setup[/]\n"
        f"  claws agent create scout --role researcher \\\n"
        f"    --onboard default                         [dim]# create + train[/]\n",
        title="claws",
        border_style="green",
    ))


def _default_model(provider: str) -> str:
    """Return the default model for a provider type."""
    defaults = {
        "anthropic": "claude-opus-4-6",
        "openai-compatible": "codex-5.3",
        "openai": "codex-5.3",
    }
    return defaults.get(provider, "")
