# AGENTS.md — Instructions for AI agents working on this repo

## Overview

This is a multi-agent system for running persistent AI agents on edge hardware (Raspberry Pi). The codebase includes evaluation tools, build orchestration, inter-agent messaging, and an onboarding curriculum.

## File structure

```
claws/
├── evals/           # Dual-judge evaluation (logic + consistency judges)
├── orchestrator/    # Build logging, reporting, taskboard parsing
├── skills/          # OpenClaw/Claude Code skills (reusable capabilities)
├── tools/           # Standalone services (AgentChat, camera, catalog)
├── onboarding/      # The Hundred Steps curriculum
├── starter-kit/     # Agent bootstrap templates
├── scripts/         # Utility scripts
├── docs/            # Architecture, heuristics, principles
└── examples/        # Example configs
```

## Code conventions

- **Shell scripts:** `set -euo pipefail` at the top. Use `$SCRIPT_DIR` for relative paths.
- **Python:** Python 3.11+. No type stubs required but type hints welcome. Use stdlib where possible.
- **Markdown:** ATX headings (`#`). Tables for structured data. No trailing whitespace.
- **Paths:** Use `$CLAWS_HOME` for the repo root. Never hardcode `/home/...` paths.
- **Config:** Use environment variables with sensible defaults: `${VAR:-default}`.

## How to make changes

1. Read the relevant files before modifying. Understand existing patterns.
2. Keep changes minimal. Don't refactor adjacent code or add features beyond scope.
3. Test your changes. The evals system (`evals/`) exists for a reason.
4. Follow existing naming conventions in whatever directory you're working in.

## What NOT to do

- Don't commit secrets, API keys, tokens, or personal information
- Don't add large binary files (images, models, databases)
- Don't create new top-level directories without discussion
- Don't rename files that other files reference (grep first)
- Don't add dependencies without checking they're available on Raspberry Pi OS

## Testing

```bash
# Validate judge output schema
echo '{"judge":"logic","score":8.5,"tier":"SILVER","timestamp":"2026-01-01T00:00:00Z"}' | bash evals/validate_output.sh -

# Run a judge against a commit
bash evals/run_single_judge.sh --judge logic --build-id TEST --task-id T1 \
  --spec path/to/spec.md --taskboard path/to/taskboard.md --commit HEAD

# Parse a taskboard
python3 orchestrator/taskboard.py status path/to/TASKBOARD.md
```

## Key design decisions

- **Two judges, not one.** Logic judge checks spec compliance. Consistency judge checks cross-file alignment. Neither alone is sufficient.
- **JSONL for logs.** Append-only, one event per line, easy to parse with jq.
- **Skills are markdown.** Each skill is a `SKILL.md` with YAML frontmatter. The LLM reads it as instructions.
- **Memory is distributed.** Daily logs + curated state + heuristics + learning journal. No single file holds everything.
