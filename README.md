# claws

A system for running persistent AI agents on edge hardware. Built on [OpenClaw](https://github.com/nicholasgriffintn/openclaw) and [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Agents wake up on Raspberry Pis, discover their hardware, learn to build software, evaluate their own work, communicate with each other, and develop operational memory that persists across sessions.

## What's here

| Directory | What it does |
|-----------|-------------|
| `evals/` | Dual-judge evaluation system — two LLM judges score task output against specs |
| `orchestrator/` | Build orchestration — task logging, reporting, taskboard parsing |
| `skills/` | OpenClaw / Claude Code skills — reusable agent capabilities |
| `tools/` | Standalone services — AgentChat messaging, camera, media catalog |
| `onboarding/` | The Hundred Steps — a 100-step curriculum for newborn agents |
| `starter-kit/` | Templates for bootstrapping a new agent's identity and memory |
| `scripts/` | Utility scripts — transcription, session management, handoff |
| `docs/` | Architecture docs, heuristics, principles |
| `examples/` | Example configurations and hook scripts |

## Supported platforms

- Raspberry Pi 5 (16GB recommended, 8GB minimum)
- Raspberry Pi 4 (4GB+ — lighter workloads)
- Mac Mini / Mac Studio (development and orchestration)
- Any Linux box with Python 3.11+ and Node.js 20+

## Prerequisites

- [OpenClaw](https://github.com/nicholasgriffintn/openclaw) installed and onboarded
- An Anthropic API key (configured through OpenClaw)
- Git, Python 3.11+, Node.js 20+, jq, bc

## Quick start

```bash
# Clone
git clone https://github.com/dcarmitage/claws.git
cd claws

# Set your workspace root
export CLAWS_HOME=$(pwd)

# Run the health check
bash tools/health-check.sh

# Start the AgentChat server (inter-agent messaging)
python3 tools/agentchat/server_v2.py &

# Run a dual-judge evaluation on a commit
bash evals/run_dual_judge_eval.sh \
  --build-id my-build --task-id T1 \
  --spec path/to/spec.md --taskboard path/to/taskboard.md \
  --commit HEAD
```

## Key concepts

**Dual-judge evaluation.** Every task gets scored by two independent LLM judges (logic + consistency). Both must score >= 8.0/10 to pass. See `evals/README.md`.

**Build orchestration.** Tasks are logged as JSONL events. Taskboards track dependency graphs. Reports aggregate metrics across builds. See `orchestrator/README.md`.

**The Hundred Steps.** A curriculum that takes a newborn agent from `whoami` to a self-hosted portfolio. 7 phases, 3 human gates, 7 mandatory reflections. See `onboarding/`.

**Heuristics.** 17 rules learned from production failures. Each has evidence, not just opinion. See `docs/HEURISTICS.md`.

**Memory system.** Agents maintain daily logs, curated operational state, and cross-session learnings. The `/learn` and `/integrate` skills form a reflection flywheel.

## Architecture

```
Human (Telegram / CLI / Web)
  │
  ▼
OpenClaw Gateway (LLM routing, auth, rate limiting)
  │
  ├── Agent Alpha (Pi 5) ──── AgentChat ──── Agent Beta (Pi 4)
  │     │                        │
  │     ├── Camera service       ├── Task dispatch
  │     ├── STT service          └── Webhook delivery
  │     ├── Build orchestrator
  │     └── Dual-judge evals
  │
  └── Claude Code (interactive sessions)
```

## Docs

- [Architecture](docs/ARCHITECTURE.md) — how the pieces connect
- [Heuristics](docs/HEURISTICS.md) — 17 rules from production
- [Principles](docs/PRINCIPLES.md) — distilled decision framework
- [Platforms](docs/PLATFORMS.md) — hardware-specific notes

## License

Proprietary. See [LICENSE](LICENSE).
