# Changelog

## v2.0.0a4 (2026-02-07)

Phase 4: The Simplification -- fixing the onramp.

### Added
- `claws doctor` command -- diagnoses setup issues (project, provider, API key, connectivity)
- Onboarding progress indicators (task N/M, phase name)
- Post-evaluation guidance for failed evaluations
- Provider-specific error messages with setup instructions
- CLI help epilog for new users

### Changed
- Python version floor lowered to 3.8+ (from 3.10)
- Repository reorganized: philosophy archived to `docs/philosophy/`, stale scripts removed, directory READMEs rewritten
- Terminology standardized throughout (event log, two-pass evaluation, onboarding curriculum)
- README rewritten with progressive disclosure and multi-provider quickstart

### Removed
- Stale v1 bash scripts from evals/, orchestrator/
- Redundant onboarding docs (archived to docs/philosophy/)
- scripts/ directory (merged into tools/scripts/)

## v2.0.0a3 (2026-02-07)

### Added
- `claws agent onboard` -- curriculum-based agent training with progressive phases
- `claws agent create --onboard` -- create and immediately onboard in one command
- `claws curriculum list` / `show` / `create` -- manage training curricula
- Onboarding engine with personality traits, reflection triggers, and checkpoints
- Default curriculum: 3 phases (foundation, domain, capstone), 8 tasks
- 6 scenario pools for diverse, substantive training content
- Curriculum inheritance (`extends:` field) for custom curricula
- Deterministic personality with `--seed` flag (405+ trait combinations)
- `--resume` flag for crash recovery during onboarding
- Shared evaluation module (`claws.evaluation`) for programmatic eval access
- 133 new tests (283 total)

## v2.0.0a2 (2026-02-06)

### Added
- `claws evaluate` -- two-pass evaluation (logic + consistency judges)
- Evaluation history -- per-agent scoring with trend detection (improving/stable/declining)
- Trust display in `agent info`, `agent list`, `status`
- 150 pytest tests across 9 test files

## v2.0.0a1 (2026-02-06)

### Added
- `claws` CLI (`pip install claws`)
- `claws init` -- create a new project with one command
- `claws agent create` -- add agents with identity and memory templates
- `claws run` -- execute tasks via any LLM provider (Anthropic, OpenAI, etc.)
- `claws status` -- see all agents, tasks, and scores in your terminal
- `claws agent list` / `claws agent info` -- manage agents
- Event log -- unified append-only event log (.claws/events.jsonl)
- Provider abstraction -- Anthropic native + OpenAI-compatible for everything else
- `claws.yaml` -- single config file for project, providers, agents, eval settings
- MIT License
