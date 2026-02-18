"""claws session — session continuity for agents.

Agents auto-read their scratchpad on wake and auto-update on completion.
Session start/end bookend every work period with structured state.

Usage:
    claws session start <agent>   — wake up, show context
    claws session end <agent>     — wrap up, tend scratchpad
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from claws.config import find_project_root
from claws.events import (
    EventSpine,
    Event,
    SESSION_STARTED,
    SESSION_ENDED,
    DECISION_PRESENTED,
    DECISION_RESOLVED,
)
from claws.scratchpad import (
    load_scratchpad,
    save_scratchpad,
)

console = Console()


def _require_project() -> Path:
    """Find project root or exit with error."""
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project. Run 'claws init' first.")
        raise SystemExit(1)
    return project_root


def _require_agent(project_root: Path, name: str) -> Path:
    """Verify agent exists, return agent directory or exit."""
    agent_dir = project_root / "agents" / name
    if not agent_dir.exists():
        console.print(f"[red]Error:[/] Agent '{name}' not found.")
        raise SystemExit(1)
    return agent_dir


def _count_pending_decisions(spine: EventSpine, agent: str) -> int:
    """Count pending (unresolved) decisions from the event log."""
    events = spine.read_by_agent(agent)
    presented = set()
    resolved = set()
    for e in events:
        if e.type == DECISION_PRESENTED:
            presented.add(e.data.get("number", 0))
        elif e.type == DECISION_RESOLVED:
            resolved.add(e.data.get("number", 0))
    return len(presented - resolved)


def _last_session_event(spine: EventSpine, agent: str) -> Event | None:
    """Get the most recent session start or end event."""
    events = spine.read_by_agent(agent)
    session_events = [
        e for e in events
        if e.type in (SESSION_STARTED, SESSION_ENDED)
    ]
    return session_events[-1] if session_events else None


@click.group()
def session():
    """Manage agent work sessions.

    Use 'start' to wake an agent (loads context from scratchpad),
    and 'end' to wrap up (auto-tends scratchpad, records reflection).
    """


@session.command()
@click.argument("agent_name")
def start(agent_name: str):
    """Start a session — wake up an agent with full context.

    Reads the scratchpad (if it exists) and prints a session-start
    summary: active threads, pending decisions, inbox items.
    Emits a session.started event.

    Example:
        claws session start scout
    """
    project_root = _require_project()
    _require_agent(project_root, agent_name)

    spine = EventSpine(project_root)

    # Check for previous session state
    last = _last_session_event(spine, agent_name)
    if last and last.type == SESSION_STARTED:
        console.print(
            f"[yellow]Note:[/] Previous session started at {last.ts[:19]} "
            f"was not ended. Consider running 'claws session end {agent_name}' first."
        )

    # Load scratchpad if available
    sp = load_scratchpad(project_root, agent_name)

    # Build session data for event
    session_data: dict = {}
    threads_count = 0
    pending_decisions_count = 0
    inbox_count = 0

    if sp:
        threads_count = len(sp.threads)
        pending_sp_decisions = len([d for d in sp.decisions if not d.resolved])
        inbox_count = len(sp.inbox)
        session_data["scratchpad"] = True
        session_data["threads"] = threads_count
        session_data["scratchpad_decisions"] = pending_sp_decisions
        session_data["inbox"] = inbox_count
    else:
        session_data["scratchpad"] = False

    # Count event-log decisions too
    pending_decisions_count = _count_pending_decisions(spine, agent_name)
    session_data["pending_decisions"] = pending_decisions_count

    # Emit session.started event
    spine.emit(Event(
        type=SESSION_STARTED,
        agent=agent_name,
        data=session_data,
    ))

    # Display session start summary
    console.print()
    console.print(f"[bold green]Session started — {agent_name}[/]")
    console.print()

    if sp:
        # Threads
        if sp.threads:
            table = Table(title="🧵 Active Threads", show_lines=False)
            table.add_column("Thread", style="bold")
            table.add_column("State")
            table.add_column("Next")

            for t in sp.threads:
                state = t.state if t.state else "[dim]-[/]"
                next_act = t.next_action if t.next_action else "[dim]-[/]"
                table.add_row(t.name, state, next_act)

            console.print(table)
            console.print()
        else:
            console.print("[dim]No active threads.[/]")
            console.print()

        # Pending scratchpad decisions
        pending = [d for d in sp.decisions if not d.resolved]
        if pending:
            console.print(f"[bold]⚖️  {len(pending)} pending scratchpad decision(s)[/]")
            for d in pending:
                console.print(f"  #{d.number}: {d.question} [{d.urgency}]")
            console.print()

        # Inbox
        if sp.inbox:
            console.print(f"[bold]📬 Inbox ({len(sp.inbox)} item(s))[/]")
            for item in sp.inbox:
                console.print(f"  • {item}")
            console.print()

        # Reflections (show last one as context)
        if sp.reflections:
            console.print(f"[dim]Last reflection: {sp.reflections[-1]}[/]")
            console.print()
    else:
        console.print("[dim]No scratchpad found. Create one with: claws scratchpad init {agent_name}[/]")
        console.print()

    # Event-log decisions
    if pending_decisions_count > 0:
        console.print(f"[bold]📋 {pending_decisions_count} pending decision(s) in event log[/]")
        console.print()

    # Summary line
    parts = []
    if threads_count:
        parts.append(f"{threads_count} threads")
    if pending_decisions_count:
        parts.append(f"{pending_decisions_count} decisions")
    if inbox_count:
        parts.append(f"{inbox_count} inbox")

    if parts:
        console.print(f"[green]Ready.[/] Context: {', '.join(parts)}")
    else:
        console.print("[green]Ready.[/] Clean slate — no pending context.")


@session.command()
@click.argument("agent_name")
@click.option("--summary", "-s", default="", help="Add a reflection/summary of what was accomplished")
def end(agent_name: str, summary: str):
    """End a session — wrap up and tend scratchpad.

    Auto-tends the scratchpad (updates last-tended timestamp).
    Optionally adds a reflection summarizing the session.
    Emits a session.ended event.

    Example:
        claws session end scout --summary "Completed API integration, tests green"
    """
    project_root = _require_project()
    _require_agent(project_root, agent_name)

    spine = EventSpine(project_root)

    # Build session data
    session_data: dict = {}
    if summary:
        session_data["summary"] = summary

    # Load and tend scratchpad if it exists
    sp = load_scratchpad(project_root, agent_name)
    if sp:
        # Add reflection if summary provided
        if summary:
            sp.reflections.append(summary)

        # Tend (save updates last_tended via to_markdown)
        save_scratchpad(project_root, sp)

        session_data["scratchpad_tended"] = True
        session_data["threads"] = len(sp.threads)
        session_data["pending_decisions"] = len([d for d in sp.decisions if not d.resolved])
    else:
        session_data["scratchpad_tended"] = False

    # Emit session.ended event
    spine.emit(Event(
        type=SESSION_ENDED,
        agent=agent_name,
        data=session_data,
    ))

    # Display
    console.print()
    console.print(f"[bold]Session ended — {agent_name}[/]")

    if sp:
        threads = len(sp.threads)
        pending = len([d for d in sp.decisions if not d.resolved])
        console.print(f"  Scratchpad tended ({threads} threads, {pending} pending decisions)")

    if summary:
        console.print(f"  Reflection: {summary}")

    console.print("[green]Done.[/]")
