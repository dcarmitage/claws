"""claws decision — first-class decision protocol.

A standard format for presenting decisions to humans and recording
resolutions. Decisions are events in the event log, independent of
the scratchpad. Every decision has a question, options with context,
and (when resolved) a choice with reasoning.

Usage:
    claws decision present <agent> <question> --option <opt> [--option <opt>]
    claws decision resolve <agent> <number> <resolution> [--reasoning <why>]
    claws decision list <agent> [--all]
    claws decision history <agent>
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
    DECISION_PRESENTED,
    DECISION_RESOLVED,
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


def _get_decisions(spine: EventSpine, agent: str) -> list[dict]:
    """Build decision list from event log.

    Returns list of dicts with keys: number, question, options, status,
    resolution, reasoning, presented_at, resolved_at.
    """
    events = spine.read_by_agent(agent)
    decisions: dict[int, dict] = {}

    for e in events:
        if e.type == DECISION_PRESENTED:
            num = e.data.get("number", 0)
            decisions[num] = {
                "number": num,
                "question": e.data.get("question", ""),
                "options": e.data.get("options", []),
                "context": e.data.get("context", ""),
                "status": "pending",
                "resolution": "",
                "reasoning": "",
                "presented_at": e.ts,
                "resolved_at": "",
            }
        elif e.type == DECISION_RESOLVED:
            num = e.data.get("number", 0)
            if num in decisions:
                decisions[num]["status"] = "resolved"
                decisions[num]["resolution"] = e.data.get("resolution", "")
                decisions[num]["reasoning"] = e.data.get("reasoning", "")
                decisions[num]["resolved_at"] = e.ts

    # Return sorted by number
    return sorted(decisions.values(), key=lambda d: d["number"])


def _next_decision_number(spine: EventSpine, agent: str) -> int:
    """Get the next decision number for an agent from the event log."""
    events = spine.read_by_agent(agent)
    max_num = 0
    for e in events:
        if e.type == DECISION_PRESENTED:
            num = e.data.get("number", 0)
            if num > max_num:
                max_num = num
    return max_num + 1


@click.group()
def decision():
    """Present decisions to humans and record resolutions.

    Decisions are first-class events — no scratchpad required.
    Each decision has a question, options, and (when resolved)
    a choice with reasoning.
    """


@decision.command()
@click.argument("agent_name")
@click.argument("question")
@click.option("--option", "-o", "options", multiple=True, required=True,
              help="An option to present (repeatable)")
@click.option("--context", "-c", default="", help="Additional context for the decision")
def present(agent_name: str, question: str, options: tuple[str, ...], context: str):
    """Present a decision with options for human review.

    Example:
        claws decision present scout "Which API?" -o "REST" -o "GraphQL" -o "gRPC"
    """
    project_root = _require_project()
    _require_agent(project_root, agent_name)

    spine = EventSpine(project_root)
    number = _next_decision_number(spine, agent_name)

    spine.emit(Event(
        type=DECISION_PRESENTED,
        agent=agent_name,
        data={
            "number": number,
            "question": question,
            "options": list(options),
            "context": context,
        },
    ))

    console.print(f"[green]Decision #{number} presented:[/] {question}")
    for i, opt in enumerate(options, 1):
        console.print(f"  {i}. {opt}")
    if context:
        console.print(f"  [dim]Context: {context}[/]")


@decision.command()
@click.argument("agent_name")
@click.argument("number", type=int)
@click.argument("resolution")
@click.option("--reasoning", "-r", default="", help="Why this choice was made")
def resolve(agent_name: str, number: int, resolution: str, reasoning: str):
    """Resolve a pending decision with a choice and reasoning.

    Example:
        claws decision resolve scout 1 "REST" --reasoning "Simpler for v1"
    """
    project_root = _require_project()
    _require_agent(project_root, agent_name)

    spine = EventSpine(project_root)
    decisions = _get_decisions(spine, agent_name)

    # Find the decision
    target = None
    for d in decisions:
        if d["number"] == number:
            target = d
            break

    if target is None:
        console.print(f"[red]Error:[/] Decision #{number} not found for agent '{agent_name}'.")
        raise SystemExit(1)

    if target["status"] == "resolved":
        console.print(
            f"[yellow]Decision #{number} is already resolved:[/] {target['resolution']}"
        )
        return

    spine.emit(Event(
        type=DECISION_RESOLVED,
        agent=agent_name,
        data={
            "number": number,
            "resolution": resolution,
            "reasoning": reasoning,
        },
    ))

    console.print(f"[green]Decision #{number} resolved:[/] {resolution}")
    if reasoning:
        console.print(f"  [dim]Reasoning: {reasoning}[/]")


@decision.command("list")
@click.argument("agent_name")
@click.option("--all", "show_all", is_flag=True, help="Include resolved decisions")
def list_decisions(agent_name: str, show_all: bool):
    """List decisions from the event log.

    By default shows only pending decisions. Use --all to include resolved.
    """
    project_root = _require_project()
    _require_agent(project_root, agent_name)

    spine = EventSpine(project_root)
    decisions = _get_decisions(spine, agent_name)

    if not show_all:
        decisions = [d for d in decisions if d["status"] == "pending"]

    if not decisions:
        if show_all:
            console.print("[dim]No decisions found.[/]")
        else:
            console.print("[dim]No pending decisions.[/]")
        return

    table = Table(title=f"Decisions — {agent_name}")
    table.add_column("#", justify="right", style="bold")
    table.add_column("Question")
    table.add_column("Options")
    table.add_column("Status")

    for d in decisions:
        opts = ", ".join(d["options"]) if d["options"] else "[dim]-[/]"
        if d["status"] == "resolved":
            status = f"[green]✓ {d['resolution']}[/]"
        else:
            status = "[yellow]pending[/]"
        table.add_row(str(d["number"]), d["question"], opts, status)

    console.print(table)


@decision.command()
@click.argument("agent_name")
def history(agent_name: str):
    """Show resolved decisions with outcomes and reasoning.

    Displays the full decision trail: what was asked, what was chosen,
    and why — useful for auditing agent decision patterns.
    """
    project_root = _require_project()
    _require_agent(project_root, agent_name)

    spine = EventSpine(project_root)
    decisions = _get_decisions(spine, agent_name)
    resolved = [d for d in decisions if d["status"] == "resolved"]

    if not resolved:
        console.print("[dim]No resolved decisions found.[/]")
        return

    console.print(f"\n[bold]Decision History — {agent_name}[/]\n")

    for d in resolved:
        console.print(Panel(
            f"[bold]Q:[/] {d['question']}\n"
            f"[bold]Options:[/] {', '.join(d['options']) if d['options'] else '-'}\n"
            f"[bold]Resolution:[/] [green]{d['resolution']}[/]\n"
            f"[bold]Reasoning:[/] {d['reasoning'] if d['reasoning'] else '[dim]none[/]'}\n"
            f"[dim]Presented: {d['presented_at'][:19]}  Resolved: {d['resolved_at'][:19]}[/]",
            title=f"Decision #{d['number']}",
            border_style="green",
        ))
