"""Onboarding Engine — drives an agent through a curriculum.

The engine executes tasks from a curriculum, evaluates responses via
judge prompts, handles retries with reflection, and tracks state
for resumability. It imports providers and evaluation functions
directly rather than shelling out to CLI commands.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from claws.config import find_project_root, load_config
from claws.evaluation import evaluate_response
from claws.events import (
    EventSpine,
    Event,
    TASK_STARTED,
    TASK_COMPLETED,
    EVAL_STARTED,
    EVAL_COMPLETED,
    ONBOARD_STARTED,
    ONBOARD_PHASE_STARTED,
    ONBOARD_TASK_COMPLETED,
    ONBOARD_TASK_FAILED,
    ONBOARD_PHASE_COMPLETED,
    ONBOARD_COMPLETED,
)
from claws.onboarding.curriculum_loader import (
    CurriculumDef,
    PhaseDef,
    TaskDef,
    load_curriculum,
)
from claws.onboarding.personality import (
    select_traits,
    format_traits_for_identity,
    get_reflection_prompt,
)
from claws.onboarding.state import OnboardingState, PhaseState, TaskState
from claws.providers import get_provider, Message

console = Console()

PACKAGE_CURRICULA = Path(__file__).parent.parent / "templates" / "curricula"


class OnboardingEngine:
    """Drives an agent through a curriculum-based onboarding process."""

    def __init__(
        self,
        project_root: Path,
        agent_name: str,
        curriculum_name: str = "default",
        seed: int | None = None,
        resume: bool = False,
    ):
        self.project_root = project_root
        self.agent_name = agent_name
        self.curriculum_name = curriculum_name
        self.seed = seed
        self.resume = resume

        self.config = load_config(project_root)
        self.spine = EventSpine(project_root)
        self.agent_dir = project_root / "agents" / agent_name
        self.state_dir = self.agent_dir / ".onboarding"
        self.state_path = self.state_dir / "state.yaml"
        self.output_dir = self.agent_dir / "output"

        # Search paths: project-local first, then package templates
        self.search_paths = [
            project_root / "curricula",
            PACKAGE_CURRICULA,
        ]

    async def run(self) -> OnboardingState:
        """Execute the full onboarding curriculum. Returns final state."""
        # Load curriculum
        curriculum = load_curriculum(self.curriculum_name, self.search_paths)

        # Load or create state
        if self.resume and self.state_path.exists():
            state = OnboardingState.load(self.state_path)
        else:
            state = self._create_initial_state(curriculum)

        # Resolve provider
        agent_cfg = self.config.agents.get(self.agent_name)
        provider_name = agent_cfg.provider if agent_cfg else "default"
        provider_cfg = self.config.providers.get(provider_name)
        if provider_cfg is None:
            console.print(f"[red]Error:[/] Provider '{provider_name}' not found in claws.yaml.")
            raise SystemExit(1)

        provider = get_provider(provider_cfg)

        # Determine temperature offset
        temp_offset = 0.0
        if curriculum.personality:
            temp_offset = curriculum.personality.temperature_offset

        # If new, select personality traits
        if not state.traits and curriculum.personality:
            effective_seed = self.seed or state.seed
            state.traits = select_traits(curriculum.personality, effective_seed)

            # Write traits to identity.md
            identity_path = self.agent_dir / "identity.md"
            if identity_path.exists():
                identity_content = identity_path.read_text()
            else:
                identity_content = ""
            trait_section = format_traits_for_identity(state.traits)
            if trait_section:
                identity_content = identity_content.rstrip() + "\n\n" + trait_section
                identity_path.write_text(identity_content)

        # Emit start event
        state.status = "in_progress"
        self.spine.emit(Event(
            type=ONBOARD_STARTED,
            agent=self.agent_name,
            data={
                "curriculum": self.curriculum_name,
                "seed": state.seed,
                "traits": state.traits,
            },
        ))

        # Pre-flight summary
        total_tasks = sum(len(p.tasks) for p in curriculum.phases)
        console.print()
        console.print(f"Starting onboarding: {total_tasks} tasks across {len(curriculum.phases)} phases (~5-7 minutes)")
        console.print(f"Curriculum: {self.curriculum_name} | Preview: claws curriculum show {self.curriculum_name}")
        console.print()

        # Print header
        console.print(f"[bold]Onboarding {self.agent_name}[/] [{self.curriculum_name} curriculum]")
        console.print(f"Seed: {state.seed}")
        if state.traits:
            console.print()
            console.print("[bold]Personality:[/]")
            for category, trait in state.traits.items():
                label = category.replace("_", " ").title()
                # Truncate to just the trait name (before the dash)
                short = trait.split(" — ")[0] if " — " in trait else trait
                console.print(f"  {label + ':':<20s} {short}")

        # Process phases
        all_passed = True
        for phase_idx, phase_def in enumerate(curriculum.phases):
            if phase_idx < state.current_phase:
                # Already completed in a previous run
                continue

            phase_state = state.phases[phase_idx]
            if phase_state.status == "passed":
                continue

            phase_state.status = "in_progress"

            self.spine.emit(Event(
                type=ONBOARD_PHASE_STARTED,
                agent=self.agent_name,
                data={
                    "phase": phase_def.name,
                    "phase_index": phase_idx,
                },
            ))

            console.print()
            console.print(f"[bold]Phase {phase_idx + 1}/{len(curriculum.phases)}: {phase_def.name}[/]")

            # Process tasks in this phase
            tasks_completed_in_phase = 0
            for task_idx, task_def in enumerate(phase_def.tasks):
                task_state = phase_state.tasks[task_idx]

                if task_state.status == "passed":
                    tasks_completed_in_phase += 1
                    score_display = f"{task_state.scores[-1]:.1f}/10" if task_state.scores else "?"
                    focus = f" — {task_def.eval_focus}" if task_def.eval_focus else ""
                    attempts = f" ({task_state.attempts} attempts)" if task_state.attempts > 1 else ""
                    console.print(
                        f"  [green][PASS][/] {task_def.id} {task_def.name:<30s} "
                        f"{score_display}{attempts}{focus}"
                    )
                    continue

                if task_state.status == "failed" and task_state.attempts >= task_state.max_retries + 1:
                    # Exhausted retries already
                    continue

                # Compute global task number for progress display
                global_task_num = sum(
                    len(curriculum.phases[pi].tasks) for pi in range(phase_idx)
                ) + task_idx + 1

                # Run this task
                passed = await self._run_task(
                    provider, curriculum, phase_def, phase_idx, task_def, task_idx,
                    task_state, state, temp_offset,
                    total_tasks=total_tasks, global_task_num=global_task_num,
                )

                if passed:
                    tasks_completed_in_phase += 1

                # Check for pending reflections
                if curriculum.personality:
                    reflection_prompt = get_reflection_prompt(
                        curriculum.personality,
                        phase_def.name,
                        tasks_completed_in_phase,
                    )
                    if reflection_prompt:
                        await self._run_reflection(
                            provider, reflection_prompt, state, temp_offset,
                        )

                # Save state after each task
                state.current_task = task_idx + 1
                state.save(self.state_path)

            # Check phase gate
            passed_count = sum(
                1 for t in phase_state.tasks if t.status == "passed"
            )
            scores = [
                t.scores[-1] for t in phase_state.tasks
                if t.status == "passed" and t.scores
            ]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            gate_passed = (
                passed_count >= phase_def.gate.min_passed
                and avg_score >= phase_def.gate.min_avg_score
            )

            if gate_passed:
                phase_state.status = "passed"
                self.spine.emit(Event(
                    type=ONBOARD_PHASE_COMPLETED,
                    agent=self.agent_name,
                    data={
                        "phase": phase_def.name,
                        "passed": passed_count,
                        "total": len(phase_def.tasks),
                        "avg_score": round(avg_score, 2),
                    },
                ))
                console.print(
                    f"  [green]Phase gate PASSED[/]  "
                    f"{passed_count}/{len(phase_def.tasks)} tasks, avg {avg_score:.1f}"
                )
            else:
                phase_state.status = "failed"
                all_passed = False
                console.print(
                    f"  [red]Phase gate FAILED[/]  "
                    f"{passed_count}/{phase_def.gate.min_passed} required, avg {avg_score:.1f}/{phase_def.gate.min_avg_score}"
                )
                state.status = "failed"
                state.save(self.state_path)
                break

            # Advance to next phase
            state.current_phase = phase_idx + 1
            state.current_task = 0
            state.save(self.state_path)

        # Graduation
        if all_passed:
            state.status = "completed"
            self._write_graduation(state, curriculum)
            self.spine.emit(Event(
                type=ONBOARD_COMPLETED,
                agent=self.agent_name,
                data={
                    "curriculum": self.curriculum_name,
                    "status": "completed",
                },
            ))

            # Compute summary stats
            all_scores = []
            for phase in state.phases:
                for task in phase.tasks:
                    if task.scores:
                        all_scores.append(task.scores[-1])
            avg = sum(all_scores) / len(all_scores) if all_scores else 0.0

            agent_role = self._get_agent_role()
            agent_dir_rel = f"agents/{self.agent_name}"

            console.print()
            console.print(Panel.fit(
                f"[bold green]{self.agent_name} graduated![/]\n\n"
                f"  Score:     {avg:.1f}/10 across {len(all_scores)} evaluations\n"
                f"  Identity:  {agent_dir_rel}/identity.md\n"
                f"  Memory:    {agent_dir_rel}/memory.md\n\n"
                f"[bold]What to do next:[/]\n"
                f"  claws agent info {self.agent_name}              [dim]# see identity + scores[/]\n"
                f"  claws run {self.agent_name} \"<your task>\"       [dim]# give it real work[/]\n"
                f"  claws evaluate {self.agent_name}                [dim]# score the output[/]\n",
                title="Onboarding complete",
                border_style="green",
            ))
        else:
            state.status = "failed"
            self.spine.emit(Event(
                type=ONBOARD_COMPLETED,
                agent=self.agent_name,
                data={
                    "curriculum": self.curriculum_name,
                    "status": "failed",
                },
            ))
            console.print()
            console.print(
                f"[bold red]Onboarding failed.[/] {self.agent_name} did not pass all phases.\n"
                f"  Resume with: claws agent onboard {self.agent_name} --resume"
            )

        state.save(self.state_path)
        return state

    def _create_initial_state(self, curriculum: CurriculumDef) -> OnboardingState:
        """Create initial state from curriculum definition."""
        seed = self.seed if self.seed is not None else random.randint(100000, 999999)
        max_retries = curriculum.defaults.get("max_retries", 2)

        phases = []
        for phase_def in curriculum.phases:
            tasks = []
            for task_def in phase_def.tasks:
                tasks.append(TaskState(
                    id=task_def.id,
                    max_retries=max_retries,
                ))
            phases.append(PhaseState(
                name=phase_def.name,
                tasks=tasks,
            ))

        state = OnboardingState(
            agent=self.agent_name,
            curriculum=self.curriculum_name,
            seed=seed,
            phases=phases,
        )

        # Save initial state
        state.save(self.state_path)
        return state

    async def _run_task(
        self,
        provider,
        curriculum: CurriculumDef,
        phase_def: PhaseDef,
        phase_idx: int,
        task_def: TaskDef,
        task_idx: int,
        task_state: TaskState,
        state: OnboardingState,
        temp_offset: float,
        total_tasks: int = 0,
        global_task_num: int = 0,
    ) -> bool:
        """Run a single task with retries. Returns True if passed."""
        threshold = curriculum.defaults.get("eval_threshold", 8.0)
        max_retries = task_state.max_retries

        while task_state.attempts <= max_retries:
            task_state.attempts += 1
            task_state.status = "in_progress"

            progress = f"Task {global_task_num}/{total_tasks} | " if total_tasks else ""
            console.print(
                f"  [    ] {progress}{task_def.id} {task_def.name:<30s} running...",
                end="\r",
            )

            # Sample scenario from pool if specified
            scenario = ""
            constraints = ""
            if task_def.scenario_pool:
                pool_name = task_def.scenario_pool.format(
                    agent_role=self._get_agent_role(),
                )
                scenario_data = self._load_scenario_pool(pool_name, state.seed, task_state.attempts)
                if isinstance(scenario_data, dict):
                    scenario = scenario_data.get("scenario", "")
                    constraints = scenario_data.get("constraints", "")
                else:
                    scenario = scenario_data or ""
                task_state.scenario = scenario[:200] if scenario else None

            # Render task template
            prompt = task_def.template.format(
                agent_name=self.agent_name,
                agent_role=self._get_agent_role(),
                project_name=self.config.project,
                scenario=scenario,
                constraints=constraints,
            )

            # Build messages
            system_prompt = self._build_system_prompt()
            messages = []
            if system_prompt:
                messages.append(Message(role="system", content=system_prompt))
            messages.append(Message(role="user", content=prompt))

            # Emit task started event
            self.spine.emit(Event(
                type=TASK_STARTED,
                agent=self.agent_name,
                data={
                    "task": f"onboard:{task_def.id}",
                    "attempt": task_state.attempts,
                },
            ))

            # Call provider
            try:
                kwargs: dict[str, Any] = {}
                if temp_offset:
                    kwargs["temperature"] = 0.7 + temp_offset
                response = await provider.complete(messages, **kwargs)
                response_text = response.content
            except Exception as e:
                console.print(
                    f"  [red][FAIL][/] {task_def.id} {task_def.name:<30s} "
                    f"Provider error: {e}"
                )
                task_state.status = "failed"
                self.spine.emit(Event(
                    type=ONBOARD_TASK_FAILED,
                    agent=self.agent_name,
                    data={
                        "task_id": task_def.id,
                        "error": str(e),
                        "attempt": task_state.attempts,
                    },
                ))
                continue

            # Save response to output file
            self.output_dir.mkdir(parents=True, exist_ok=True)
            output_file = self.output_dir / f"onboard-{task_def.id}-{task_state.attempts}.md"
            output_content = f"# Task\n\n{prompt}\n\n# Response\n\n{response_text}\n"
            output_file.write_text(output_content)

            # Emit task completed event
            self.spine.emit(Event(
                type=TASK_COMPLETED,
                agent=self.agent_name,
                data={
                    "task": f"onboard:{task_def.id}",
                    "output_file": str(output_file.relative_to(self.project_root)),
                    "attempt": task_state.attempts,
                },
            ))

            # Evaluate response
            self.spine.emit(Event(
                type=EVAL_STARTED,
                agent=self.agent_name,
                data={"task_id": task_def.id, "attempt": task_state.attempts},
            ))

            eval_results = await evaluate_response(provider, prompt, response_text)

            # Compute average overall score from judge results
            valid_scores = [
                r.get("overall", 0.0)
                for r in eval_results.values()
                if r is not None
            ]
            avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

            self.spine.emit(Event(
                type=EVAL_COMPLETED,
                agent=self.agent_name,
                data={
                    "task_id": task_def.id,
                    "results": {
                        k: v for k, v in eval_results.items() if v is not None
                    },
                    "avg_score": round(avg_score, 2),
                    "attempt": task_state.attempts,
                },
            ))

            task_state.scores.append(round(avg_score, 2))

            if avg_score >= threshold:
                task_state.status = "passed"
                self.spine.emit(Event(
                    type=ONBOARD_TASK_COMPLETED,
                    agent=self.agent_name,
                    data={
                        "task_id": task_def.id,
                        "score": round(avg_score, 2),
                        "attempts": task_state.attempts,
                        "status": "passed",
                    },
                ))
                attempts = f" ({task_state.attempts} attempts)" if task_state.attempts > 1 else ""
                console.print(
                    f"  [green][PASS][/] {task_def.id} {task_def.name:<30s} "
                    f"{avg_score:.1f}/10{attempts}"
                )
                summary = self._summary_line(response_text)
                console.print(f"         [dim]→ {summary}[/]")

                # Write to memory/identity if specified
                self._write_task_output(task_def, response_text, avg_score)
                return True
            else:
                # Below threshold
                if task_state.attempts <= max_retries:
                    # Trigger reflection before retry
                    reflection_text = await self._generate_retry_reflection(
                        provider, prompt, response_text, eval_results, temp_offset,
                    )
                    task_state.reflection = reflection_text
                    # Write reflection to memory.md
                    self._append_to_memory(
                        f"### Reflection on {task_def.id} (attempt {task_state.attempts})\n\n{reflection_text}"
                    )
                    console.print(
                        f"  [yellow][RETRY][/] {task_def.id} {task_def.name:<30s} "
                        f"{avg_score:.1f}/10  — reflecting and retrying..."
                    )
                    summary = self._summary_line(response_text)
                    console.print(f"         [dim]→ {summary}[/]")
                else:
                    task_state.status = "failed"
                    self.spine.emit(Event(
                        type=ONBOARD_TASK_FAILED,
                        agent=self.agent_name,
                        data={
                            "task_id": task_def.id,
                            "score": round(avg_score, 2),
                            "attempts": task_state.attempts,
                            "status": "failed",
                        },
                    ))
                    console.print(
                        f"  [red][FAIL][/] {task_def.id} {task_def.name:<30s} "
                        f"{avg_score:.1f}/10  ({task_state.attempts} attempts)"
                    )
                    summary = self._summary_line(response_text)
                    console.print(f"         [dim]→ {summary}[/]")
                    return False

        return False

    @staticmethod
    def _summary_line(text: str, max_len: int = 90) -> str:
        """Extract the first substantive line from a response for display."""
        for line in text.strip().split("\n"):
            stripped = line.strip()
            # Skip headings, blank lines, and very short lines
            if not stripped or stripped.startswith("#") or len(stripped) < 15:
                continue
            # Skip common preamble patterns
            if stripped.lower().startswith(("here is", "here's", "sure,", "certainly")):
                continue
            if len(stripped) > max_len:
                return stripped[:max_len - 3] + "..."
            return stripped
        # Fallback: first N chars of the whole text
        flat = text.strip().replace("\n", " ")[:max_len]
        return flat + "..." if len(text.strip()) > max_len else flat

    def _get_agent_role(self) -> str:
        """Get the agent's role from config."""
        agent_cfg = self.config.agents.get(self.agent_name)
        return agent_cfg.role if agent_cfg else "general"

    def _build_system_prompt(self) -> str:
        """Build system prompt from identity.md + memory.md."""
        system_prompt = ""
        identity_path = self.agent_dir / "identity.md"
        if identity_path.exists():
            system_prompt = identity_path.read_text()

        memory_path = self.agent_dir / "memory.md"
        if memory_path.exists():
            memory = memory_path.read_text()
            if memory.strip():
                system_prompt += f"\n\n---\n\n# Your Memory\n{memory}"

        return system_prompt

    def _load_scenario_pool(
        self, pool_name: str, seed: int | None, attempt: int
    ) -> str | dict:
        """Load and sample from a scenario pool.

        Checks project curricula/pools/ first, then package templates/curricula/pools/.
        Returns a scenario string or dict (for constrained_tasks with constraints key).
        """
        pool_search_paths = [
            self.project_root / "curricula" / "pools",
            PACKAGE_CURRICULA / "pools",
        ]

        pool_data = None
        for base in pool_search_paths:
            pool_file = base / f"{pool_name}.yaml"
            if pool_file.exists():
                with open(pool_file) as f:
                    pool_data = yaml.safe_load(f)
                break

        if pool_data is None or "scenarios" not in pool_data:
            return ""

        scenarios = pool_data["scenarios"]
        if not scenarios:
            return ""

        # Use seed-derived RNG for deterministic sampling
        effective_seed = (seed or 0) + attempt
        rng = random.Random(effective_seed)
        return rng.choice(scenarios)

    def _write_task_output(self, task_def: TaskDef, response_text: str, score: float):
        """Write task results to identity.md or memory.md based on writes_to."""
        if not task_def.writes_to:
            return

        summary = f"### {task_def.name} (score: {score:.1f}/10)\n\n{response_text[:500]}"
        if len(response_text) > 500:
            summary += "...\n"

        if task_def.writes_to in ("memory", "both"):
            self._append_to_memory(summary)

        if task_def.writes_to in ("identity", "both"):
            identity_path = self.agent_dir / "identity.md"
            if identity_path.exists():
                content = identity_path.read_text()
            else:
                content = ""
            content = content.rstrip() + "\n\n" + summary + "\n"
            identity_path.write_text(content)

    def _append_to_memory(self, text: str):
        """Append text to the agent's memory.md."""
        memory_path = self.agent_dir / "memory.md"
        if memory_path.exists():
            content = memory_path.read_text()
        else:
            content = ""
        content = content.rstrip() + "\n\n" + text + "\n"
        memory_path.write_text(content)

    async def _generate_retry_reflection(
        self,
        provider,
        task_prompt: str,
        response_text: str,
        eval_results: dict,
        temp_offset: float,
    ) -> str:
        """Generate a reflection on a failed task to help with retry."""
        # Summarize feedback from judges
        feedback_parts = []
        for judge_name, result in eval_results.items():
            if result is not None:
                rationale = result.get("rationale", "No rationale provided.")
                overall = result.get("overall", 0)
                feedback_parts.append(f"{judge_name}: {overall:.1f}/10 - {rationale}")

        feedback = "\n".join(feedback_parts) if feedback_parts else "No evaluation feedback available."

        reflection_prompt = (
            f"You attempted the following task and scored below the threshold.\n\n"
            f"Task: {task_prompt[:500]}\n\n"
            f"Your response (first 500 chars): {response_text[:500]}\n\n"
            f"Evaluation feedback:\n{feedback}\n\n"
            f"Reflect briefly on what went wrong and how you would approach it differently. "
            f"Be specific. Two sentences maximum."
        )

        messages = [
            Message(role="user", content=reflection_prompt),
        ]

        try:
            kwargs: dict[str, Any] = {}
            if temp_offset:
                kwargs["temperature"] = 0.7 + temp_offset
            result = await provider.complete(messages, **kwargs)
            return result.content.strip()
        except Exception:
            return "Unable to generate reflection."

    async def _run_reflection(
        self,
        provider,
        reflection_prompt: str,
        state: OnboardingState,
        temp_offset: float,
    ):
        """Run a scheduled personality reflection."""
        system_prompt = self._build_system_prompt()
        messages = []
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))
        messages.append(Message(role="user", content=reflection_prompt))

        try:
            kwargs: dict[str, Any] = {}
            if temp_offset:
                kwargs["temperature"] = 0.7 + temp_offset
            result = await provider.complete(messages, **kwargs)
            reflection_text = result.content.strip()

            # Write reflection to identity.md
            identity_path = self.agent_dir / "identity.md"
            if identity_path.exists():
                content = identity_path.read_text()
            else:
                content = ""
            content = content.rstrip() + "\n\n## Reflection\n\n" + reflection_text + "\n"
            identity_path.write_text(content)

            console.print(f"  [dim]Reflection recorded.[/]")
        except Exception:
            console.print(f"  [yellow]Warning:[/] Reflection failed.")

    def _write_graduation(self, state: OnboardingState, curriculum: CurriculumDef):
        """Write graduation summary to identity.md and memory.md."""
        # Collect all scores
        all_scores = []
        for phase in state.phases:
            for task in phase.tasks:
                if task.scores:
                    all_scores.append(task.scores[-1])

        avg = sum(all_scores) / len(all_scores) if all_scores else 0.0

        summary = (
            f"## Graduation\n\n"
            f"Completed {self.curriculum_name} curriculum. "
            f"Average score: {avg:.1f}/10 across {len(all_scores)} tasks.\n"
        )

        if state.traits:
            trait_list = ", ".join(
                f"{k}: {v.split(' — ')[0]}" if " — " in v else f"{k}: {v}"
                for k, v in state.traits.items()
            )
            summary += f"Personality: {trait_list}\n"

        # Write to identity.md
        identity_path = self.agent_dir / "identity.md"
        if identity_path.exists():
            content = identity_path.read_text()
        else:
            content = ""
        content = content.rstrip() + "\n\n" + summary
        identity_path.write_text(content)

        # Write to memory.md
        self._append_to_memory(summary)
