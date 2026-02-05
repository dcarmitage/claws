---
name: save-memory
description: >-
  Thorough end-of-session memory save. Use before compacting, ending a session,
  or whenever significant work has been completed. Saves to both daily memory
  and MEMORY.md with full context so the next session can pick up seamlessly.
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Save Memory

Capture everything the next session needs to continue where this one left off.
This is not a quick note — it's a structured handoff document.

## What To Do

### 1. Gather Context

Before writing anything, collect the facts:

```bash
# What changed today?
git -C /home/clawd log --oneline --since="midnight" 2>/dev/null || echo "no commits today"

# What files are new or modified?
git -C /home/clawd status --short 2>/dev/null

# What builds happened?
ls -t /home/clawd/systems/orchestrator/logs/*.jsonl 2>/dev/null | head -3

# What judge evals happened?
ls -t /home/clawd/evals/results/*.json 2>/dev/null | head -5
```

Read the current daily memory and MEMORY.md to understand what's already captured.

### 2. Update Daily Memory (`/home/clawd/memory/YYYY-MM-DD.md`)

Create or update today's file. Use this structure — every section matters:

```markdown
# YYYY-MM-DD

## What Was Built
- One bullet per feature/system/change, with enough detail to understand it
- Include the WHY, not just the what

## Automation / Integration
- How the new work connects to existing systems
- Hooks, skills, triggers, workflows added

## Bugs Fixed During Build
- What broke, why, and the fix
- These are the learnings that prevent repeats

## Key Decisions Made
- What trade-offs were chosen and why
- What was considered but rejected

## File Inventory
### New files
- Full path and one-line purpose for every new file

### Modified files
- Full path and what changed for every modified file

## What's Verified Working
- Specific test results: what was tested, what scores/outcomes
- Pass paths AND fail paths

## What's NOT Done / Known Gaps
- Anything left incomplete
- Anything that needs testing in a real build
- Next steps if someone picks this up

## Flywheel Status
- Is the system running end-to-end?
- What triggers what?
- What still requires manual intervention?
```

### 3. Update MEMORY.md (`/home/clawd/MEMORY.md`)

This is the **curated operational state** — not a log, but a snapshot of how the system works RIGHT NOW. Update the relevant sections:

- System architecture (if changed)
- Active services and their status
- Key file locations
- Current capabilities
- Known issues

Keep it under 200 lines. If a section grows too long, link to a dedicated file.

### 4. Update Auto Memory (if running as dcarmitage)

Update `/home/dcarmitage/.claude/projects/-home-dcarmitage/memory/MEMORY.md` with:
- Key learnings from this session (patterns, anti-patterns, gotchas)
- Updated system knowledge (file locations, conventions, how things work)
- Keep it focused on what helps the NEXT session be productive

### 5. Verify

After saving, verify nothing was missed:

```bash
# Daily memory exists and has substance
wc -l /home/clawd/memory/$(date +%Y-%m-%d).md

# MEMORY.md was updated recently
stat -c '%Y %n' /home/clawd/MEMORY.md 2>/dev/null || stat -f '%m %N' /home/clawd/MEMORY.md

# No unstaged important files
git -C /home/clawd status --short | grep -v '^\?\?' | head -10
```

## Important

- **Be specific.** "Updated build system" is useless. "Extended build_log.py with judge-eval subcommand that logs logic/consistency scores as JSONL events" is useful.
- **Include file paths.** The next session doesn't know where anything is.
- **Include what was tested.** Not just "it works" — what specific scenarios were verified?
- **Include what broke.** Bugs fixed during the build are the most valuable learnings.
- **Include the flow.** How does data move through the system? What triggers what?
- **Don't skip the gaps.** Honest about what's incomplete > pretending everything is done.
