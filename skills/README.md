# Skills — Reusable Agent Capabilities

Skills are markdown files with YAML frontmatter that give agents specific capabilities. When an agent invokes a skill (e.g., `/judge`, `/learn`), the LLM reads the SKILL.md as instructions.

## Available skills

| Skill | Command | Description |
|-------|---------|-------------|
| dual-judge | `/judge` | Run dual-judge evaluation on a commit |
| learn | `/learn` | Analyze what was just learned (read-only) |
| integrate | `/integrate` | Wire learnings into the memory system |
| save-memory | `/save-memory` | End-of-session memory save |
| task-dispatch | `/dispatch` | Dispatch tasks to other agents via AgentChat |
| ralph-loops | — | Autonomous build loop framework |
| camsnap | `/camsnap` | Camera snapshot and clip capture |
| parakeet-stt | — | Local speech-to-text transcription |
| video-subtitles | — | Generate and burn-in subtitles |
| polylogue | — | Document collaboration webhook |

## Creating a new skill

1. Create a directory: `skills/my-skill/`
2. Write `SKILL.md` with YAML frontmatter:

```yaml
---
name: my-skill
description: What this skill does (shown in skill listings)
user-invocable: true  # Set to true if users can invoke with /my-skill
allowed-tools: Read, Grep, Glob, Bash
---
```

3. Below the frontmatter, write instructions the LLM will follow when the skill is invoked.

## Skill conventions

- `$ARGUMENTS` is replaced with whatever the user typed after the command
- Skills should be self-contained — don't assume the agent has read other files
- Include concrete `bash` commands the agent can run
- Specify what tools the skill needs in `allowed-tools`
