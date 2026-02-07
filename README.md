# claws -- Build, train, and manage AI agents

Create agents with persistent identity and memory. Train them through structured curricula. Evaluate their work. Build trust over time.

## Quick start

Prerequisites:
- Python 3.8+
- An API key from one of: [Anthropic](https://console.anthropic.com), [OpenAI](https://platform.openai.com), or [OpenRouter](https://openrouter.ai)

```bash
pip install git+https://github.com/dcarmitage/claws.git@prod

# Guided setup — picks your provider, shows you what to configure:
claws init my-project
cd my-project

# Verify everything works:
claws doctor

# Create and train an agent:
claws agent create scout --role researcher --onboard default
```

## What just happened?

`claws agent create --onboard` did four things in one command. It created an agent with a unique personality sampled from trait pools. It ran the agent through a curriculum of eight progressive tasks across three phases (foundation, domain, capstone). Each response was scored by two independent judges (one for logic, one for consistency). The agent now has an identity, skills, and an evaluation history with a trust score.

## Commands

| Command | What it does |
|---------|-------------|
| `claws init <project>` | Guided project setup — provider, model, API key |
| `claws agent create <name> --role <role>` | Create an agent with identity and memory |
| `claws agent create <name> --role <role> --onboard <curriculum>` | Create and immediately train |
| `claws agent onboard <name>` | Train an agent through an onboarding curriculum |
| `claws agent list` | List all agents with roles and trust scores |
| `claws agent info <name>` | Agent details -- identity, history, scores |
| `claws run <agent> "task"` | Execute a task via the configured LLM provider |
| `claws evaluate <agent>` | Two-pass quality scoring (logic + consistency) |
| `claws status` | Project overview -- agents, tasks, recent activity |
| `claws curriculum list` | List available curricula (built-in and custom) |
| `claws curriculum show <name>` | View curriculum phases, tasks, and traits |
| `claws curriculum create <name>` | Create a custom curriculum |
| `claws doctor` | Diagnose setup issues (project, provider, API key, connectivity) |

## Configuration

`claws init` generates `claws.yaml` automatically. You can also edit it directly:

```yaml
project: my-project
version: 2

providers:
  default:
    type: anthropic
    model: claude-opus-4-6

  # Or use OpenAI:
  # default:
  #   type: openai-compatible
  #   model: codex-5.3
  #   base_url: https://api.openai.com/v1

agents:
  scout:
    role: researcher
    provider: default

eval:
  judges: [logic, consistency]
  threshold: 8.0
```

## How it works

Agents follow a lifecycle: **create** gives them identity and memory. **Train** runs them through a curriculum of progressively harder tasks, with two-pass evaluation at each step. Failed tasks trigger reflection before retry. **Run** sends tasks to the configured LLM provider, with the agent's identity and memory as context. **Evaluate** scores the agent's latest output. Every action is logged to an append-only event log, and trust scores are derived from the evaluation history over time.

## Project structure

When you run `claws init`, you get:

```
my-project/
├── claws.yaml              # Project config -- providers, agents, eval settings
├── .claws/events.jsonl     # Event log -- append-only audit trail
├── agents/
│   └── scout/
│       ├── identity.md     # Agent identity (evolves through work)
│       ├── memory.md       # Agent memory (persists across sessions)
│       └── output/         # Task outputs (timestamped)
└── curricula/              # Custom curricula (optional)
```

Repository directories (for contributors):

| Directory | What's inside |
|-----------|---------------|
| `src/claws/` | CLI source code |
| `tests/` | Test suite (322 tests) |
| `evals/` | Evaluation system docs |
| `orchestrator/` | Event log docs |
| `onboarding/` | Training system docs |
| `skills/` | Agent skill definitions |
| `tools/` | Deployment and operational utilities |
| `docs/` | Architecture, best practices, and philosophy |
| `starter-kit/` | Agent templates and learning resources |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on pull requests, code style, and development principles.

## License

[MIT](LICENSE)
