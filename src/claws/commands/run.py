"""claws run — execute a task with an agent, optionally with self-evaluation and retry."""

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
from claws.events import EventSpine, Event, TASK_STARTED, TASK_COMPLETED, TASK_FAILED, EVAL_STARTED, EVAL_COMPLETED
from claws.evaluation import evaluate_response, _determine_tier, _tier_color
from claws.providers import get_provider, Message

console = Console()


@click.command()
@click.argument("agent_name")
@click.argument("task")
@click.option("--no-stream", is_flag=True, help="Wait for full response instead of streaming")
@click.option("--save/--no-save", default=True, help="Save output to agent's output directory")
@click.option("--eval", "auto_eval", is_flag=True, help="Auto-evaluate after run; retry on failure")
@click.option("--retries", default=2, type=int, help="Max retries when --eval is set (default: 2)")
@click.option("--threshold", default=None, type=float, help="Override eval threshold (default: from claws.yaml)")
@click.option("--learn/--no-learn", default=False, help="Persist reflection insights to agent memory after eval")
def run(agent_name: str, task: str, no_stream: bool, save: bool, auto_eval: bool, retries: int, threshold: float | None, learn: bool):
    """Run a task with an agent.

    The agent uses its identity as system context and sends the task
    to the configured LLM provider.

    With --eval, the output is automatically evaluated using two-pass
    scoring. If the score falls below the threshold, the agent receives
    reflection feedback and retries (up to --retries times).
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

    # Resolve eval threshold
    eval_threshold = threshold if threshold is not None else config.eval.threshold

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

    # Execute with optional eval-retry loop
    spine = EventSpine(project_root)
    attempt = 0
    max_attempts = (retries + 1) if auto_eval else 1
    reflection_context = ""
    eval_scores: list[float] = []  # Track scores across attempts for learning

    while attempt < max_attempts:
        attempt += 1

        if attempt > 1:
            console.print()
            console.print(f"[bold yellow]Retry {attempt - 1}/{retries}[/] — reflecting and retrying...")
            console.print()

        # Build messages
        messages = []
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))

        # On retries, include the reflection feedback
        if reflection_context:
            messages.append(Message(role="user", content=task))
            messages.append(Message(role="assistant", content=f"[Previous attempt]\n{reflection_context}"))
            messages.append(Message(role="user", content=(
                "Your previous response was evaluated and scored below the quality threshold. "
                "The feedback above explains what went wrong. Please try again with an improved response. "
                "Address the specific issues raised by the judges."
            )))
        else:
            messages.append(Message(role="user", content=task))

        # Emit task started event
        correlation_id = spine.emit(Event(
            type=TASK_STARTED,
            agent=agent_name,
            data={
                "task": task,
                "provider": provider_name,
                "model": provider_cfg.model,
                "attempt": attempt,
            },
        )).id

        if attempt == 1:
            console.print()
            console.print(f"[bold]{agent_name}[/] [{provider_cfg.model}]")
            console.print(f"[dim]{task}[/]")
            if auto_eval:
                console.print(f"[dim]Auto-eval enabled · threshold: {eval_threshold} · max retries: {retries}[/]")
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
                data={"error": str(e), "elapsed_s": round(elapsed, 1), "attempt": attempt},
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
            suffix = f"-attempt{attempt}" if attempt > 1 else ""
            output_path = output_dir / f"{timestamp}{suffix}.md"
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
                "output_file": str(output_path.relative_to(project_root)) if output_path else None,
                "attempt": attempt,
            },
        ))

        # Print summary
        console.print()
        console.print(
            f"[dim]{tokens_in + tokens_out} tokens · {elapsed:.1f}s"
            + (f" · saved to {output_path.name}" if output_path else "")
            + (f" · attempt {attempt}/{max_attempts}" if auto_eval else "")
            + "[/]"
        )

        # Run evaluation if --eval
        if auto_eval:
            console.print()
            console.print("[dim]Running two-pass evaluation...[/]")

            # Use eval provider if configured, otherwise same provider
            eval_provider_name = config.eval.provider or provider_name
            eval_provider_cfg = config.providers.get(eval_provider_name)
            if eval_provider_cfg:
                try:
                    eval_provider = get_provider(eval_provider_cfg)
                except ValueError:
                    eval_provider = provider
            else:
                eval_provider = provider

            # Emit eval started event
            eval_correlation_id = spine.emit(Event(
                type=EVAL_STARTED,
                agent=agent_name,
                correlation_id=correlation_id,
                data={
                    "provider": eval_provider_name,
                    "model": (eval_provider_cfg or provider_cfg).model,
                    "judges": config.eval.judges,
                    "task_event_id": correlation_id,
                    "attempt": attempt,
                },
            )).id

            eval_results = asyncio.run(
                evaluate_response(eval_provider, task, result_text, config.eval.judges)
            )

            # Calculate average score
            scores = []
            feedback_parts = []
            for judge_name, result in eval_results.items():
                if result is None:
                    console.print(f"  [yellow]{judge_name}:[/] evaluation failed")
                    continue
                overall = result.get("overall", 0)
                tier = result.get("tier", _determine_tier(overall))
                color = _tier_color(tier)
                rationale = result.get("rationale", "")
                scores.append(overall)
                feedback_parts.append(f"**{judge_name.title()} Judge** ({overall:.1f}/10, {tier}): {rationale}")
                console.print(f"  [{color}]{judge_name}:[/] {overall:.1f}/10 ({tier})")

            if scores:
                avg_score = sum(scores) / len(scores)
                passed = avg_score >= eval_threshold

                # Track score progression for learning
                eval_scores.append(avg_score)

                # Emit eval completed event (feeds trust profiles)
                spine.emit(Event(
                    type=EVAL_COMPLETED,
                    agent=agent_name,
                    correlation_id=eval_correlation_id,
                    data={
                        "results": {k: v for k, v in eval_results.items() if v is not None},
                        "all_passed": passed,
                        "average_score": round(avg_score, 1),
                        "threshold": eval_threshold,
                        "attempt": attempt,
                        "improvement": round(avg_score - eval_scores[-2], 1) if len(eval_scores) > 1 else None,
                    },
                ))

                if passed:
                    console.print()
                    console.print(f"[bold green]✓ PASS[/] Average: {avg_score:.1f}/10 (threshold: {eval_threshold})")

                    # Show improvement if this was a retry
                    if len(eval_scores) > 1:
                        delta = avg_score - eval_scores[0]
                        console.print(f"[dim]Improved {delta:+.1f} from first attempt ({eval_scores[0]:.1f} → {avg_score:.1f})[/]")

                    # Persist learning to memory if --learn
                    if learn and len(eval_scores) > 1:
                        _persist_learning(agent_dir, task, eval_scores, feedback_parts)
                        console.print("[dim]Reflection saved to memory.md[/]")

                    break  # Success — exit retry loop
                else:
                    console.print()
                    console.print(f"[bold red]✗ FAIL[/] Average: {avg_score:.1f}/10 (threshold: {eval_threshold})")

                    if attempt < max_attempts:
                        # Build reflection context for next attempt
                        reflection_context = (
                            f"Score: {avg_score:.1f}/10 (below threshold {eval_threshold})\n\n"
                            + "\n\n".join(feedback_parts)
                        )
                    else:
                        console.print(f"[dim]All {retries} retries exhausted.[/]")

                        # Even on final failure, persist what was learned if --learn
                        if learn:
                            _persist_learning(agent_dir, task, eval_scores, feedback_parts)
                            console.print("[dim]Reflection saved to memory.md[/]")

                        raise SystemExit(1)
            else:
                console.print("[yellow]All judges failed — cannot evaluate. Keeping result.[/]")
                break
        else:
            break  # No eval, single run


def _persist_learning(agent_dir: Path, task: str, eval_scores: list[float], feedback_parts: list[str]):
    """Append reflection insights to agent memory after eval-retry cycle.

    Records what was learned from the evaluation feedback so the agent
    improves on similar tasks in future sessions.
    """
    memory_path = agent_dir / "memory.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [f"\n\n## Reflection — {timestamp}\n"]
    lines.append(f"**Task:** {task[:200]}{'...' if len(task) > 200 else ''}\n")

    if len(eval_scores) > 1:
        trajectory = " → ".join(f"{s:.1f}" for s in eval_scores)
        delta = eval_scores[-1] - eval_scores[0]
        lines.append(f"**Score trajectory:** {trajectory} ({delta:+.1f})\n")

        if eval_scores[-1] >= eval_scores[0]:
            lines.append("**What improved:** Addressed judge feedback through reflection and retry.\n")
        else:
            lines.append("**Note:** Score did not improve despite retries.\n")
    else:
        lines.append(f"**Score:** {eval_scores[0]:.1f}\n")

    # Extract the most actionable feedback
    if feedback_parts:
        lines.append("**Key feedback:**\n")
        for part in feedback_parts:
            lines.append(f"- {part}\n")

    content = "".join(lines)

    if memory_path.exists():
        existing = memory_path.read_text()
        memory_path.write_text(existing + content)
    else:
        memory_path.write_text(f"# Memory\n{content}")


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
