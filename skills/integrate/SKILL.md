---
name: integrate
description: >-
  Integrate learnings into the full memory system. Links new knowledge to
  existing concepts, updates the right files, keeps memory tidy, and sets up
  future sessions for success. Run after /learn or whenever significant
  knowledge needs to be persisted.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Integrate

Wire new learnings into the memory system so they compound instead of evaporate.

## What To Do

### 1. Understand What Needs Integrating

First, figure out what knowledge needs to be captured. Sources:

- **The current conversation** — what was just discussed, built, or discovered
- **Output from /learn** — if it was run, use its analysis as the starting point
- **Uncommitted changes** — `git -C $CLAWS_HOME status --short` may reveal work not yet documented
- **Recent evals/builds** — check logs for undocumented results

### 2. Read ALL Target Files Before Editing

This is critical. Read every file you plan to modify BEFORE making changes:

```
$CLAWS_HOME/systems/orchestrator/HEURISTICS.md    — rules (H1-H15, E1-E6)
$CLAWS_HOME/LEARN.md                               — techniques & patterns
$CLAWS_HOME/MEMORY.md                              — operational state
$CLAWS_HOME/memory/YYYY-MM-DD.md                   — today's daily log
$HOME/.claude/projects/-home-your-user/memory/MEMORY.md  — auto memory
```

You need to understand what's already there to:
- Avoid duplicating knowledge
- Find the right place to add new knowledge
- Link new learnings to existing concepts
- Consolidate if old entries are now subsumed by new ones

### 3. Decide Where Each Learning Goes

Not everything goes everywhere. Use this routing table:

| Type of Learning | Where It Goes |
|-----------------|---------------|
| **Reusable rule with evidence** | HEURISTICS.md (new H# or update existing) |
| **Technique or how-to** | LEARN.md section 4 (Techniques & Patterns) |
| **What happened today** | memory/YYYY-MM-DD.md |
| **System state change** | MEMORY.md (update relevant section) |
| **Cross-session pattern** | Auto memory (~/.claude/.../MEMORY.md) |
| **Refinement of existing rule** | Update the existing entry, don't create a new one |
| **Contradiction of existing belief** | Update or remove the old entry, add the correction |

### 4. Integration Rules

**Link, don't island.** When adding a new concept, explicitly reference related existing concepts. "This is H14 applied to X" or "This extends the pattern from section 4.2" or "See also: memory/2026-02-05.md". Isolated knowledge is forgotten knowledge.

**Consolidate, don't accumulate.** If a new learning subsumes or refines an old one, UPDATE the old entry rather than adding a new one alongside it. Memory files that only grow eventually become unreadable.

**Preserve numbering.** HEURISTICS.md uses H1-H15 and E1-E6. When adding a new heuristic, use the next number. Never renumber existing entries — other files reference them by number.

**Keep MEMORY.md under 200 lines.** If it's getting long, move detailed content to topic-specific files and link from MEMORY.md. Operational state should be scannable, not a novel.

**Keep auto memory focused.** The auto memory (`~/.claude/.../MEMORY.md`) is loaded into every session's system prompt. Only put things there that help EVERY future session — key patterns, gotchas, system locations. Not daily details.

**Date your updates.** When modifying a file, update the "Last updated" line if one exists.

**Follow existing format.** Each file has its own conventions. Match them:
- HEURISTICS.md: `### H#: Title` + bold rule + explanation + evidence + action
- LEARN.md: Tables, code blocks, structured sections
- Daily memory: Sections from the save-memory template
- MEMORY.md: Dense operational reference
- Auto memory: Bullet points, brief

### 5. Execute the Integration

Make all edits. For each file:

1. Read it (if not already read)
2. Identify the insertion/update point
3. Edit precisely — don't rewrite sections you're not changing
4. Verify the edit didn't break surrounding content

### 6. Verify

After all edits:

```bash
# Files were actually modified
git -C $CLAWS_HOME diff --stat

# MEMORY.md is still under 200 lines
wc -l $CLAWS_HOME/MEMORY.md

# No broken markdown (quick check)
head -5 $CLAWS_HOME/systems/orchestrator/HEURISTICS.md
head -5 $CLAWS_HOME/LEARN.md
head -5 $CLAWS_HOME/MEMORY.md
```

### 7. Report What Was Done

Tell the user exactly what was integrated and where:

```
| File | What Changed |
|------|-------------|
| HEURISTICS.md | Added H16: ... |
| LEARN.md | Updated Strategy Council section with ... |
| memory/2026-02-05.md | Added experiment results |
| MEMORY.md | Updated heuristic count |
| Auto memory | Added key pattern for ... |
```

## Important

- **Read before write. Always.** Blind edits break things. You MUST understand what's in a file before modifying it.
- **Don't bloat.** If you're adding more than you're consolidating, something is wrong. Good integration often makes files shorter, not longer.
- **Test your links.** If you reference another file or section, verify it exists.
- **Don't create new files unless necessary.** Prefer editing existing files. New files fragment knowledge.
- **Be surgical.** Edit the minimum needed. Don't reformat surrounding text, don't add comments to code you didn't change, don't "improve" nearby sections.
- **This is not /save-memory.** /save-memory is a comprehensive end-of-session dump. /integrate is surgical insertion of specific learnings into the right places. Use /save-memory at session end; use /integrate after any significant discovery.
