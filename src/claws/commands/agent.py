"""claws agent — manage agents in a project."""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from claws.config import find_project_root, load_config, CONFIG_FILENAME
from claws.events import (
    EventSpine,
    Event,
    AGENT_CREATED,
    AGENT_SNAPSHOT_CREATED,
    AGENT_SNAPSHOT_RESTORED,
)
from claws.trust import TrustProfile, tier_label

console = Console()
TEMPLATES = Path(__file__).parent.parent / "templates"
SNAPSHOT_FILES = ("identity.md", "memory.md")


@click.group()
def agent():
    """Create, list, and manage agents."""


@agent.command()
@click.argument("name")
@click.option("--role", required=True, help="Agent role (e.g. researcher, developer, reviewer)")
@click.option("--provider", default="default", help="LLM provider name from claws.yaml")
@click.option("--onboard", "onboard_curriculum", default=None, is_flag=False, flag_value="default",
              help="Onboard agent with curriculum (default: 'default')")
def create(name: str, role: str, provider: str, onboard_curriculum: str | None):
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

    if onboard_curriculum:
        from claws.onboarding.engine import OnboardingEngine
        console.print(f"Starting onboarding with '{onboard_curriculum}' curriculum...")
        engine = OnboardingEngine(
            project_root=project_root,
            agent_name=name,
            curriculum_name=onboard_curriculum,
        )
        state = asyncio.run(engine.run())
        if state.status != "completed":
            raise SystemExit(1)
    else:
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
        trust_lines.append(f"Tier:        {tier_label(profile.tier)}")
        console.print()
        console.print(Panel("\n".join(trust_lines), title="Trust Profile", border_style="cyan"))

    # Show recent events
    events = spine.read_by_agent(name)
    if events:
        console.print(f"\n[bold]Recent events:[/] ({len(events)} total)")
        for event in events[-5:]:
            console.print(f"  {event.ts[:19]}  {event.type}  {event.data}")


@agent.command()
@click.argument("name")
def tier(name: str):
    """Show an agent's autonomy tier, trust score, and permissions."""
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project.")
        raise SystemExit(1)

    agent_dir = project_root / "agents" / name
    if not agent_dir.exists():
        console.print(f"[red]Error:[/] Agent '{name}' not found.")
        raise SystemExit(1)

    spine = EventSpine(project_root)
    profile = TrustProfile.for_agent(spine, name)

    t = profile.tier
    label = tier_label(t)

    tier_colors = {
        "Restricted": "red",
        "Standard": "yellow",
        "Autonomous": "green",
    }
    color = tier_colors.get(label, "white")

    lines = []
    lines.append(f"Agent:       [bold]{name}[/]")
    if profile.average is not None:
        lines.append(f"Trust Score: {profile.average:.1f}")
    else:
        lines.append("Trust Score: [dim]no evaluations[/]")
    lines.append(f"Evaluations: {profile.eval_count}")
    lines.append(f"Trend:       {profile.trend}")
    lines.append("")
    lines.append(f"[bold]Tier: [{color}]{label}[/{color}][/bold]")
    lines.append("")
    lines.append("[bold]Permissions:[/]")
    for perm in profile.permissions:
        lines.append(f"  • {perm}")

    console.print()
    console.print(Panel("\n".join(lines), title="Autonomy Tier", border_style=color))


@agent.command()
@click.argument("name")
def snapshot(name: str):
    """Snapshot an agent's identity.md and memory.md."""
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project.")
        raise SystemExit(1)

    agent_dir = project_root / "agents" / name
    if not agent_dir.exists():
        console.print(f"[red]Error:[/] Agent '{name}' not found.")
        raise SystemExit(1)

    try:
        snapshot_dir = _create_snapshot(project_root, name, require_all_files=True)
    except ValueError as exc:
        console.print(f"[red]Error:[/] {exc}")
        raise SystemExit(1)

    EventSpine(project_root).emit(Event(
        type=AGENT_SNAPSHOT_CREATED,
        agent=name,
        data={"snapshot": snapshot_dir.name},
    ))

    console.print(f"[green]Snapshot created:[/] {snapshot_dir.relative_to(project_root)}")


@agent.command()
@click.argument("name")
@click.option("--snapshot", "snapshot_id", default=None,
              help="Snapshot timestamp (default: latest)")
@click.option("--no-backup", is_flag=True, default=False,
              help="Skip automatic safety snapshot before restore")
def restore(name: str, snapshot_id: str | None, no_backup: bool):
    """Restore an agent's identity.md and memory.md from a snapshot."""
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project.")
        raise SystemExit(1)

    agent_dir = project_root / "agents" / name
    if not agent_dir.exists():
        console.print(f"[red]Error:[/] Agent '{name}' not found.")
        raise SystemExit(1)

    snapshot_dir = _resolve_snapshot(project_root, name, snapshot_id)
    if snapshot_dir is None:
        if snapshot_id:
            console.print(f"[red]Error:[/] Snapshot '{snapshot_id}' not found for agent '{name}'.")
        else:
            console.print(f"[red]Error:[/] No snapshots found for agent '{name}'.")
        raise SystemExit(1)

    missing = [f for f in SNAPSHOT_FILES if not (snapshot_dir / f).exists()]
    if missing:
        console.print(f"[red]Error:[/] Snapshot missing required files: {', '.join(missing)}")
        raise SystemExit(1)

    backup_snapshot = None
    if not no_backup:
        backup_snapshot = _create_snapshot(
            project_root,
            name,
            require_all_files=False,
            note="auto-pre-restore-backup",
        )

    for filename in SNAPSHOT_FILES:
        shutil.copy2(snapshot_dir / filename, agent_dir / filename)

    event_data = {"snapshot": snapshot_dir.name}
    if backup_snapshot is not None:
        event_data["backup_snapshot"] = backup_snapshot.name

    EventSpine(project_root).emit(Event(
        type=AGENT_SNAPSHOT_RESTORED,
        agent=name,
        data=event_data,
    ))

    if backup_snapshot is not None:
        console.print(
            f"[green]Restored[/] agent '{name}' from snapshot {snapshot_dir.name} "
            f"(backup: {backup_snapshot.name})"
        )
    else:
        console.print(f"[green]Restored[/] agent '{name}' from snapshot {snapshot_dir.name}")


@agent.group()
def snapshots():
    """Manage agent snapshots."""


@snapshots.command("list")
@click.argument("name")
def snapshots_list(name: str):
    """List snapshots for an agent."""
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project.")
        raise SystemExit(1)

    agent_dir = project_root / "agents" / name
    if not agent_dir.exists():
        console.print(f"[red]Error:[/] Agent '{name}' not found.")
        raise SystemExit(1)

    dirs = _list_snapshot_dirs(project_root, name)
    if not dirs:
        console.print(f"No snapshots found for agent '{name}'.")
        return

    table = Table(title=f"Snapshots: {name}")
    table.add_column("Snapshot", style="bold")
    table.add_column("Created At")
    table.add_column("Files")

    for snap in dirs:
        manifest_path = snap / "manifest.json"
        created_at = "-"
        files = ", ".join(SNAPSHOT_FILES)
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
                created_at = manifest.get("created_at", "-")
                files = ", ".join(manifest.get("files", SNAPSHOT_FILES))
            except json.JSONDecodeError:
                pass
        table.add_row(snap.name, created_at, files)

    console.print(table)


def _create_snapshot(
    project_root: Path,
    agent_name: str,
    require_all_files: bool,
    note: str | None = None,
) -> Path | None:
    """Create snapshot for an agent.

    If require_all_files is False and no snapshot files currently exist, returns None.
    """
    agent_dir = project_root / "agents" / agent_name

    existing_files = [f for f in SNAPSHOT_FILES if (agent_dir / f).exists()]
    missing_files = [f for f in SNAPSHOT_FILES if f not in existing_files]

    if require_all_files and missing_files:
        raise ValueError(f"Missing files for snapshot: {', '.join(missing_files)}")

    if not existing_files:
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    snapshot_dir = _snapshots_root(project_root, agent_name) / timestamp
    snapshot_dir.mkdir(parents=True, exist_ok=False)

    for filename in existing_files:
        shutil.copy2(agent_dir / filename, snapshot_dir / filename)

    manifest = {
        "agent": agent_name,
        "snapshot": timestamp,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": existing_files,
        "source": str(agent_dir.relative_to(project_root)),
    }
    if note:
        manifest["note"] = note

    (snapshot_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return snapshot_dir


def _snapshots_root(project_root: Path, agent_name: str) -> Path:
    return project_root / ".claws" / "snapshots" / agent_name


def _list_snapshot_dirs(project_root: Path, agent_name: str) -> list[Path]:
    root = _snapshots_root(project_root, agent_name)
    if not root.exists():
        return []
    dirs = [p for p in root.iterdir() if p.is_dir()]
    return sorted(dirs, key=lambda p: p.name, reverse=True)


def _resolve_snapshot(project_root: Path, agent_name: str, snapshot_id: str | None) -> Path | None:
    dirs = _list_snapshot_dirs(project_root, agent_name)
    if not dirs:
        return None
    if snapshot_id is None:
        return dirs[0]
    for d in dirs:
        if d.name == snapshot_id:
            return d
    return None


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


# Register onboard subcommand from its own module
from claws.commands.onboard import onboard as onboard_cmd  # noqa: E402
agent.add_command(onboard_cmd, "onboard")
