# Plan: claws v4 — The Simplification Build

## Pre-flight

Before dispatching agents, the lead must:
1. Activate venv: `source /home/clawd/.venv/bin/activate`
2. Verify tests pass: `python -m pytest /home/clawd/tests/ -v` (283 expected)
3. Verify on prod branch: `git -C /home/clawd branch --show-current`

## Agents

### cli-enhancements: Product Code Changes
**Creates:**
- src/claws/commands/doctor.py
- tests/test_doctor.py

**Modifies:**
- src/claws/cli.py
- src/claws/__init__.py
- src/claws/providers/registry.py
- src/claws/providers/anthropic.py
- src/claws/providers/openai_compat.py
- src/claws/onboarding/engine.py
- src/claws/commands/evaluate.py
- pyproject.toml

**Depends on:** nothing

Build these product improvements:

**1. `claws doctor` command** — New command that diagnoses setup issues.
- Check: is this a claws project? (claws.yaml exists)
- Check: is a provider configured?
- Check: is the API key available? (env var or config)
- Check: can we reach the provider? (attempt a simple completion: "Say hello")
- Output: Rich table with pass/fail per check, actionable fix message for each failure
- Register in cli.py

**2. Better error messages:**
- In `providers/registry.py`: when API key is missing, suggest specific setup steps:
  "Anthropic API key not found. Set it with: export ANTHROPIC_API_KEY=your-key\n  Get a key at: https://console.anthropic.com\n  Or run: claws doctor"
- In `providers/anthropic.py`: same pattern for connection failures
- In `providers/openai_compat.py`: similar for OpenAI-compatible provider errors

**3. CLI help epilog:**
- In `cli.py`: add epilog to the main click group: "New to claws? Start with: claws init my-project"

**4. Onboarding UX:**
- In `onboarding/engine.py`: before starting onboarding, print a pre-flight summary:
  "Starting onboarding: 8 tasks across 3 phases (~5-7 minutes)\nCurriculum: default | Preview: claws curriculum show default\n"
- Add task progress to each task: "Task 3/8 | Phase: Foundation"

**5. Post-evaluation guidance:**
- In `commands/evaluate.py`: after displaying scores, if average < threshold, add:
  "Tip: Re-run the task with: claws run <agent> \"revised prompt\"\n  Or add guidance to agents/<agent>/memory.md"

**6. Version and Python floor:**
- In `pyproject.toml`: change `requires-python` from `>=3.10` to `>=3.8`
- Bump version to 2.0.0a4 in BOTH `pyproject.toml` AND `src/claws/__init__.py`

**7. Tests:**
- Write tests for `claws doctor` (test_doctor.py): test each check pass/fail, test output format
- Existing tests must still pass (283 + new doctor tests)

Gate: `python -m pytest /home/clawd/tests/ -v` all green (283 + new tests)

### repo-restructure: Directory Cleanup and File Moves
**Creates:**
- docs/philosophy/README.md
- docs/philosophy/the-hundred-steps.md
- docs/philosophy/agent-identity-model.md
- docs/BEST_PRACTICES.md
- tools/scripts/handoff_eval.sh
- tools/scripts/session_close.sh
- tools/scripts/subtitle.py
- tools/scripts/transcribe.py
- tools/scripts/transcription_service.py

**Modifies:**
- evals/README.md
- orchestrator/README.md
- onboarding/README.md
- skills/README.md
- tools/README.md
- docs/PLATFORMS.md
- starter-kit/README.md
- CONTRIBUTING.md

**Removes (git rm):**
- evals/consistency_judge.sh
- evals/logic_judge.sh
- evals/run_dual_judge_eval.sh
- evals/run_single_judge.sh
- evals/validate_output.sh
- evals/hooks/post_task_done.py
- evals/prompts/logic_judge.txt
- evals/prompts/consistency_judge.txt
- orchestrator/build_log.py
- orchestrator/build_report.py
- orchestrator/taskboard.py
- orchestrator/templates/BRIEF.md
- orchestrator/templates/TASKBOARD.md
- onboarding/THE_HUNDRED_STEPS.md
- onboarding/SOUL_ARCHITECTURE.md
- onboarding/INFRASTRUCTURE_MAP.md
- onboarding/PERMISSIONS.md
- scripts/handoff_eval.sh
- scripts/session_close.sh
- scripts/subtitle.py
- scripts/transcribe.py
- scripts/transcription_service.py
- docs/HEURISTICS.md
- docs/PRINCIPLES.md
- orchestrator/CHECKLISTS.md

**Depends on:** nothing

Execute these changes:

**1. Archive philosophy content:**
- Create `docs/philosophy/README.md`: "Original design philosophy for claws. The ideas here inspired the current implementation. For the working system, see `claws agent onboard`."
- Copy `onboarding/THE_HUNDRED_STEPS.md` → `docs/philosophy/the-hundred-steps.md` with header: "This is the original 100-step onboarding vision. The current implementation uses YAML curricula — see `claws curriculum show default`."
- Copy `onboarding/SOUL_ARCHITECTURE.md` → `docs/philosophy/agent-identity-model.md` with header: "This is the original agent identity philosophy. The current implementation uses identity.md + personality traits — see `claws agent onboard`."
- Then git rm the originals from onboarding/

**2. Rewrite directory READMEs (each should be 1-2 pages, describing the v2 CLI feature):**

`evals/README.md` — "# Evaluation System\n\nclaws uses two-pass evaluation to assess agent output quality...\n\n## How it works\n`claws evaluate <agent>` runs two independent judges...\n\n## Judge prompts\nJudge prompts are at `src/claws/templates/prompts/`. Customize by...\n\n## Scoring\nScores 0-10, tiers: Gold (8+), Silver (6-8), Bronze (4-6), Fail (<4)..."
Then git rm all bash scripts and the evals/prompts/ directory (duplicated in src/claws/templates/prompts/).

`orchestrator/README.md` — "# Event Log & Orchestration\n\nclaws tracks all agent activity in an append-only event log...\n\n## Event log format\n`.claws/events.jsonl` — one JSON object per line...\n\n## Event types\n14 event types: AGENT_CREATED, TASK_STARTED, EVAL_COMPLETED, etc...\n\n## Viewing status\n`claws status` shows project overview..."
Then git rm the Python scripts and templates.

`onboarding/README.md` — "# Agent Onboarding\n\nclaws trains new agents through structured curricula...\n\n## Quick start\n`claws agent create scout --role researcher --onboard default`\n\n## How it works\nCurricula define phases, tasks, checkpoints, and personality traits...\n\n## Custom curricula\n`claws curriculum create my-curriculum`...\n\n## Design philosophy\nSee `docs/philosophy/` for the original vision that inspired this system."
Then git rm THE_HUNDRED_STEPS.md, SOUL_ARCHITECTURE.md, INFRASTRUCTURE_MAP.md, PERMISSIONS.md.

`skills/README.md` — "# Skills\n\nSkills are reusable agent capabilities defined as markdown files...\n\n## Active skills\n- `build-team/` — Multi-agent team dispatch\n- `learn/` — Extract patterns from work\n- `integrate/` — Wire learnings into memory\n- `save-memory/` — End-of-session capture\n- `dual-judge/` — Two-pass evaluation\n\n## Hardware examples\n- `camsnap/`, `parakeet-stt/`, `video-subtitles/` — Pi-specific integrations\n\n## Creating skills\nA skill is a SKILL.md file with YAML frontmatter..."

`tools/README.md` — "# Tools\n\nStandalone services and utilities that complement the claws CLI...\n\nThese are deployment-specific — not required to use claws.\n\n## Included tools\n- `agentchat/` — Agent-to-agent communication\n- `health-check.sh` — System health monitoring\n- `scripts/` — Utility scripts (transcription, session management)"

Move scripts/* into tools/scripts/ (create the subdirectory), then git rm scripts/.

**3. Update docs/:**
- Rename HEURISTICS.md content → create `docs/BEST_PRACTICES.md` with updated terminology. git rm HEURISTICS.md.
- Merge relevant PRINCIPLES.md content into CONTRIBUTING.md. git rm PRINCIPLES.md.
- Update PLATFORMS.md: generalize to "any machine with Python 3.8+ and a terminal." Remove Pi-specific setup instructions.

**4. Update starter-kit/README.md:**
- Replace references to "The Hundred Steps" with `claws agent onboard`
- Explain templates are auto-generated by `claws agent create`

**5. Terminology sweep across ALL files this agent owns:**
- "Event Spine" → "event log"
- "The Hundred Steps" → "onboarding curriculum"
- "Soul Architecture" → "agent identity model"
- "Trust Profile" → "evaluation history" or "agent score"
- "Dual-judge" → "two-pass"
- "Phase gate" → "checkpoint"
- "Scenario pool" → "task template"

Gate: No custom jargon in any file this agent touches. `grep -ri "event spine\|hundred steps\|soul architecture" evals/ orchestrator/ onboarding/ skills/ tools/ docs/ starter-kit/ CONTRIBUTING.md` returns nothing.

### readme-rewrite: README and Install Path
**Creates:** (none)

**Modifies:**
- README.md
- CHANGELOG.md
- AGENTS.md

**Depends on:** cli-enhancements, repo-restructure

Rewrite the main README with progressive disclosure. This agent runs LAST because it needs to reference the final directory structure and new commands.

**1. README.md — complete rewrite:**

Structure:
```
# claws — Build, train, and manage AI agents

One-line description + badge (alpha, version)

## Quick start
Prerequisites: Python 3.8+, an API key from one of:
- Anthropic (console.anthropic.com)
- OpenAI (platform.openai.com)
- OpenRouter (openrouter.ai)

pip install git+https://github.com/dcarmitage/claws.git
  (or pip install claws if on PyPI)

claws init my-project && cd my-project
# Set your API key:
export ANTHROPIC_API_KEY=your-key-here
# Verify setup:
claws doctor
# Create and train an agent:
claws agent create scout --role researcher --onboard default

## What just happened?
Explain: created agent, ran through curriculum, evaluated with two judges, built trust score.

## Commands
Full table: init, agent create/list/info/onboard, run, evaluate, status, curriculum list/show/create, doctor

## Configuration
claws.yaml examples for Anthropic, OpenAI, OpenRouter

## Project structure
What each directory is for (2-3 words each)

## Contributing
Link to CONTRIBUTING.md

## License
MIT
```

**2. CHANGELOG.md** — Add v2.0.0a4 entry with Phase 4 changes

**3. AGENTS.md** — Update with new doctor command, updated directory structure

Gate: README quick start commands are accurate. All referenced commands exist. All referenced directories exist.

## Verification

After all agents complete, the lead runs:
```bash
cd /home/clawd && source .venv/bin/activate

# Tests pass
python -m pytest tests/ -v

# Terminology check — zero matches
grep -ri "event spine\|hundred steps\|soul architecture" \
  evals/ orchestrator/ onboarding/ skills/ tools/ docs/ \
  starter-kit/ README.md AGENTS.md CONTRIBUTING.md CHANGELOG.md

# New command works
pip install -e ".[dev,anthropic]"
claws doctor --help

# Directory structure is clean
ls evals/        # should be just README.md
ls orchestrator/ # should be just README.md
ls onboarding/   # should be just README.md
ls docs/philosophy/  # should have 3 files

# Quick start smoke test
cd /tmp && rm -rf v4-test
claws init v4-test && cd v4-test
claws doctor  # should report missing API key with helpful message
claws --help  # should show epilog
```
