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

## Onboard an agent

New agents can train themselves through a structured curriculum:

```bash
claws agent create scout --role researcher --onboard default
```

This runs the agent through 8 tasks across 3 phases (foundation, domain, capstone), with dual-judge evaluation at each step. The agent gets a unique personality, builds real skills, and graduates with a trust score.

Or onboard an existing agent:

```bash
claws agent onboard scout --curriculum default
```

See available curricula:

```bash
claws curriculum list
claws curriculum show default
```

## Evaluate and trust

```bash
claws evaluate scout        # dual-judge scoring (logic + consistency)
claws agent info scout      # see trust profile, identity, history
claws status                # see all agents, tasks, scores
```

Agents earn trust through work. Every evaluation feeds into a trust profile with trend detection (improving, stable, declining).

## What claws does

| Feature | What it means |
|---------|---------------|
| **Your agents remember** | Memory persists across sessions. Agents learn from yesterday's work. |
| **Your agents train** | Curriculum-based onboarding builds real skills through progressive challenges. |
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
claws evaluate <agent> → dual-judge scoring
  │
  ▼
claws status → see all agents, tasks, trust scores
```

## All commands

| Command | What it does |
|---------|-------------|
| `claws init <project>` | Create a new project with config, event spine, agent directory |
| `claws agent create <name> --role <role>` | Create an agent with identity and memory |
| `claws agent create <name> --role <role> --onboard default` | Create and immediately onboard |
| `claws agent onboard <name>` | Run an agent through a training curriculum |
| `claws agent list` | List all agents with roles and trust scores |
| `claws agent info <name>` | Show agent identity, history, trust profile |
| `claws run <agent> "task"` | Execute a task via the configured LLM provider |
| `claws evaluate <agent>` | Score the agent's last output with dual judges |
| `claws status` | Project overview — agents, tasks, recent activity |
| `claws curriculum list` | List available curricula (built-in and project) |
| `claws curriculum show <name>` | Display curriculum phases, tasks, traits |
| `claws curriculum create <name>` | Scaffold a new custom curriculum |

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

eval:
  judges: [logic, consistency]
  threshold: 8.0
```

Supports: Anthropic, OpenAI, Ollama, OpenRouter, Together, Groq, LM Studio, or any OpenAI-compatible API.

## Project structure

```
my-project/
├── claws.yaml              # Project config — providers, agents, eval settings
├── .claws/events.jsonl     # Event Spine — append-only audit log
├── agents/
│   └── scout/
│       ├── identity.md     # Who this agent is (evolves through work)
│       ├── memory.md       # What this agent remembers
│       └── output/         # Task outputs (timestamped)
└── curricula/              # Custom curricula (optional)
```

## The philosophy

Agents aren't disposable workers. They're team members with identity, memory, and growth.

The curriculum system takes a newborn agent from self-introduction to capstone deliverable. Personality traits are sampled from constrained pools — each agent develops a unique working style. Failed tasks trigger reflection before retry. Trust is earned, not declared.

> Your agents have resumes.

## Platforms

Works on any machine with Python 3.10+ and an LLM API key:

- macOS (Apple Silicon or Intel)
- Linux (x86_64 or ARM64)
- Raspberry Pi 5 / Pi 4
- WSL2 on Windows

## Docs

- [Architecture](docs/ARCHITECTURE.md) — how the pieces connect
- [Contributing](CONTRIBUTING.md) — how to contribute
- [Security](SECURITY.md) — security model and reporting

## License

[MIT](LICENSE)
