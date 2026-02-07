# Changelog

## 2.0.0a3 — 2026-02-07

### Added
- `claws agent onboard` — curriculum-based agent training with progressive phases
- `claws agent create --onboard` — create and immediately onboard in one command
- `claws curriculum list` / `show` / `create` — manage training curricula
- Onboarding engine with personality traits, reflection triggers, and phase gates
- Default curriculum: 3 phases (foundation, domain, capstone), 8 tasks
- 6 scenario pools for diverse, substantive training content
- Curriculum inheritance (`extends:` field) for custom curricula
- Deterministic personality with `--seed` flag (405+ trait combinations)
- `--resume` flag for crash recovery during onboarding
- Shared evaluation module (`claws.evaluation`) for programmatic eval access
- 133 new tests (283 total)

## 2.0.0a2 — 2026-02-06

### Added
- `claws evaluate` — dual-judge evaluation (logic + consistency judges)
- Trust profiles — per-agent scoring with trend detection (improving/stable/declining)
- Trust display in `agent info`, `agent list`, `status`
- 150 pytest tests across 9 test files

## 2.0.0a1 — 2026-02-06

### Added
- `claws` CLI (`pip install claws`)
- `claws init` — create a new project with one command
- `claws agent create` — add agents with identity and memory templates
- `claws run` — execute tasks via any LLM provider (Anthropic, OpenAI, Ollama, etc.)
- `claws status` — see all agents, tasks, and scores in your terminal
- `claws agent list` / `claws agent info` — manage agents
- Event Spine — unified append-only event log (.claws/events.jsonl)
- Provider abstraction — Anthropic native + OpenAI-compatible for everything else
- `claws.yaml` — single config file for project, providers, agents, eval settings
- MIT License
