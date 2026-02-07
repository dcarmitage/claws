# Plan: claws v2 Phase 2 — Eval, Trust, Tests

## Pre-flight
Before dispatching, the lead must:
1. Verify `claws run` works: `cd /tmp && rm -rf smoke-test && source /home/clawd/.venv/bin/activate && claws init smoke-test && cd smoke-test && claws agent create t --role test && claws run t "say hello" && cd /tmp && rm -rf smoke-test`
2. Fix output_file in run.py to use relative paths (store relative to project root, not absolute)
3. Fix pyproject.toml to include template files as package data

## Agents

### test-writer: Test Suite Author
**Creates:**
- tests/__init__.py
- tests/conftest.py
- tests/test_config.py
- tests/test_events.py
- tests/test_init.py
- tests/test_agent.py
- tests/test_run.py
- tests/test_status.py
- tests/test_providers.py

**Modifies:** (none)
**Depends on:** nothing

Write a comprehensive pytest suite for the existing claws CLI. Use Click's CliRunner for command tests. Use tmp_path fixtures for isolated project directories. Mock httpx for provider tests. Every test file should be self-contained. Read the source files in src/claws/ to understand what to test. Cover:

- config.py: loading valid/invalid YAML, find_project_root, provider config API key resolution, EvalConfig defaults
- events.py: Event creation, serialization, EventSpine emit/read/filter/last_event
- commands/init.py: project creation, directory structure, template files, custom provider/model
- commands/agent.py: create agent, duplicate detection, list agents, agent info, config update
- commands/run.py: successful run, failed run, save/no-save, streaming vs complete mode
- commands/status.py: status display with events, empty project, agent states
- providers/: registry dispatch, anthropic provider init, openai-compat provider init

Gate: `source /home/clawd/.venv/bin/activate && cd /home/clawd && python -m pytest tests/ -v` all green.

### eval-builder: Evaluation System Builder
**Creates:**
- src/claws/templates/prompts/logic_judge.txt
- src/claws/templates/prompts/consistency_judge.txt
- src/claws/commands/evaluate.py
- tests/test_evaluate.py

**Modifies:**
- src/claws/config.py (add provider field to EvalConfig)

**Depends on:** nothing

Build the `claws evaluate` command. Design judge prompts FROM SCRATCH for evaluating text responses against task prompts (NOT code diffs — this is for evaluating agent output text quality).

Logic judge checks: claims accuracy, reasoning quality, hallucination risk, task adherence, factual grounding. Output structured JSON with scores 0-10 per dimension and overall, plus a tier (excellent/good/acceptable/poor).

Consistency judge checks: completeness vs task requirements, internal coherence, output quality, relevance, format appropriateness. Same JSON structure with scores and tier.

The evaluate command:
1. Find last TASK_COMPLETED event for the agent from Event Spine
2. Load the output file referenced in the event data
3. Parse the task prompt and response from the output file
4. Run each judge via provider.complete() with the judge prompt + task + response
5. Parse JSON from judge responses (handle LLM preamble — find first `{` to last `}`)
6. Emit EVAL_STARTED event at beginning, EVAL_COMPLETED event with scores when done
7. Display Rich formatted summary with scores, tiers, pass/fail vs threshold

Options: `--provider` (override eval provider), `--output` (save eval results to file)
Use `max_tokens=8192` for judge calls.

Handle edge cases: no completed tasks for agent, missing output file, JSON parse failure in judge response.

Gate: `source /home/clawd/.venv/bin/activate && cd /home/clawd && python -m pytest tests/test_evaluate.py -v` all green.

### trust-integrator: Trust Profiles + CLI Wiring
**Creates:**
- src/claws/trust.py
- tests/test_trust.py

**Modifies:**
- src/claws/events.py (add DEPLOY_COMPLETED event type constant)
- src/claws/commands/agent.py (add trust display in info and list commands)
- src/claws/commands/status.py (add trust column in agent table)
- src/claws/cli.py (register evaluate command)
- src/claws/__init__.py (version bump 2.0.0a1 to 2.0.0a2)
- pyproject.toml (version bump 2.0.0a1 to 2.0.0a2)

**Depends on:** eval-builder

Build trust profiles and wire everything into the CLI.

trust.py — TrustProfile class:
- Reads EVAL_COMPLETED events from EventSpine for a given agent
- Groups scores by judge type (logic, consistency)
- Computes: average score per judge, overall average, eval count, trend
- Edge cases:
  - 0 evals: trend="new", scores=None
  - 1-2 evals: trend="insufficient" data for trend
  - 3+ evals: compare last 3 avg vs overall avg. Delta > 0.5 = "improving", delta < -0.5 = "declining", else "stable"
- Method: `TrustProfile.for_agent(spine: EventSpine, agent: str) -> TrustProfile`

CLI wiring:
- agent info: Add a Rich panel showing trust profile (scores per judge, overall, trend, eval count)
- agent list: Add "Trust" column showing overall score or "new" if no evals
- status: Add "Trust" column to agent table
- cli.py: Import and register the evaluate command from commands.evaluate
- Bump version in __init__.py and pyproject.toml to 2.0.0a2

Gate: `source /home/clawd/.venv/bin/activate && cd /home/clawd && python -m pytest tests/test_trust.py -v` all green, plus `claws agent list` shows Trust column.

## Verification
Run in a fresh temp directory:
```bash
cd /tmp && rm -rf e2e-test
source /home/clawd/.venv/bin/activate
pip install -e "/home/clawd[dev,anthropic]"
claws init e2e-test && cd e2e-test
claws agent create scout --role researcher
claws run scout "Name 3 benefits of Rust"
claws evaluate scout
claws agent info scout
claws agent list
claws status
claws --version
cd /home/clawd && python -m pytest tests/ -v
```

Expected:
- `claws --version` shows 2.0.0a2
- `claws evaluate scout` runs both judges, shows scores
- `claws agent list` has a Trust column
- `claws agent info scout` shows trust panel
- All tests pass
