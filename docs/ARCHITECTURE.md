# Architecture

## System overview

claws is a CLI tool that manages persistent AI agents. Each agent has identity, memory, and a trust score built from two-pass evaluations. Agents connect to any LLM provider via a unified interface.

```
┌──────────────────────────────────────────────┐
│              Human (terminal)                  │
│  claws init / agent create / run / evaluate   │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│              claws CLI (Click)                 │
│  commands/ → config.py → events.py             │
└──────┬───────────┬──────────────┬────────────┘
       │           │              │
  ┌────▼────┐ ┌────▼────┐  ┌─────▼──────┐
  │ Provider│ │ Eval    │  │ Onboarding │
  │ Layer   │ │ System  │  │ Engine     │
  └────┬────┘ └────┬────┘  └─────┬──────┘
       │           │              │
  ┌────▼───────────▼──────────────▼────────────┐
  │              LLM Provider                    │
  │  Anthropic (native) | OpenAI-compatible      │
  │  (Ollama, OpenRouter, Together, Groq, etc.)  │
  └────────────────────────────────────────────┘
```

## Data flow

### Task execution
```
claws run <agent> "task"
  │
  ├── load_config() → ProjectConfig
  ├── Read agents/<name>/identity.md as system prompt
  ├── Read agents/<name>/memory.md as context
  ├── get_provider(config) → Provider instance
  ├── provider.complete([system, user]) → Response
  ├── Save output to agents/<name>/output/YYYYMMDD-HHMMSS.md
  ├── EventSpine.emit(TASK_STARTED)
  └── EventSpine.emit(TASK_COMPLETED, {output_file, tokens, elapsed})
```

### Evaluation
```
claws evaluate <agent>
  │
  ├── Find last TASK_COMPLETED event for agent
  ├── Load output file → parse task + response
  ├── EventSpine.emit(EVAL_STARTED)
  ├── For each judge (logic, consistency):
  │   ├── Load judge prompt template
  │   ├── provider.complete(judge_prompt + task + response)
  │   └── Parse JSON scores from LLM response
  ├── Display scores, tiers, pass/fail
  └── EventSpine.emit(EVAL_COMPLETED, {results, all_passed})
```

### Onboarding
```
claws agent onboard <name> --curriculum default
  │
  ├── Load curriculum YAML (resolve inheritance if extends: parent)
  ├── Select personality traits from constrained pools
  ├── Inject traits into agents/<name>/identity.md
  ├── EventSpine.emit(ONBOARD_STARTED)
  │
  ├── For each phase (foundation → domain → capstone):
  │   ├── EventSpine.emit(ONBOARD_PHASE_STARTED)
  │   ├── For each task in phase:
  │   │   ├── Render task template with {agent_name}, {agent_role}, {scenario}
  │   │   ├── Sample scenario from pool if specified
  │   │   ├── provider.complete(task_prompt) → agent response
  │   │   ├── evaluate_response(provider, task, response) → judge scores
  │   │   ├── If pass: update memory, emit ONBOARD_TASK_COMPLETED
  │   │   ├── If fail: reflect → retry (up to max_retries)
  │   │   └── Save state to .onboarding/state.yaml after each task
  │   ├── Check phase gate (min_passed, min_avg_score)
  │   └── EventSpine.emit(ONBOARD_PHASE_COMPLETED)
  │
  ├── Write graduation summary to identity.md + memory.md
  └── EventSpine.emit(ONBOARD_COMPLETED)
```

### Trust
```
TrustProfile.for_agent(spine, agent_name)
  │
  ├── Read all EVAL_COMPLETED events for this agent
  ├── Group scores by judge type (logic, consistency)
  ├── Compute: avg per judge, overall avg, eval count
  └── Trend: 0 evals="new", 1-2="insufficient", 3+: compare recent vs overall
      (delta > 0.5 = "improving", < -0.5 = "declining", else "stable")
```

## Key files

| Component | Entry point | Config |
|-----------|-------------|--------|
| CLI | `src/claws/cli.py` | `claws.yaml` |
| Config | `src/claws/config.py` | ProjectConfig, ProviderConfig, EvalConfig, OnboardingConfig |
| Events | `src/claws/events.py` | 14 event types, EventSpine class |
| Evaluation | `src/claws/evaluation.py` | Judge prompts at `templates/prompts/` |
| Trust | `src/claws/trust.py` | Derived from EVAL_COMPLETED events |
| Providers | `src/claws/providers/registry.py` | get_provider() dispatches by type |
| Onboarding | `src/claws/onboarding/engine.py` | Curricula at `templates/curricula/` |
| Tests | `tests/` | 283 tests, 16 files, pytest |

## Event types

| Event | When |
|-------|------|
| `project.initialized` | `claws init` |
| `agent.created` | `claws agent create` |
| `task.started` | `claws run` begins |
| `task.completed` | `claws run` succeeds |
| `task.failed` | `claws run` fails |
| `eval.started` | `claws evaluate` begins |
| `eval.completed` | `claws evaluate` finishes |
| `deploy.completed` | Reserved for Phase 4 |
| `onboard.started` | Onboarding begins |
| `onboard.phase.started` | Phase begins |
| `onboard.task.completed` | Onboarding task passes |
| `onboard.task.failed` | Onboarding task fails |
| `onboard.phase.completed` | Phase gate checked |
| `onboard.completed` | Agent graduates |

## Environment variables

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | API key for native Anthropic provider |
| `OPENAI_API_KEY` | API key for OpenAI provider |
| Custom via `api_key_env` | Any env var name, configured per provider in claws.yaml |
