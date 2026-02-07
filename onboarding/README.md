# Agent Onboarding

claws trains new agents through structured curricula — progressive challenges that build real skills and earn trust through evaluation.

## Quick start

```bash
# Create and immediately onboard
claws agent create scout --role researcher --onboard default

# Or onboard an existing agent
claws agent onboard scout --curriculum default
```

## How it works

1. **Curriculum loads** — Phases, tasks, checkpoints, and personality traits
2. **Personality assigned** — Unique traits selected from constrained pools
3. **Tasks executed** — Agent works through progressive challenges
4. **Two-pass evaluation** — Each response scored by logic + consistency judges
5. **Checkpoints enforced** — Must pass minimum score to advance to next phase
6. **Reflection on failure** — Failed tasks trigger self-reflection before retry
7. **Graduation** — Summary written to agent identity and memory

## Curricula

```bash
claws curriculum list              # see available curricula
claws curriculum show default      # view phases, tasks, traits
claws curriculum create my-custom  # scaffold a new curriculum
```

The default curriculum has 3 phases (foundation, domain, capstone) with 8 tasks.

## Custom curricula

Curricula are YAML files. Create one with `claws curriculum create <name>`, then customize:

- **Phases** — groups of related tasks with checkpoint gates
- **Tasks** — prompts with task template pools for variety
- **Personality traits** — constrained pools for unique agent working styles
- **Reflection triggers** — scheduled self-reflection prompts

Curricula support inheritance — extend a parent and override specific phases.

## Options

```bash
claws agent onboard scout --curriculum default  # specify curriculum
claws agent onboard scout --seed 42             # deterministic personality
claws agent onboard scout --resume              # resume interrupted onboarding
claws agent onboard scout --force               # restart from scratch
```

## Design philosophy

See `docs/philosophy/` for the original vision that inspired this system.
