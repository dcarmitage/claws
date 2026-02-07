# Plan: claws v2 Phase 3 — Curriculum-Based Agent Onboarding

## Context

Phase 2 (completed 2026-02-06) delivered `claws evaluate`, trust profiles, and 150 tests.
Phase 3 adds **curriculum-based onboarding** — agents get a structured training program at
creation, work through it autonomously, and emerge with populated identity, real trust scores,
and unique personality.

### Design Sources
- **Codebase map**: Full agent lifecycle analysis (creation → run → evaluate → trust)
- **Pattern research**: Voyager skill library, Generative Agents memory-driven personality,
  roguelike trait pools, Bloom's taxonomy progression, spaced repetition, RL curriculum learning
- **System architecture**: Detailed design for curriculum YAML, onboarding engine, personality
  system, state management, CLI commands

### Key Design Decisions
1. **Constrained trait pools** (not free-form generation) — 5 trait categories with 3-5 options
   each produce 405+ personality combinations. Predictable yet diverse.
2. **Write to existing files** — Onboarding populates `identity.md` and `memory.md` directly.
   No changes needed to `claws run`. Zero new agent-visible files.
3. **Reuse eval system** — Onboarding tasks are evaluated by the same dual-judge system.
   Trust scores accumulate during onboarding. The agent graduates with a real trust profile.
4. **State file for resumability** — `.onboarding/state.yaml` per agent tracks progress.
   Ctrl+C saves state; `--resume` picks up where it left off.
5. **Curriculum inheritance** — Specialized curricula extend `default` and override phases.
   Users write domain curricula without repeating foundation tasks.
6. **Reflect-on-failure** — Failed tasks trigger a reflection prompt before retry. The
   reflection gets written to memory. Even failures teach.

## Pre-flight

Before dispatching, the lead must:
1. Verify Phase 2 is clean: `source /home/clawd/.venv/bin/activate && cd /home/clawd && python -m pytest tests/ -v`
2. Verify `claws evaluate` works: `cd /tmp && rm -rf onboard-preflight && claws init onboard-preflight && cd onboard-preflight && claws agent create t --role test && claws run t "say hello" && claws evaluate t && cd /tmp && rm -rf onboard-preflight`

## Agents

### data-layer: Curriculum Data Layer

**Creates:**
- src/claws/onboarding/__init__.py
- src/claws/onboarding/curriculum_loader.py
- src/claws/onboarding/personality.py
- src/claws/onboarding/state.py
- src/claws/templates/curricula/default.yaml
- src/claws/templates/curricula/pools/summarization_docs.yaml
- src/claws/templates/curricula/pools/critique_drafts.yaml
- src/claws/templates/curricula/pools/constrained_tasks.yaml
- src/claws/templates/curricula/pools/general_tasks.yaml
- src/claws/templates/curricula/pools/general_edge_cases.yaml
- src/claws/templates/curricula/pools/general_capstone.yaml
- tests/test_curriculum_loader.py
- tests/test_personality.py
- tests/test_onboarding_state.py

**Modifies:** (none)
**Depends on:** nothing

Build the data layer for the onboarding system. Read the existing codebase first to understand conventions (especially `src/claws/config.py` for dataclass patterns, `src/claws/events.py` for data structures, and `src/claws/templates/` for template conventions).

#### curriculum_loader.py

Parse curriculum YAML files with inheritance support. Key structures:

```python
@dataclass
class TaskDef:
    id: str                          # e.g. "f01"
    name: str                        # e.g. "Self-introduction"
    template: str                    # prompt template with {agent_name}, {agent_role}, {project_name}, {scenario}, {constraints}
    scenario_pool: str | None = None # pool name for random scenario selection
    eval_focus: str | None = None    # hint for judges about what to prioritize
    writes_to: str | None = None     # "identity", "memory", "both", or None

@dataclass
class PhaseDef:
    name: str                        # "foundation", "domain", "capstone"
    description: str
    tasks: list[TaskDef]
    gate: GateDef                    # min_passed, min_avg_score

@dataclass
class GateDef:
    min_passed: int
    min_avg_score: float = 7.5

@dataclass
class TraitPool:
    pick: int = 1                    # how many to select
    pool: list[str]                  # trait descriptions

@dataclass
class ReflectionDef:
    phase: str                       # which phase triggers this
    after_task: int                  # run after completing N tasks in this phase
    prompt: str                      # the reflection prompt

@dataclass
class PersonalityDef:
    traits: dict[str, TraitPool]     # category -> pool
    reflections: list[ReflectionDef]
    temperature_offset: float = 0.15
    seed: int | None = None          # for reproducible personality

@dataclass
class CurriculumDef:
    name: str
    version: int = 1
    extends: str | None = None       # parent curriculum name
    description: str = ""
    target_role: str | None = None
    defaults: dict = field(...)      # eval_threshold, max_retries, retry_strategy
    personality: PersonalityDef
    phases: list[PhaseDef]
```

Key functions:
- `load_curriculum(name: str, search_paths: list[Path]) -> CurriculumDef` — load from YAML, resolve inheritance by merging parent phases. Search paths: project `curricula/` dir first, then package `templates/curricula/`.
- `resolve_inheritance(child: CurriculumDef, parent: CurriculumDef) -> CurriculumDef` — merge: child phases override parent phases by name. Personality is fully replaced if child defines it.
- `list_curricula(search_paths: list[Path]) -> list[str]` — find all .yaml files in search paths.

#### personality.py

Trait selection and reflection handling. Key functions:

- `select_traits(personality: PersonalityDef, seed: int | None = None) -> dict[str, str]` — for each trait category, randomly pick `pool.pick` items. If seed is provided, use `random.Random(seed)` for determinism.
- `format_traits_for_identity(traits: dict[str, str]) -> str` — render traits as markdown for injection into identity.md.
- `get_reflection_prompt(personality: PersonalityDef, phase: str, tasks_completed: int) -> str | None` — check if any reflection is due (matching phase and after_task count). Return the prompt or None.

#### state.py

Onboarding state persistence. Key structures:

```python
@dataclass
class TaskState:
    id: str
    status: str = "pending"          # pending, in_progress, passed, failed, skipped
    attempts: int = 0
    max_retries: int = 2
    scores: list[float] = field(...)  # score from each attempt
    scenario: str | None = None       # the sampled scenario (for reproducibility)
    reflection: str | None = None     # failure reflection text

@dataclass
class PhaseState:
    name: str
    status: str = "pending"          # pending, in_progress, passed, failed
    tasks: list[TaskState] = field(...)

@dataclass
class OnboardingState:
    agent: str
    curriculum: str
    status: str = "pending"          # pending, in_progress, completed, failed
    seed: int | None = None
    traits: dict[str, str] = field(...)  # selected traits
    phases: list[PhaseState] = field(...)
    current_phase: int = 0
    current_task: int = 0

    @classmethod
    def load(cls, state_path: Path) -> OnboardingState: ...
    def save(self, state_path: Path): ...
    def next_task(self) -> tuple[int, int] | None: ...  # (phase_idx, task_idx) or None if done
```

State files use YAML format at `agents/<name>/.onboarding/state.yaml`.

#### default.yaml

Write the complete default curriculum. Use the design from the system architect's report. Include:
- 5 personality trait categories (cognitive_style, communication, risk_posture, work_ethic) with 3-5 options each
- 3 reflection prompts (one per phase)
- 3 phases: foundation (4 tasks), domain (3 tasks), capstone (1 task)
- Gates: foundation needs 3/4 passed avg 7.5, domain needs 2/3 passed avg 7.5, capstone needs 1/1 passed avg 8.0
- Task templates use `{agent_name}`, `{agent_role}`, `{project_name}`, `{scenario}`, `{constraints}` placeholders

#### Scenario pool files

Each pool is a YAML file with a list of scenarios. Minimum 5 scenarios per pool. Keep scenarios substantive (2-4 paragraphs each) — they need to be rich enough for meaningful evaluation. The pool files are:
- `summarization_docs.yaml` — documents for analysis tasks (articles, reports, proposals)
- `critique_drafts.yaml` — flawed drafts for error detection (contain planted mistakes)
- `constrained_tasks.yaml` — tasks with specific constraints (word limits, format requirements, tone rules)
- `general_tasks.yaml` — role-neutral domain tasks (fallback for unknown roles)
- `general_edge_cases.yaml` — ambiguous or underspecified tasks
- `general_capstone.yaml` — synthesis tasks combining multiple skills

Each pool file structure:
```yaml
pool_name: "summarization_docs"
scenarios:
  - |
    <scenario text>
  - |
    <scenario text>
  ...
```

For `constrained_tasks.yaml`, each entry has `constraints` and `scenario` keys.

#### Tests

Write pytest tests covering:
- curriculum_loader: YAML parsing, inheritance resolution, missing parent, circular inheritance detection, curriculum listing
- personality: trait selection determinism with seed, trait formatting, reflection trigger logic
- state: save/load round-trip, next_task progression, state transitions

Use `tmp_path` fixtures. No external dependencies. Gate: `python -m pytest tests/test_curriculum_loader.py tests/test_personality.py tests/test_onboarding_state.py -v` all green.

### eval-refactor: Extract Shared Evaluation Logic

**Creates:**
- src/claws/evaluation.py
- tests/test_evaluation.py

**Modifies:**
- src/claws/commands/evaluate.py (change to import from evaluation.py)

**Depends on:** nothing

Extract the reusable evaluation logic from `commands/evaluate.py` into a shared module `evaluation.py` that both the evaluate command and the onboarding engine can use.

Read `src/claws/commands/evaluate.py` first. The following functions should be moved to `src/claws/evaluation.py`:
- `_load_prompt(judge_name)` — load judge prompt template
- `_extract_json(text)` — extract JSON from LLM response
- `_determine_tier(score)` — score to tier mapping
- `_tier_color(tier)` — tier to Rich color
- `_parse_output_file(content)` — parse task/response from output file
- `_run_judge(provider, judge_name, task, response)` — run a single judge evaluation

Plus add a new high-level function:
```python
async def evaluate_response(
    provider,
    task: str,
    response: str,
    judges: list[str] = None,
) -> dict[str, dict | None]:
    """Run judges on a task/response pair and return results dict.

    Returns: {judge_name: {scores, overall, tier, rationale} | None}
    """
```

This function encapsulates the judge-running loop without any CLI, event, or display logic.

Then update `commands/evaluate.py` to import from `evaluation.py` instead of defining these functions inline. The evaluate CLI command should still work identically — this is a pure refactor with no behavior change.

Tests for `evaluation.py`:
- `_extract_json`: valid JSON, JSON in markdown fence, JSON with preamble, no JSON, nested JSON
- `_determine_tier`: boundary cases (9.0, 7.0, 5.0, 4.9)
- `_parse_output_file`: standard format, no Response marker, empty content
- `evaluate_response`: mock provider, verify judge calls and result structure

Also run existing tests to verify no regression: `python -m pytest tests/test_evaluate.py -v`

Gate: `python -m pytest tests/test_evaluation.py tests/test_evaluate.py -v` all green.

### engine-and-cli: Onboarding Engine + CLI Commands

**Creates:**
- src/claws/onboarding/engine.py
- src/claws/commands/onboard.py
- src/claws/commands/curriculum.py
- tests/test_onboarding_engine.py
- tests/test_onboard_command.py
- tests/test_curriculum_command.py

**Modifies:**
- src/claws/cli.py (register curriculum command group)
- src/claws/events.py (add 6 onboarding event type constants)
- src/claws/commands/agent.py (add --onboard flag to create, add onboard subcommand)
- src/claws/config.py (add OnboardingConfig dataclass and parsing)
- src/claws/__init__.py (version bump 2.0.0a2 to 2.0.0a3)
- pyproject.toml (version bump 2.0.0a2 to 2.0.0a3)

**Depends on:** data-layer, eval-refactor

Build the onboarding engine and wire everything into the CLI. Read ALL existing source files first — especially `commands/agent.py`, `commands/evaluate.py`, `config.py`, `events.py`, `cli.py`, `trust.py`, and the data-layer files created by the previous agent.

#### engine.py — OnboardingEngine class

The engine drives an agent through a curriculum. It does NOT shell out to `claws run` or `claws evaluate`. It imports providers and evaluation functions directly.

```python
class OnboardingEngine:
    def __init__(self, project_root: Path, agent_name: str, curriculum_name: str = "default",
                 seed: int | None = None, resume: bool = False):
        ...

    async def run(self) -> OnboardingState:
        """Execute the full onboarding curriculum. Returns final state."""
        ...
```

Engine flow:
1. Load curriculum via `curriculum_loader.load_curriculum()`
2. Load or create `OnboardingState`
3. If new: select personality traits via `personality.select_traits()`
4. Write selected traits to agent's `identity.md` (append a "Personality" section)
5. Emit `ONBOARD_STARTED` event
6. For each phase:
   a. Emit `ONBOARD_PHASE_STARTED` event
   b. For each task in phase:
      - Sample scenario from pool (if scenario_pool specified). Load pool YAML, pick random item using seed-derived RNG.
      - Render task template with substitutions: `{agent_name}`, `{agent_role}`, `{project_name}`, `{scenario}`, `{constraints}`
      - Build message list: system prompt = agent's current `identity.md` + `memory.md` (same as `claws run`)
      - Call `provider.complete()` with temperature = base + personality.temperature_offset
      - Save response to `agents/<name>/output/onboard-<task_id>-<attempt>.md` (same format as `claws run`)
      - Emit `TASK_STARTED` and `TASK_COMPLETED` events (reuse existing types)
      - Evaluate via `evaluation.evaluate_response()` (from the refactored module)
      - Emit `EVAL_STARTED` and `EVAL_COMPLETED` events
      - If score >= threshold: mark task passed
      - If score < threshold and retries remain: trigger reflection, write to memory.md, retry
      - If score < threshold and no retries: mark task failed
      - Emit `ONBOARD_TASK_COMPLETED` event with pass/fail
      - Check for pending reflections via `personality.get_reflection_prompt()`. If due, run reflection as a provider call, write response to identity.md.
      - Update and save state after each task
   c. Check phase gate: count passed tasks, compute average. If gate met, emit `ONBOARD_PHASE_COMPLETED`. If not, mark phase failed.
   d. If phase failed, stop onboarding.
7. After all phases pass, write graduation summary to identity.md and memory.md
8. Emit `ONBOARD_COMPLETED` event
9. Display Rich summary of results

The engine should display live progress during execution (like the system architect designed):
```
Onboarding scout [default curriculum]
Seed: 847291

Personality:
  Cognitive style: adversarial
  Communication:   concise
  Risk posture:    pragmatic
  Work ethic:      efficient

Phase 1/3: Foundation
  [PASS] f01 Self-introduction           8.7/10  (1 attempt)
  [PASS] f02 Document analysis           9.1/10  (1 attempt)
  [    ] f03 Error detection             running...
```

#### New event types (add to events.py)

```python
ONBOARD_STARTED = "onboard.started"
ONBOARD_PHASE_STARTED = "onboard.phase.started"
ONBOARD_TASK_COMPLETED = "onboard.task.completed"
ONBOARD_TASK_FAILED = "onboard.task.failed"
ONBOARD_PHASE_COMPLETED = "onboard.phase.completed"
ONBOARD_COMPLETED = "onboard.completed"
```

#### commands/onboard.py

The `claws agent onboard` subcommand:

```
claws agent onboard <name> [--curriculum <name>] [--resume] [--seed <int>]
```

- Validates agent exists, project exists
- If `--resume`, loads existing state and continues
- If agent already completed onboarding and no `--force`, error
- Instantiates and runs OnboardingEngine
- Exits 0 on success, 1 on failure

#### commands/curriculum.py

A Click command group with three subcommands:

```
claws curriculum list           # list available curricula
claws curriculum show <name>    # display phases, tasks, trait pools
claws curriculum create <name>  # scaffold a new curriculum YAML
```

- `list`: Search package templates + project `curricula/` dir
- `show`: Load curriculum, display as Rich table (phases, tasks, gates)
- `create`: Write a template YAML file to `curricula/<name>.yaml` with comments

#### Agent command modifications (agent.py)

Add `--onboard` option to `claws agent create`:
```python
@click.option("--onboard", "onboard_curriculum", default=None, is_flag=False, flag_value="default",
              help="Onboard agent with curriculum (default: 'default')")
```

When `--onboard` is provided, after creating the agent, automatically invoke the onboarding engine.

Add `onboard` as a subcommand of the `agent` group:
```python
@agent.command()
@click.argument("name")
@click.option("--curriculum", default="default")
@click.option("--resume", is_flag=True)
@click.option("--seed", type=int, default=None)
def onboard(name, curriculum, resume, seed):
    ...
```

#### Config modifications (config.py)

Add OnboardingConfig dataclass:
```python
@dataclass
class OnboardingConfig:
    default_curriculum: str = "default"
    auto_onboard: bool = False
```

Add `onboarding: OnboardingConfig` field to `ProjectConfig`. Parse from claws.yaml `onboarding:` section.

#### CLI registration (cli.py)

Import and register `curriculum` command group:
```python
from claws.commands.curriculum import curriculum
main.add_command(curriculum)
```

#### Version bump

Bump `__version__` in `src/claws/__init__.py` and `version` in `pyproject.toml` from `2.0.0a2` to `2.0.0a3`.

#### Tests

Write comprehensive tests using Click's CliRunner, tmp_path fixtures, and mocked providers:
- test_onboarding_engine: mock provider responses, verify task progression, phase gating, reflection triggers, state save/resume, personality injection into identity.md, memory.md updates, event emission
- test_onboard_command: CLI invocation, error cases (no agent, already onboarded), --resume flag
- test_curriculum_command: list, show, create subcommands

Gate: `source /home/clawd/.venv/bin/activate && cd /home/clawd && python -m pytest tests/ -v` all green.

## Verification

Run in a fresh temp directory:
```bash
cd /tmp && rm -rf e2e-onboard
source /home/clawd/.venv/bin/activate
pip install -e "/home/clawd[dev,anthropic]"
claws init e2e-onboard && cd e2e-onboard
claws curriculum list
claws curriculum show default
claws agent create scout --role researcher --onboard
# Scout should go through full onboarding, display live progress
claws agent info scout
# Should show populated identity, trust profile from onboarding evals, onboarding status
claws agent list
# Should show scout with trust score
claws status
# Should show onboarding events in activity feed
claws --version
# Should be 2.0.0a3
cd /home/clawd && python -m pytest tests/ -v
# All tests pass
```

Expected:
- `claws --version` shows 2.0.0a3
- `claws curriculum list` shows "default"
- `claws curriculum show default` displays phases, tasks, gates, trait pools
- `claws agent create scout --role researcher --onboard` runs full onboarding with live progress
- Scout's `identity.md` has personality traits and reflection responses
- Scout's `memory.md` has task learnings and heuristics from onboarding
- Trust profile shows scores from onboarding evaluations
- All tests pass (existing 150 + new onboarding tests)
