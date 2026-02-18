"""claws scratchpad — structured working memory for agents.

Maintains a living scratchpad.md in each agent's directory.
Unlike memory.md (retrospective), the scratchpad answers "where are we?"
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from claws.config import find_project_root, load_config
from claws.events import EventSpine, Event
from claws.scratchpad import (
    Scratchpad,
    Thread,
    Decision,
    scratchpad_path,
    load_scratchpad,
    save_scratchpad,
)

console = Console()

# Event types for scratchpad operations
SCRATCHPAD_CREATED = "scratchpad.created"
SCRATCHPAD_THREAD_ADDED = "scratchpad.thread.added"
SCRATCHPAD_THREAD_UPDATED = "scratchpad.thread.updated"
SCRATCHPAD_THREAD_ARCHIVED = "scratchpad.thread.archived"
SCRATCHPAD_DECISION_ADDED = "scratchpad.decision.added"
SCRATCHPAD_DECISION_RESOLVED = "scratchpad.decision.resolved"


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


def _require_scratchpad(project_root: Path, agent_name: str) -> Scratchpad:
    """Load existing scratchpad or exit with error."""
    sp = load_scratchpad(project_root, agent_name)
    if sp is None:
        console.print(
            f"[red]Error:[/] No scratchpad for agent '{agent_name}'. "
            f"Run: [bold]claws scratchpad init {agent_name}[/]"
        )
        raise SystemExit(1)
    return sp


@click.group()
def scratchpad():
    """Manage agent working memory (scratchpad.md)."""


@scratchpad.command()
@click.argument("agent_name")
@click.option("--force", is_flag=True, help="Overwrite existing scratchpad")
def init(agent_name: str, force: bool):
    """Create a new scratchpad.md for an agent."""
    project_root = _require_project()
    _require_agent(project_root, agent_name)

    path = scratchpad_path(project_root, agent_name)
    if path.exists() and not force:
        console.print(
            f"[yellow]Warning:[/] Scratchpad already exists for '{agent_name}'. "
            f"Use --force to overwrite."
        )
        raise SystemExit(1)

    sp = Scratchpad(agent_name=agent_name)
    save_scratchpad(project_root, sp)

    spine = EventSpine(project_root)
    spine.emit(Event(
        type=SCRATCHPAD_CREATED,
        agent=agent_name,
        data={"path": str(path.relative_to(project_root))},
    ))

    console.print(f"[green]Scratchpad created:[/] agents/{agent_name}/scratchpad.md")


@scratchpad.command()
@click.argument("agent_name")
@click.option("--raw", is_flag=True, help="Show raw markdown instead of formatted")
def show(agent_name: str, raw: bool):
    """Display an agent's scratchpad."""
    project_root = _require_project()
    _require_agent(project_root, agent_name)
    sp = _require_scratchpad(project_root, agent_name)

    if raw:
        console.print(sp.to_markdown())
        return

    # Formatted display
    console.print()
    console.print(f"[bold]Scratchpad — {sp.agent_name}[/]")
    if sp.last_tended:
        console.print(f"[dim]Last tended: {sp.last_tended}[/]")
    console.print()

    # Threads
    if sp.threads:
        table = Table(title="🧵 Open Threads", show_lines=True)
        table.add_column("Thread", style="bold")
        table.add_column("State")
        table.add_column("Next Action")
        table.add_column("Blocking")

        for t in sp.threads:
            blocking = f"[red]{t.blocking}[/]" if t.blocking else "[dim]-[/]"
            next_act = t.next_action if t.next_action else "[dim]-[/]"
            state = t.state if t.state else "[dim]-[/]"
            table.add_row(t.name, state, next_act, blocking)

        console.print(table)
    else:
        console.print("[dim]No active threads.[/]")

    console.print()

    # Decisions
    pending = [d for d in sp.decisions if not d.resolved]
    if pending:
        table = Table(title="⚖️ Decisions Waiting")
        table.add_column("#", justify="right")
        table.add_column("Decision")
        table.add_column("Context")
        table.add_column("Urgency")

        for d in pending:
            urgency_style = (
                "[red]" if d.urgency.lower() in ("urgent", "high")
                else "[yellow]" if d.urgency.lower() == "medium"
                else ""
            )
            urgency_text = f"{urgency_style}{d.urgency}[/]" if urgency_style else d.urgency
            table.add_row(str(d.number), d.question, d.context, urgency_text)

        console.print(table)
    else:
        console.print("[dim]No pending decisions.[/]")

    console.print()

    # Inbox
    if sp.inbox:
        console.print("[bold]📬 Inbox[/]")
        for item in sp.inbox:
            console.print(f"  • {item}")
        console.print()

    # Reflections
    if sp.reflections:
        console.print("[bold]🪞 Reflections[/]")
        for r in sp.reflections:
            console.print(f"  • {r}")
        console.print()


# --- Thread subcommands ---

@scratchpad.group()
def thread():
    """Manage scratchpad threads (active work streams)."""


@thread.command("add")
@click.argument("agent_name")
@click.argument("name")
@click.option("--state", "-s", default="", help="Current state of the thread")
@click.option("--next", "next_action", default="", help="Next action to take")
@click.option("--blocking", "-b", default="", help="What's blocking progress")
def thread_add(agent_name: str, name: str, state: str, next_action: str, blocking: str):
    """Add a new thread to an agent's scratchpad."""
    project_root = _require_project()
    _require_agent(project_root, agent_name)
    sp = _require_scratchpad(project_root, agent_name)

    # Check for duplicate
    if sp.find_thread(name):
        console.print(f"[red]Error:[/] Thread '{name}' already exists. Use 'thread update' to modify.")
        raise SystemExit(1)

    t = Thread(name=name, state=state, next_action=next_action, blocking=blocking)
    sp.threads.append(t)
    save_scratchpad(project_root, sp)

    spine = EventSpine(project_root)
    spine.emit(Event(
        type=SCRATCHPAD_THREAD_ADDED,
        agent=agent_name,
        data={"thread": name, "state": state},
    ))

    console.print(f"[green]Thread added:[/] {name}")


@thread.command("update")
@click.argument("agent_name")
@click.argument("name")
@click.option("--state", "-s", default=None, help="New state")
@click.option("--next", "next_action", default=None, help="New next action")
@click.option("--blocking", "-b", default=None, help="New blocking info (empty to clear)")
@click.option("--note", "-n", default=None, help="Add a note to the thread")
def thread_update(
    agent_name: str,
    name: str,
    state: str | None,
    next_action: str | None,
    blocking: str | None,
    note: str | None,
):
    """Update an existing thread in an agent's scratchpad."""
    project_root = _require_project()
    _require_agent(project_root, agent_name)
    sp = _require_scratchpad(project_root, agent_name)

    t = sp.find_thread(name)
    if t is None:
        console.print(f"[red]Error:[/] Thread '{name}' not found.")
        raise SystemExit(1)

    changes = {}
    if state is not None:
        t.state = state
        changes["state"] = state
    if next_action is not None:
        t.next_action = next_action
        changes["next_action"] = next_action
    if blocking is not None:
        t.blocking = blocking
        changes["blocking"] = blocking
    if note is not None:
        t.notes.append(note)
        changes["note"] = note

    if not changes:
        console.print("[yellow]No changes specified.[/]")
        return

    save_scratchpad(project_root, sp)

    spine = EventSpine(project_root)
    spine.emit(Event(
        type=SCRATCHPAD_THREAD_UPDATED,
        agent=agent_name,
        data={"thread": t.name, **changes},
    ))

    console.print(f"[green]Thread updated:[/] {t.name}")


@thread.command("archive")
@click.argument("agent_name")
@click.argument("name")
def thread_archive(agent_name: str, name: str):
    """Archive (remove) a thread from an agent's scratchpad."""
    project_root = _require_project()
    _require_agent(project_root, agent_name)
    sp = _require_scratchpad(project_root, agent_name)

    t = sp.find_thread(name)
    if t is None:
        console.print(f"[red]Error:[/] Thread '{name}' not found.")
        raise SystemExit(1)

    sp.threads.remove(t)
    save_scratchpad(project_root, sp)

    spine = EventSpine(project_root)
    spine.emit(Event(
        type=SCRATCHPAD_THREAD_ARCHIVED,
        agent=agent_name,
        data={"thread": t.name},
    ))

    console.print(f"[green]Thread archived:[/] {t.name}")


@thread.command("list")
@click.argument("agent_name")
def thread_list(agent_name: str):
    """List all threads in an agent's scratchpad."""
    project_root = _require_project()
    _require_agent(project_root, agent_name)
    sp = _require_scratchpad(project_root, agent_name)

    if not sp.threads:
        console.print("[dim]No active threads.[/]")
        return

    for t in sp.threads:
        status_icon = "⏸" if t.blocking else "→" if t.next_action else "·"
        console.print(f"  {status_icon} [bold]{t.name}[/]  {t.state}")


# --- Decision subcommands ---

@scratchpad.group()
def decision():
    """Manage scratchpad decisions (pending human input)."""


@decision.command("add")
@click.argument("agent_name")
@click.argument("question")
@click.option("--context", "-c", default="", help="Context for the decision")
@click.option("--urgency", "-u", default="normal",
              type=click.Choice(["low", "normal", "high", "urgent"], case_sensitive=False),
              help="Urgency level")
def decision_add(agent_name: str, question: str, context: str, urgency: str):
    """Add a pending decision to an agent's scratchpad."""
    project_root = _require_project()
    _require_agent(project_root, agent_name)
    sp = _require_scratchpad(project_root, agent_name)

    number = sp.next_decision_number
    d = Decision(number=number, question=question, context=context, urgency=urgency)
    sp.decisions.append(d)
    save_scratchpad(project_root, sp)

    spine = EventSpine(project_root)
    spine.emit(Event(
        type=SCRATCHPAD_DECISION_ADDED,
        agent=agent_name,
        data={"number": number, "question": question, "urgency": urgency},
    ))

    console.print(f"[green]Decision #{number} added:[/] {question}")


@decision.command("resolve")
@click.argument("agent_name")
@click.argument("number", type=int)
@click.argument("resolution")
def decision_resolve(agent_name: str, number: int, resolution: str):
    """Resolve a pending decision."""
    project_root = _require_project()
    _require_agent(project_root, agent_name)
    sp = _require_scratchpad(project_root, agent_name)

    d = sp.find_decision(number)
    if d is None:
        console.print(f"[red]Error:[/] Decision #{number} not found.")
        raise SystemExit(1)

    if d.resolved:
        console.print(f"[yellow]Decision #{number} is already resolved:[/] {d.resolution}")
        return

    d.resolved = True
    d.resolution = resolution
    save_scratchpad(project_root, sp)

    spine = EventSpine(project_root)
    spine.emit(Event(
        type=SCRATCHPAD_DECISION_RESOLVED,
        agent=agent_name,
        data={"number": number, "resolution": resolution},
    ))

    console.print(f"[green]Decision #{number} resolved:[/] {resolution}")


@decision.command("list")
@click.argument("agent_name")
@click.option("--all", "show_all", is_flag=True, help="Include resolved decisions")
def decision_list(agent_name: str, show_all: bool):
    """List decisions in an agent's scratchpad."""
    project_root = _require_project()
    _require_agent(project_root, agent_name)
    sp = _require_scratchpad(project_root, agent_name)

    decisions = sp.decisions if show_all else [d for d in sp.decisions if not d.resolved]

    if not decisions:
        console.print("[dim]No pending decisions.[/]")
        return

    table = Table(title="Decisions")
    table.add_column("#", justify="right")
    table.add_column("Decision")
    table.add_column("Context")
    table.add_column("Status")

    for d in decisions:
        if d.resolved:
            status = f"[green]✓ {d.resolution}[/]"
        else:
            status = f"[yellow]{d.urgency}[/]"
        table.add_row(str(d.number), d.question, d.context, status)

    console.print(table)
