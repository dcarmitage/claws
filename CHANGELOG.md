# Changelog

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
- MIT License (previously proprietary)

## 1.0.0 — 2026-02-06 — Initial public release

### Added
- Dual-judge evaluation system (logic + consistency judges)
- Build orchestrator (JSONL logging, reporting, taskboard parser)
- AgentChat V2 (HTTP + WebSocket inter-agent messaging)
- 10 OpenClaw/Claude Code skills (judge, learn, integrate, save-memory, task-dispatch, ralph-loops, camsnap, parakeet-stt, video-subtitles, polylogue)
- The Hundred Steps onboarding curriculum (100-step agent development program)
- Soul Architecture document (philosophy, CV framework, identity formation)
- Infrastructure map and permissions checklist
- Agent starter kit (identity, memory, learning templates)
- 17 operational heuristics (H1-H17) with evidence
- 6 eval heuristics (E1-E6)
- Camera service, media catalog, health checks
- Example configurations and hook scripts
