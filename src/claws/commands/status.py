"""claws status — show the state of all agents and recent activity."""

from pathlib import Path
from collections import defaultdict

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from claws.config import find_project_root, load_config
from claws.events import (
    EventSpine, TASK_STARTED, TASK_COMPLETED, TASK_FAILED,
    AGENT_CREATED, EVAL_COMPLETED,
)
from claws.trust import TrustProfile

console = Console()


@click.command()
@click.option("--events", "-e", default=10, help="Number of recent events to show")
def status(events: int):
    """Show project status, agents, and recent activity."""
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project. Run 'claws init' first.")
        raise SystemExit(1)

    config = load_config(project_root)
    spine = EventSpine(project_root)
    all_events = spine.read_all()

    # Project header
    console.print()
    console.print(f"[bold]{config.project}[/] [dim]claws v{config.version}[/]")
    console.print()

    # Agent table
    _print_agent_table(config, spine)

    # Recent events
    if all_events:
        console.print()
        _print_recent_events(all_events, events)

    # Summary stats
    if all_events:
        console.print()
        _print_stats(all_events)


def _print_agent_table(config, spine):
    """Show a table of all agents with their current state."""
    table = Table(title="Agents", show_lines=False)
    table.add_column("Agent", style="bold")
    table.add_column("Role")
    table.add_column("Tasks")
    table.add_column("Last Task")
    table.add_column("Status")
    table.add_column("Trust")

    for name, agent_cfg in config.agents.items():
        agent_events = spine.read_by_agent(name)
        completed = [e for e in agent_events if e.type == TASK_COMPLETED]
        failed = [e for e in agent_events if e.type == TASK_FAILED]
        started = [e for e in agent_events if e.type == TASK_STARTED]

        task_count = f"{len(completed)}/{len(completed) + len(failed)}"

        # Last task
        last = spine.last_event(agent=name, event_type=TASK_COMPLETED)
        if last:
            task_text = last.data.get("task", "")[:40]
            if len(last.data.get("task", "")) > 40:
                task_text += "..."
        else:
            task_text = "[dim]-[/]"

        # Status
        last_any = spine.last_event(agent=name)
        if last_any and last_any.type == TASK_STARTED:
            status_text = "[yellow]running[/]"
        elif last_any and last_any.type == TASK_FAILED:
            status_text = "[red]failed[/]"
        elif last_any and last_any.type == TASK_COMPLETED:
            status_text = "[green]idle[/]"
        else:
            status_text = "[dim]new[/]"

        # Trust
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

        table.add_row(name, agent_cfg.role, task_count, task_text, status_text, trust_text)

    if config.agents:
        console.print(table)
    else:
        console.print("[dim]No agents configured. Run: claws agent create <name> --role <role>[/]")


def _print_recent_events(all_events, limit):
    """Show recent events in a compact format."""
    console.print("[bold]Recent Activity[/]")
    for event in all_events[-limit:]:
        icon = _event_icon(event.type)
        agent_str = f"[bold]{event.agent}[/]" if event.agent else "[dim]system[/]"
        detail = _event_detail(event)
        time_str = event.ts[11:19] if len(event.ts) > 19 else event.ts
        console.print(f"  {time_str}  {icon} {agent_str}  {detail}")


def _print_stats(all_events):
    """Show aggregate statistics."""
    completed = [e for e in all_events if e.type == TASK_COMPLETED]
    total_tokens = sum(
        e.data.get("tokens_in", 0) + e.data.get("tokens_out", 0)
        for e in completed
    )
    total_time = sum(e.data.get("elapsed_s", 0) for e in completed)

    console.print(
        f"[dim]{len(completed)} tasks completed · "
        f"{total_tokens:,} tokens · "
        f"{total_time:.0f}s total[/]"
    )


def _event_icon(event_type: str) -> str:
    icons = {
        TASK_STARTED: "[yellow]>[/]",
        TASK_COMPLETED: "[green]v[/]",
        TASK_FAILED: "[red]x[/]",
        AGENT_CREATED: "[blue]+[/]",
        EVAL_COMPLETED: "[cyan]J[/]",
    }
    return icons.get(event_type, " ")


def _event_detail(event) -> str:
    if event.type == TASK_STARTED:
        task = event.data.get("task", "")[:50]
        return f"started: {task}"
    if event.type == TASK_COMPLETED:
        elapsed = event.data.get("elapsed_s", 0)
        tokens = event.data.get("tokens_in", 0) + event.data.get("tokens_out", 0)
        return f"completed ({elapsed}s, {tokens} tokens)"
    if event.type == TASK_FAILED:
        error = event.data.get("error", "unknown")[:50]
        return f"[red]failed: {error}[/]"
    if event.type == AGENT_CREATED:
        role = event.data.get("role", "")
        return f"created (role: {role})"
    if event.type == EVAL_COMPLETED:
        score = event.data.get("score", "?")
        return f"eval score: {score}"
    return event.type
