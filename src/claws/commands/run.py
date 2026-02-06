"""claws run — execute a task with an agent."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner

from claws.config import find_project_root, load_config
from claws.events import EventSpine, Event, TASK_STARTED, TASK_COMPLETED, TASK_FAILED
from claws.providers import get_provider, Message

console = Console()


@click.command()
@click.argument("agent_name")
@click.argument("task")
@click.option("--no-stream", is_flag=True, help="Wait for full response instead of streaming")
@click.option("--save/--no-save", default=True, help="Save output to agent's output directory")
def run(agent_name: str, task: str, no_stream: bool, save: bool):
    """Run a task with an agent.

    The agent uses its identity as system context and sends the task
    to the configured LLM provider.
    """
    project_root = find_project_root()
    if project_root is None:
        console.print("[red]Error:[/] Not in a claws project. Run 'claws init' first.")
        raise SystemExit(1)

    config = load_config(project_root)
    agent_dir = project_root / "agents" / agent_name

    if not agent_dir.exists():
        console.print(f"[red]Error:[/] Agent '{agent_name}' not found. Create with: claws agent create {agent_name} --role <role>")
        raise SystemExit(1)

    # Load agent config
    agent_cfg = config.agents.get(agent_name)
    if agent_cfg is None:
        console.print(f"[yellow]Warning:[/] Agent '{agent_name}' not in claws.yaml. Using default provider.")
        provider_name = "default"
    else:
        provider_name = agent_cfg.provider

    provider_cfg = config.providers.get(provider_name)
    if provider_cfg is None:
        console.print(f"[red]Error:[/] Provider '{provider_name}' not found in claws.yaml.")
        raise SystemExit(1)

    # Build provider
    try:
        provider = get_provider(provider_cfg)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        raise SystemExit(1)

    # Load agent identity as system prompt
    identity_path = agent_dir / "identity.md"
    system_prompt = ""
    if identity_path.exists():
        system_prompt = identity_path.read_text()

    # Load agent memory for context
    memory_path = agent_dir / "memory.md"
    if memory_path.exists():
        memory = memory_path.read_text()
        if memory.strip():
            system_prompt += f"\n\n---\n\n# Your Memory\n{memory}"

    # Build messages
    messages = []
    if system_prompt:
        messages.append(Message(role="system", content=system_prompt))
    messages.append(Message(role="user", content=task))

    # Emit task started event
    spine = EventSpine(project_root)
    correlation_id = spine.emit(Event(
        type=TASK_STARTED,
        agent=agent_name,
        data={"task": task, "provider": provider_name, "model": provider_cfg.model},
    )).id

    console.print()
    console.print(f"[bold]{agent_name}[/] [{provider_cfg.model}]")
    console.print(f"[dim]{task}[/]")
    console.print()

    # Execute
    start_time = time.time()
    try:
        if no_stream:
            response = asyncio.run(_run_complete(provider, messages))
            console.print(Markdown(response.content))
            result_text = response.content
            tokens_in = response.tokens_in
            tokens_out = response.tokens_out
        else:
            result_text, tokens_in, tokens_out = asyncio.run(
                _run_stream(provider, messages)
            )
    except Exception as e:
        elapsed = time.time() - start_time
        spine.emit(Event(
            type=TASK_FAILED,
            agent=agent_name,
            correlation_id=correlation_id,
            data={"error": str(e), "elapsed_s": round(elapsed, 1)},
        ))
        console.print(f"\n[red]Error:[/] {e}")
        raise SystemExit(1)

    elapsed = time.time() - start_time

    # Save output
    output_path = None
    if save:
        output_dir = agent_dir / "output"
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = output_dir / f"{timestamp}.md"
        output_content = f"# Task\n\n{task}\n\n# Response\n\n{result_text}\n"
        output_path.write_text(output_content)

    # Emit completed event
    spine.emit(Event(
        type=TASK_COMPLETED,
        agent=agent_name,
        correlation_id=correlation_id,
        data={
            "task": task,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "elapsed_s": round(elapsed, 1),
            "output_file": str(output_path) if output_path else None,
        },
    ))

    # Print summary
    console.print()
    console.print(
        f"[dim]{tokens_in + tokens_out} tokens · {elapsed:.1f}s"
        + (f" · saved to {output_path.name}" if output_path else "")
        + "[/]"
    )


async def _run_complete(provider, messages):
    return await provider.complete(messages)


async def _run_stream(provider, messages) -> tuple[str, int, int]:
    """Stream response to terminal, return full text and token estimates."""
    chunks = []
    async for chunk in provider.stream(messages):
        console.print(chunk, end="", highlight=False)
        chunks.append(chunk)
    console.print()  # final newline
    full_text = "".join(chunks)
    # Estimate tokens (streaming doesn't always return usage)
    est_out = len(full_text) // 4
    return full_text, 0, est_out
