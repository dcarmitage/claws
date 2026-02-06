# claws

The operating system for human-AI teams.

Your agents build software, evaluate their own work, and get better over time. You review PRs.

## Quick start

```bash
pip install claws

claws init my-project
cd my-project

claws agent create scout --role researcher
claws run scout "Find the 3 most popular Rust web frameworks and compare their tradeoffs"
```

That's it. One agent, one task, real output. In under 5 minutes.

## Add a second agent

```bash
claws agent create reviewer --role "code reviewer"
claws status
```

## What claws does

| Feature | What it means |
|---------|---------------|
| **Your agents remember** | Memory persists across sessions. Agents learn from yesterday's work. |
| **Your agents collaborate** | Agents communicate, dispatch tasks, review each other's work. |
| **Your agents earn trust** | Dual-judge evaluation gates. Agents prove their work meets your standards. |

## How it works

```
You give a task
  │
  ▼
claws run <agent> "task"
  │
  ├── Agent reads its identity + memory
  ├── Sends task to configured LLM provider
  ├── Streams response to your terminal
  ├── Saves output to agents/<name>/output/
  └── Logs event to the Event Spine
  │
  ▼
claws status → see all agents, tasks, scores
```

## Configuration

Everything lives in `claws.yaml`:

```yaml
project: my-project
version: 2

providers:
  default:
    type: anthropic
    model: claude-sonnet-4-5-20250929

  # Works with any OpenAI-compatible endpoint
  # cheap:
  #   type: ollama
  #   model: llama3
  #   base_url: http://localhost:11434/v1

agents:
  scout:
    role: researcher
    provider: default
  builder:
    role: developer
    provider: default

eval:
  judges: [logic, consistency]
  threshold: 8.0
```

Supports: Anthropic, OpenAI, Ollama, OpenRouter, Together, Groq, LM Studio, or any OpenAI-compatible API.

## What's in the repo

| Directory | What it does |
|-----------|-------------|
| `src/claws/` | The CLI — `pip install claws` |
| `evals/` | Dual-judge evaluation system — two LLM judges score work against specs |
| `orchestrator/` | Build orchestration — task logging, reporting, taskboard parsing |
| `skills/` | Reusable agent capabilities with YAML frontmatter |
| `tools/` | Standalone services — AgentChat messaging, camera, media catalog |
| `onboarding/` | The Hundred Steps — a 100-step curriculum for newborn agents |
| `starter-kit/` | Templates for bootstrapping agent identity and memory |
| `docs/` | Architecture, heuristics, principles, platform notes |

## The philosophy

Agents aren't disposable workers. They're team members with identity, memory, and growth.

The [Hundred Steps](onboarding/THE_HUNDRED_STEPS.md) curriculum takes a newborn agent from `whoami` to a self-hosted portfolio. The [Soul Architecture](onboarding/SOUL_ARCHITECTURE.md) treats agent development as seriously as software development.

The [17 heuristics](docs/HEURISTICS.md) were learned from production failures. Each has evidence, not opinion.

> Your agents have resumes.

## Platforms

Works on any machine with Python 3.10+ and an LLM API key:

- macOS (Apple Silicon or Intel)
- Linux (x86_64 or ARM64)
- Raspberry Pi 5 / Pi 4
- WSL2 on Windows

## Docs

- [Architecture](docs/ARCHITECTURE.md) — how the pieces connect
- [Heuristics](docs/HEURISTICS.md) — 17 rules from production
- [Principles](docs/PRINCIPLES.md) — distilled decision framework
- [Platforms](docs/PLATFORMS.md) — hardware-specific notes
- [Contributing](CONTRIBUTING.md) — how to contribute
- [Security](SECURITY.md) — security model and reporting

## License

[MIT](LICENSE)
