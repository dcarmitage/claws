"""claws agent — manage agents in a project."""

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from claws.config import find_project_root, load_config, CONFIG_FILENAME
from claws.events import EventSpine, Event, AGENT_CREATED
from claws.trust import TrustProfile

console = Console()
TEMPLATES = Path(__file__).parent.parent / "templates"


@click.group()
def agent():
    """Create, list, and manage agents."""


@agent.command()
@click.argument("name")
@click.option("--role", required=True, help="Agent role (e.g. researcher, developer, reviewer)")
@click.option("--provider", default="default", help="LLM provider name from claws.yaml")
def create(name: str, role: str, provider: str):
    """Create a new agent in the current project."""
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project. Run 'claws init' first.")
        raise SystemExit(1)

    agent_dir = project_root / "agents" / name
    if agent_dir.exists():
        console.print(f"[red]Error:[/] Agent '{name}' already exists.")
        raise SystemExit(1)

    # Create agent directory
    agent_dir.mkdir(parents=True)
    (agent_dir / "output").mkdir()

    # Write identity from template
    identity = (TEMPLATES / "identity.md").read_text()
    identity = identity.replace("{agent_name}", name).replace("{agent_role}", role)
    (agent_dir / "identity.md").write_text(identity)

    # Write memory from template
    memory = (TEMPLATES / "memory.md").read_text()
    memory = memory.replace("{agent_name}", name)
    (agent_dir / "memory.md").write_text(memory)

    # Update claws.yaml with the new agent
    _add_agent_to_config(project_root, name, role, provider)

    # Emit event
    spine = EventSpine(project_root)
    spine.emit(Event(
        type=AGENT_CREATED,
        agent=name,
        data={"role": role, "provider": provider},
    ))

    console.print()
    console.print(f"[bold green]Agent '{name}' created.[/]")
    console.print()
    console.print(f"  [green]+[/] agents/{name}/identity.md")
    console.print(f"  [green]+[/] agents/{name}/memory.md")
    console.print(f"  [green]+[/] agents/{name}/output/")
    console.print()
    console.print(f"Run: [bold]claws run {name} \"your task here\"[/]")


@agent.command("list")
def list_agents():
    """List all agents in the current project."""
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project. Run 'claws init' first.")
        raise SystemExit(1)

    config = load_config(project_root)
    agents_dir = project_root / "agents"

    if not config.agents and not agents_dir.exists():
        console.print("No agents found. Create one with: [bold]claws agent create <name> --role <role>[/]")
        return

    spine = EventSpine(project_root)

    table = Table(title="Agents")
    table.add_column("Name", style="bold")
    table.add_column("Role")
    table.add_column("Provider")
    table.add_column("Machine")
    table.add_column("Trust")

    # Show agents from config
    for name, agent_cfg in config.agents.items():
        profile = TrustProfile.for_agent(spine, name)
        if profile.eval_count == 0:
            trust_text = "[dim]new[/]"
        else:
            avg = profile.average
            if avg is not None and avg >= 8.0:
                trust_text = f"[green]{avg:.1f}[/]"
            elif avg is not None and avg >= 6.0:
                trust_text = f"[yellow]{avg:.1f}[/]"
            elif avg is not None:
                trust_text = f"[red]{avg:.1f}[/]"
            else:
                trust_text = "[dim]new[/]"
        table.add_row(name, agent_cfg.role, agent_cfg.provider, agent_cfg.machine, trust_text)

    # Show agents on disk but not in config
    if agents_dir.exists():
        for agent_path in sorted(agents_dir.iterdir()):
            if agent_path.is_dir() and agent_path.name not in config.agents:
                table.add_row(agent_path.name, "[dim]unregistered[/]", "-", "-", "-")

    console.print(table)


@agent.command()
@click.argument("name")
def info(name: str):
    """Show detailed info about an agent."""
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project.")
        raise SystemExit(1)

    agent_dir = project_root / "agents" / name
    if not agent_dir.exists():
        console.print(f"[red]Error:[/] Agent '{name}' not found.")
        raise SystemExit(1)

    # Read identity
    identity_path = agent_dir / "identity.md"
    if identity_path.exists():
        console.print(identity_path.read_text())

    # Show trust profile
    spine = EventSpine(project_root)
    profile = TrustProfile.for_agent(spine, name)
    if profile.eval_count > 0:
        trust_lines = []
        trust_lines.append(f"Evaluations: {profile.eval_count}")
        if profile.average is not None:
            avg = profile.average
            color = "green" if avg >= 8.0 else "yellow" if avg >= 6.0 else "red"
            trust_lines.append(f"Overall:     [{color}]{avg:.1f}[/]")
        for judge, avg in profile.judge_averages.items():
            color = "green" if avg >= 8.0 else "yellow" if avg >= 6.0 else "red"
            trust_lines.append(f"  {judge}: [{color}]{avg:.1f}[/]")
        trust_lines.append(f"Trend:       {profile.trend}")
        console.print()
        console.print(Panel("\n".join(trust_lines), title="Trust Profile", border_style="cyan"))

    # Show recent events
    events = spine.read_by_agent(name)
    if events:
        console.print(f"\n[bold]Recent events:[/] ({len(events)} total)")
        for event in events[-5:]:
            console.print(f"  {event.ts[:19]}  {event.type}  {event.data}")


def _add_agent_to_config(project_root: Path, name: str, role: str, provider: str):
    """Add an agent entry to claws.yaml."""
    import yaml

    config_path = project_root / CONFIG_FILENAME
    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    if "agents" not in raw or raw["agents"] is None:
        raw["agents"] = {}

    raw["agents"][name] = {
        "role": role,
        "provider": provider,
        "machine": "local",
    }

    with open(config_path, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, sort_keys=False)
