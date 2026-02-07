"""claws evaluate -- evaluate agent task output using dual judge prompts."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from claws.config import find_project_root, load_config
from claws.events import EventSpine, Event, TASK_COMPLETED, EVAL_STARTED, EVAL_COMPLETED
from claws.evaluation import (
    _load_prompt,
    _parse_output_file,
    _extract_json,
    _determine_tier,
    _tier_color,
    _run_judge,
)
from claws.providers import get_provider, Message

console = Console()


@click.command()
@click.argument("agent_name")
@click.option("--provider", "provider_name", default=None, help="Provider to use for evaluation")
@click.option("--output", "output_path", type=click.Path(), default=None, help="Save results JSON to file")
def evaluate(agent_name: str, provider_name: str | None, output_path: str | None):
    """Evaluate an agent's last task output using dual judge prompts.

    Runs logic and consistency judges against the agent's most recent
    task output and reports quality scores.
    """
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project. Run 'claws init' first.")
        raise SystemExit(1)

    config = load_config(project_root)
    spine = EventSpine(project_root)

    # Find last completed task for this agent
    completed_events = [
        e for e in spine.read_by_type(TASK_COMPLETED)
        if e.agent == agent_name
    ]
    if not completed_events:
        console.print(f"[red]Error:[/] No completed tasks found for agent '{agent_name}'.")
        raise SystemExit(1)

    last_event = completed_events[-1]
    output_file_rel = last_event.data.get("output_file")
    if not output_file_rel:
        console.print(f"[red]Error:[/] Last completed task for '{agent_name}' has no output file.")
        raise SystemExit(1)

    output_file = project_root / output_file_rel
    if not output_file.exists():
        console.print(f"[red]Error:[/] Output file not found: {output_file_rel}")
        raise SystemExit(1)

    # Read and parse output file
    content = output_file.read_text()
    task, response = _parse_output_file(content)

    if not response.strip():
        console.print(f"[red]Error:[/] Output file has empty response.")
        raise SystemExit(1)

    # Determine provider: --provider flag > eval.provider config > default provider
    resolved_provider_name = provider_name or config.eval.provider or "default"
    provider_cfg = config.providers.get(resolved_provider_name)
    if provider_cfg is None:
        console.print(f"[red]Error:[/] Provider '{resolved_provider_name}' not found in claws.yaml.")
        raise SystemExit(1)

    try:
        provider = get_provider(provider_cfg)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        raise SystemExit(1)

    # Emit eval started event
    correlation_id = spine.emit(Event(
        type=EVAL_STARTED,
        agent=agent_name,
        data={
            "provider": resolved_provider_name,
            "model": provider_cfg.model,
            "judges": config.eval.judges,
            "task_event_id": last_event.id,
        },
    )).id

    console.print()
    console.print(f"[bold]Evaluating[/] {agent_name} [{provider_cfg.model}]")
    console.print(f"[dim]Output: {output_file_rel}[/]")
    console.print(f"[dim]Judges: {', '.join(config.eval.judges)}[/]")
    console.print(f"[dim]Threshold: {config.eval.threshold}[/]")

    # Run judges
    start_time = time.time()
    results: dict[str, dict[str, Any] | None] = {}

    for judge_name in config.eval.judges:
        try:
            console.print(f"\n[dim]Running {judge_name} judge...[/]")
            result = asyncio.run(_run_judge(provider, judge_name, task, response))
            if result is None:
                console.print(f"[yellow]Warning:[/] Failed to parse {judge_name} judge response")
            results[judge_name] = result
        except FileNotFoundError as e:
            console.print(f"[yellow]Warning:[/] {e}")
            results[judge_name] = None

    elapsed = time.time() - start_time

    # Display results
    all_passed = True
    for judge_name, result in results.items():
        if result is None:
            console.print(f"\n[yellow]{judge_name} judge:[/] evaluation failed")
            all_passed = False
            continue

        overall = result.get("overall", 0)
        tier = result.get("tier", _determine_tier(overall))
        color = _tier_color(tier)
        passed = overall >= config.eval.threshold

        if not passed:
            all_passed = False

        # Build scores table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Dimension", style="bold")
        table.add_column("Score", justify="right")

        scores = result.get("scores", {})
        for dim, score in scores.items():
            dim_display = dim.replace("_", " ").title()
            score_color = "green" if score >= 8 else "yellow" if score >= 6 else "red"
            table.add_row(dim_display, f"[{score_color}]{score:.1f}[/]")

        status_text = "[green]PASS[/]" if passed else "[red]FAIL[/]"
        panel_title = f"{judge_name.title()} Judge  [{color}]{tier.upper()}[/]  {overall:.1f}/10  {status_text}"

        rationale = result.get("rationale", "")
        console.print()
        console.print(Panel(
            f"[dim]{rationale}[/]" if rationale else "",
            title=panel_title,
            border_style=color,
        ))
        console.print(table)

    # Summary
    console.print()
    passing_scores = [
        r.get("overall", 0)
        for r in results.values()
        if r is not None
    ]
    if passing_scores:
        avg = sum(passing_scores) / len(passing_scores)
        verdict_color = "green" if all_passed else "red"
        verdict = "PASS" if all_passed else "FAIL"
        console.print(
            f"[bold {verdict_color}]{verdict}[/]  "
            f"Average: {avg:.1f}/10  "
            f"Threshold: {config.eval.threshold}  "
            f"[dim]{elapsed:.1f}s[/]"
        )
    else:
        console.print("[red]All judges failed to produce results.[/]")
        all_passed = False

    # Emit eval completed event
    spine.emit(Event(
        type=EVAL_COMPLETED,
        agent=agent_name,
        correlation_id=correlation_id,
        data={
            "results": {k: v for k, v in results.items() if v is not None},
            "all_passed": all_passed,
            "elapsed_s": round(elapsed, 1),
        },
    ))

    # Save results to file if requested
    if output_path:
        output_data = {
            "agent": agent_name,
            "output_file": output_file_rel,
            "provider": resolved_provider_name,
            "model": provider_cfg.model,
            "threshold": config.eval.threshold,
            "results": results,
            "all_passed": all_passed,
            "elapsed_s": round(elapsed, 1),
        }
        output_dest = Path(output_path)
        output_dest.parent.mkdir(parents=True, exist_ok=True)
        output_dest.write_text(json.dumps(output_data, indent=2) + "\n")
        console.print(f"[dim]Results saved to {output_path}[/]")

    if not all_passed:
        raise SystemExit(1)
