# Skills

Skills are reusable agent capabilities defined as markdown instruction files. Each skill tells an LLM agent how to perform a specific task.

## Format

A skill is a `SKILL.md` file with YAML frontmatter:

```yaml
---
name: my-skill
description: What this skill does
user-invocable: true
allowed-tools: Read, Write, Bash
---

# Instructions for the agent
Step 1: ...
Step 2: ...
```

## Active skills

| Skill | What it does |
|-------|-------------|
| `build-team/` | Dispatch structured plans to parallel agent teams |
| `learn/` | Analyze work and extract patterns (read-only) |
| `integrate/` | Wire learnings into memory and documentation |
| `save-memory/` | Comprehensive end-of-session memory capture |
| `dual-judge/` | Two-pass evaluation (logic + consistency judges) |
| `task-dispatch/` | Send tasks to agents via messaging |

## Hardware examples

These skills are specific to certain hardware deployments:

| Skill | What it does |
|-------|-------------|
| `camsnap/` | Camera snapshot and clip capture |
| `parakeet-stt/` | Local speech-to-text transcription |
| `video-subtitles/` | Generate and burn subtitles into video |

## Advanced

| Skill | What it does |
|-------|-------------|
| `ralph-loops/` | Autonomous build loop framework |
| `polylogue/` | Multi-document collaboration via webhooks |
