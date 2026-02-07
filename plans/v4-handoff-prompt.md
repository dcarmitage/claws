# v4 Build — Handoff Prompt

Copy-paste this to start after compact:

---

## What to do

Execute `/build-team plans/v4-build.md` — this is a fully structured build plan ready for dispatch.

## Context

claws is a Python CLI tool (v2.0.0a3, 283 tests, E2E verified) for creating, training, and managing AI agents. The product code works great. Phase 4 is about fixing the onramp: install path, provider guidance, repo cleanup, and UX polish.

**Strategy doc:** `/home/clawd/plans/v4-simplification.md` — full background, decisions, audit results
**Build plan:** `/home/clawd/plans/v4-build.md` — structured for `/build-team` dispatch

## The 3 agents

| Agent | What | Depends on | Touches |
|-------|------|-----------|---------|
| `cli-enhancements` | `claws doctor`, error messages, onboarding progress, help epilog, version bump | nothing | `src/claws/` product code + new tests |
| `repo-restructure` | Archive philosophy to `docs/philosophy/`, rewrite all directory READMEs, rm stale scripts, merge `scripts/` → `tools/`, terminology sweep | nothing | All non-src directories |
| `readme-rewrite` | README progressive disclosure, provider setup guide, CHANGELOG, AGENTS.md | both above | README.md, CHANGELOG.md, AGENTS.md |

**Agents 1 and 2 run in parallel. Agent 3 runs after both complete.**

## Key decisions (from user interview)
- **Providers:** Anthropic + OpenAI + OpenRouter in quickstart. No Ollama.
- **Install:** GitHub install for now (`pip install git+...@prod`). PyPI later.
- **CLI changes:** Full UX pass — doctor command, error messages, onboarding progress, help epilog
- **Philosophy:** Move Hundred Steps + Soul Architecture to `docs/philosophy/`. Don't delete.
- **Python version:** Lower floor to >=3.8 (verify with tests)
- **Platform:** claws runs anywhere. Not Pi-specific.

## Environment
- Repo: `/home/clawd/` on `prod` branch
- venv: `source /home/clawd/.venv/bin/activate`
- Tests: `python -m pytest /home/clawd/tests/ -v` (283 tests, must stay green + new doctor tests)
- LLM for E2E: OpenClaw gateway at localhost:18789, token at `/home/dcarmitage/.openclaw/openclaw.json`

## After build completes
1. Run verification section from the build plan
2. Commit + push to prod
3. `/save-memory`
