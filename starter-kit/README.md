# Starter Kit — Bootstrap a New Agent

Templates for initializing a new agent's identity and memory system. These are reference templates — in practice, `claws agent create` auto-generates the agent's workspace with the right structure.

## Files

| File | Purpose |
|------|---------|
| `IDENTITY.md` | Agent identity template — name, role, personality |
| `SOUL.md` | Philosophy and values template |
| `MEMORY.md` | Operational memory template |
| `LEARN.md` | Shared learning journal template |
| `TOOLS.md` | Hardware and software reference template |

## Usage

```bash
# The recommended way to create an agent:
claws agent create scout --role researcher

# To onboard with a training curriculum:
claws agent create scout --role researcher --onboard default

# Or onboard an existing agent:
claws agent onboard scout --curriculum default
```

## How it connects

The starter kit provides empty structures. The `claws agent onboard` command guides the agent through filling them in via structured curricula with progressive challenges and two-pass evaluation. See `onboarding/README.md` for details on the curriculum system.
