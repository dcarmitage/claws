# AGENTS.md — Instructions for AI agents working on this repo

## Overview

claws is a CLI tool for running persistent AI agents. Agents have identity, memory, and trust scores. The codebase is a Python package (`pip install claws`) built with Click, Rich, and httpx.

## File structure

```
claws/
├── src/claws/              # The CLI package
│   ├── cli.py              # Main Click group, command registration
│   ├── config.py           # Config dataclasses (ProjectConfig, ProviderConfig, etc.)
│   ├── events.py           # Event/EventSpine, 14 event type constants
│   ├── evaluation.py       # Shared eval: _run_judge, evaluate_response()
│   ├── trust.py            # TrustProfile computation from eval events
│   ├── commands/           # CLI subcommands
│   │   ├── init.py         # claws init
│   │   ├── agent.py        # claws agent create/list/info/onboard
│   │   ├── run.py          # claws run
│   │   ├── status.py       # claws status
│   │   ├── evaluate.py     # claws evaluate
│   │   ├── curriculum.py   # claws curriculum list/show/create
│   │   └── onboard.py      # claws agent onboard
│   ├── providers/          # LLM provider abstraction
│   │   ├── base.py         # Provider ABC, Message, Response
│   │   ├── registry.py     # get_provider() factory
│   │   ├── anthropic.py    # Native Anthropic provider
│   │   └── openai_compat.py # OpenAI-compatible (Ollama, OpenRouter, etc.)
│   ├── onboarding/         # Curriculum-based agent training
│   │   ├── engine.py       # OnboardingEngine class
│   │   ├── curriculum_loader.py # YAML parsing + inheritance
│   │   ├── personality.py  # Trait selection + formatting
│   │   └── state.py        # OnboardingState persistence
│   └── templates/          # Templates for init, agents, curricula
│       ├── claws.yaml      # Project config template
│       ├── identity.md     # Agent identity template
│       ├── memory.md       # Agent memory template
│       ├── prompts/        # Judge prompt templates
│       └── curricula/      # Built-in curricula + scenario pools
├── tests/                  # 283 pytest tests (16 files)
├── docs/                   # Architecture, contributing, security
└── pyproject.toml          # Package metadata, dependencies, build config
```

## Code conventions

- **Python:** 3.10+. `from __future__ import annotations`. Type hints welcome.
- **CLI:** Click for commands, Rich for output. Use `Console()` for printing.
- **Config:** Dataclasses for config types. YAML for persistence. `claws.yaml` is the single source of truth.
- **Events:** Use the Event Spine (`EventSpine.emit()`) for all state changes. Never modify events.jsonl directly.
- **Tests:** pytest with Click's `CliRunner`. Use `tmp_path` fixtures. Mock `httpx` for provider tests.
- **Markdown:** ATX headings (`#`). Tables for structured data.

## How to make changes

1. Read the relevant files before modifying. Understand existing patterns.
2. Keep changes minimal. Don't refactor adjacent code or add features beyond scope.
3. Run tests: `source /home/clawd/.venv/bin/activate && python -m pytest tests/ -v`
4. Follow existing naming conventions in whatever directory you're working in.

## What NOT to do

- Don't commit secrets, API keys, tokens, or personal information
- Don't add large binary files (images, models, databases)
- Don't create new top-level directories without discussion
- Don't rename files that other files reference (grep first)
- Don't add dependencies without checking they're available on Raspberry Pi OS

## Testing

```bash
source /home/clawd/.venv/bin/activate

# Run all 283 tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_onboarding_engine.py -v

# Run tests matching a pattern
python -m pytest tests/ -k "test_curriculum" -v
```

## Key design decisions

- **Two judges, not one.** Logic judge checks accuracy and reasoning. Consistency judge checks completeness and coherence. Neither alone is sufficient.
- **Event Spine.** Append-only JSONL. Every action emits a typed event. Trust profiles are derived, not stored.
- **Curriculum-based onboarding.** Agents train through progressive phases with gates. Personality traits are sampled, not assigned. Failed tasks trigger reflection before retry.
- **Provider abstraction.** Anthropic native + OpenAI-compatible for everything else. One interface, any LLM.
- **File ownership.** When multiple agents work on the codebase, each agent owns specific files. No file appears in two agents' ownership lists.
