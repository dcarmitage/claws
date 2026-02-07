# Handoff: claws v4 — The Simplification

## The Problem

The claws GitHub repo has 153 files. The v2 CLI product works great (283 tests, E2E verified), but the surrounding directories (`evals/`, `orchestrator/`, `skills/`, `onboarding/`, `tools/`, `scripts/`, `docs/`) are stale v1 content that hasn't been updated to match the v2 CLI. A new user sees a wall of folders full of conflicting information.

Additionally, the codebase uses made-up terminology ("Event Spine", "The Hundred Steps", "Soul Architecture") instead of standard industry terms. This creates unnecessary cognitive load.

**The concepts are valuable. The content needs updating.**

## The Vision

**Apple out-of-box experience.** Not by removing folders, but by making every folder tell a coherent story. When someone explores the repo, each directory should feel like it belongs and use terminology they already understand.

### Terminology Cleanup

| Current (custom jargon) | Standard term |
|------------------------|---------------|
| Event Spine | event log / audit log |
| The Hundred Steps | onboarding curriculum |
| Soul Architecture | agent identity model |
| Trust Profile | agent score / evaluation history |
| Dual-judge evaluation | two-pass evaluation |
| Phase gate | checkpoint / milestone |
| Scenario pool | task template library |

### Progressive Disclosure

**Level 1 — First 5 minutes:**
```bash
pip install claws
claws init my-project && cd my-project
claws agent create scout --role researcher --onboard default
```

**Level 2 — First hour:**
```bash
claws run scout "research task"
claws evaluate scout
claws status
```

**Level 3 — Power user:**
Custom curricula, multiple providers, evaluation tuning, orchestration.

## Decisions (user interview, 2026-02-07)

### Providers: Anthropic + OpenAI + OpenRouter
- **Anthropic**: OAuth console signup + API key. First-class, recommended.
- **OpenAI**: OAuth console signup + API key. First-class alternative.
- **OpenRouter**: API key only. Third option for users who want model variety.
- **No Ollama** in quickstart. Local providers are a power-user topic.
- README quickstart shows all three with clear setup steps for each.

### Installation: Whatever enables testing THIS session
- Pragmatic: try PyPI publish if credentials exist, otherwise GitHub install.
- README must have a working `pip install` command by end of Phase 4.
- Goal: user can test the full flow on a fresh VM today.

### CLI changes: Full UX pass
- Improved error messages (API key errors suggest next steps + alternatives)
- `claws doctor` command (checks provider config, connectivity, test query)
- Onboarding progress indicator (task N/M, phase name, ETA)
- `claws --help` epilog ("New to claws? Start with: claws init <project>")
- Product code changes ARE in scope — this isn't docs-only.

### Philosophy content: Elegant archive
- Don't lose important philosophy — it's part of the project's DNA.
- Move long-form content (Hundred Steps, Soul Architecture) to `docs/philosophy/`.
- Add clear framing: "Original design vision. Current implementation: `claws agent onboard`."
- Keep `onboarding/` clean for v2 content only (README + practical guides).

## What Needs to Happen

### Layer 1: Unblock the front door

**1a. Fix installation path**
- Publish v2.0.0a3 to PyPI (or update README to `pip install git+...@prod`)
- Verify: fresh venv, `pip install claws`, `claws --version` → 2.0.0a3

**1b. Provider setup guide**
- Add Prerequisites section to README before Quick Start
- Three paths with exact steps:
  - Anthropic: sign up at console.anthropic.com → get API key → `export ANTHROPIC_API_KEY=...`
  - OpenAI: sign up at platform.openai.com → get API key → configure in claws.yaml
  - OpenRouter: sign up at openrouter.ai → get API key → configure in claws.yaml
- Show claws.yaml examples for each provider

**1c. `claws doctor` command**
- Check: is a provider configured in claws.yaml?
- Check: is the API key set (env var or config)?
- Check: can we reach the provider endpoint?
- Check: does a test query succeed?
- Output: clear pass/fail with actionable fix for each failure

**1d. Improved error messages**
- "No API key" → suggest provider setup steps + mention `claws doctor`
- "Provider not configured" → show example claws.yaml snippet
- Add epilog to `claws --help`: "New to claws? Start with: claws init <project>"

### Layer 2: Clean the repo

**2a. Update every directory to match v2**

**`evals/`** — The evaluation system exists in `claws evaluate`. This directory should:
- Describe how evaluation works (two judges, scoring, thresholds)
- Document the judge prompts and how to customize them
- Remove: bash scripts that are replaced by `claws evaluate`
- Keep/update: README explaining the eval philosophy

**`orchestrator/`** — The event log + status system exists in `claws status` and `.claws/events.jsonl`. This directory should:
- Describe the event log format and how events flow
- Document how to query events, understand agent state
- Remove: Python scripts replaced by CLI commands
- Keep/update: README explaining orchestration concepts

**`onboarding/`** — The curriculum system exists in `claws agent onboard`. This directory should:
- Rewrite README: curriculum model, phases, checkpoints, personality traits, custom curricula guide
- Move THE_HUNDRED_STEPS.md → `docs/philosophy/the-hundred-steps.md`
- Move SOUL_ARCHITECTURE.md → `docs/philosophy/agent-identity-model.md`
- Move PERMISSIONS.md to `docs/` (operational checklist, not user-facing)
- Move INFRASTRUCTURE_MAP.md to `docs/` (Pi-specific deployment example, not product docs)

**`skills/`** — Skills are reusable agent capabilities. This directory should:
- Keep: `build-team/` (actively used for multi-agent dispatch)
- Keep: `learn/`, `integrate/`, `save-memory/`, `dual-judge/` (active workflow skills)
- Move to `skills/examples/`: `camsnap/`, `parakeet-stt/`, `video-subtitles/` (hardware-specific)
- Keep: `ralph-loops/` (advanced pattern, clearly labeled)
- Keep: `task-dispatch/`, `polylogue/` (evaluate relevance)
- Update: README to describe the skill format and categorize skills

**`tools/`** — Standalone services. This directory should:
- Absorb `scripts/` contents (consolidate into one directory)
- Clearly label everything as environment-specific implementations
- Update README: "These are example tools for specific deployments, not required by claws"
- Keep: agentchat (useful pattern), health-check
- Move or remove Pi-specific tools (camera, catalog, media) — these are deployment examples, not product

**`scripts/`** — Merge into `tools/`. Remove directory.

**`docs/`** — Architecture and reference docs. This directory should:
- Keep: `ARCHITECTURE.md` (already updated for v2)
- Create: `docs/philosophy/` — archive for Hundred Steps, Soul Architecture
- Update: `HEURISTICS.md` → rename to `BEST_PRACTICES.md`, update content
- Update: `PRINCIPLES.md` → consolidate or merge into CONTRIBUTING.md
- Update: `PLATFORMS.md` → generalize to standard platform requirements (Python 3.8+, any OS), not Pi-centric

**`starter-kit/`** — Agent templates. This directory should:
- Update README: explain these are auto-generated by `claws agent create`
- Update references from "The Hundred Steps" to `claws agent onboard`
- Keep templates current with v2 agent structure

**`examples/`** — Keep, update if needed.

**`plans/`** — Keep as-is (operational artifacts).

**2b. Terminology sweep**
- grep for all custom jargon and replace with standard terms
- Update code comments, docstrings, help text, error messages
- Cover: all markdown files, all Python source, all YAML configs

**2c. README rewrite — progressive disclosure**
- Hero: one sentence + install
- Prerequisites: API key setup (Anthropic / OpenAI / OpenRouter)
- Quick start: 3 commands to a trained agent
- "What just happened": explain what onboarding did
- Configuration: claws.yaml with provider examples
- Command reference (full table)
- Directory guide (what each folder is for)

### Layer 3: Polish the experience

**3a. Onboarding UX**
- Pre-flight prompt: "This runs 8 tasks across 3 phases (~5-7 min). Continue? [Y/n]"
- Progress indicator: "Task 3/8 | Phase: Foundation | ETA: 3 min"
- Preview option: mention `claws curriculum show default`

**3b. Post-evaluation guidance**
- After low-score eval, suggest next steps
- Mention `claws run` to retry, or editing agent memory for guidance

**3c. CLI help polish**
- `claws --help` epilog: "New to claws? Start with: claws init <project>"
- Consistent formatting across all subcommand help text

## Fresh User Audit (2-judge analysis, 2026-02-07)

Two judges independently evaluated the "VM → few commands → working agent" experience.

### Scorecard

| Step | What | UX Score | Technical Score | Verdict |
|------|------|----------|----------------|---------|
| Discovery | Land on GitHub, read README | 7/10 | — | Good but missing prerequisites |
| Installation | `pip install claws` | 8/10 | 3/10 | **BROKEN** — PyPI has old v0.0.22, not v2 |
| `claws init` | Create project | 9/10 | 10/10 | Excellent |
| Provider setup | Configure LLM access | 3/10 | 8/10 | **WALL** — code works, zero guidance |
| Agent creation | `claws agent create` | 9/10 | 10/10 | Excellent |
| Onboarding | `--onboard default` | 5/10 | 10/10 | Works but no time estimate or explanation |
| Use agent | `claws run` + `evaluate` | 7/10 | — | Works but no feedback loop |
| Browse repo | Look at directory listing | 4/10 | — | 14 dirs, no navigation guide |

**Overall: Engine is 10/10. Onramp is 3/10.**

### Critical Blockers (priority order)

1. **Install path broken** — `pip install claws` gets wrong version. Must publish v2 to PyPI or fix README to use `pip install git+https://github.com/dcarmitage/claws.git@prod`
2. **Provider setup wall** — No prerequisites section, no "how to get an API key," no guidance on alternatives. 80% of fresh users abandon here.
3. **Repo clutter** — 14 top-level directories with no explanation of what's product vs. development. Stale v1 content contradicts v2 CLI.
4. **Onboarding UX** — No pre-flight explanation ("this takes 5-7 min"), no progress indicator, no preview option
5. **No feedback loop** — User evaluates agent, sees low score, doesn't know what to do next

### What's NOT Broken

- All product code (init, create, run, evaluate, onboard, status, trust)
- Template packaging (curricula, prompts, configs all included correctly)
- Error messages (generally actionable, with room for improvement)
- CLI help text (clear, well-organized)

## Current State

### What's Working (v2.0.0a3, E2E verified 2026-02-07)
- Full lifecycle: init → create → onboard → run → evaluate → trust
- 283 tests, all green in 1.6s
- E2E: scout graduated default curriculum, 8.7/10, reflect-retry worked
- Pushed to prod on GitHub

### Key Product Files (56 files — these don't change unless Layer 1/3 requires it)
```
src/claws/         — The CLI package (38 files)
tests/             — 283 tests (16 files + conftest + __init__)
pyproject.toml     — Package metadata
```

### Branch Architecture
- **`prod`** — public GitHub branch (current, v2.0.0a3)
- **`dev`** — private operational branch (clawd's secrets, memory, state)
- **GitHub default** still `master` — needs change to `prod`

### Environment
- **claws runs anywhere** — any machine with Python 3.8+ and a terminal

## How to Execute This

### Recommended approach: research → judge → execute → verify

1. **Research phase** — agents explore how successful CLI tools organize their repos (uv, ruff, gh, dagger) and what standard terminology they use
2. **Braintrust** — 2-judge session per directory: what to update, remove, keep
3. **Execution** — `/build-team` with agents for each layer
4. **E2E verification** — fresh VM test: clone, install, 3-command getting started

### Execution order

**Layer 1 first** — unblocks the user testing on a VM immediately.
**Layer 2 in parallel** — multiple agents updating directories simultaneously.
**Layer 3 after Layer 1** — UX polish builds on the fixed front door.

### Key Constraints
- 283 tests must still pass (and new tests for `claws doctor`)
- pyproject.toml force-include for templates must still work
- Don't lose concepts — update content to match v2 reality
- Use standard terminology throughout
- Philosophy content archived elegantly, not deleted

### Success Criteria
- User can `pip install claws` on any machine with Python 3.8+ and get v2.0.0a3
- `claws doctor` passes with a configured provider
- `claws init` + `claws agent create --onboard default` works end-to-end
- Every directory README tells the v2 story
- Zero custom jargon in user-facing content
- Full onboarding shows progress and time estimate

## Skills Available
- `/build-team <plan>` — dispatch structured plans to agent teams
- `/save-memory` — comprehensive end-of-session memory save
- `/learn` — extract patterns from what happened
- Speed braintrust: 2 judges in parallel for quick decisions
