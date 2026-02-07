---
name: build-team
description: >-
  Dispatch a structured plan to an agent team. Reads a plan file,
  validates file ownership, spawns teammates, creates shared tasks
  with dependencies, and runs verification when complete.
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Task
---

# Build Team

Parse a structured plan file and dispatch it to an agent team for parallel execution.

## Arguments

`$ARGUMENTS` should be a path to a plan file (e.g., `plans/phase2.md`).

## Phase 1: Parse & Validate

1. Read the plan file at `$ARGUMENTS` (relative to `/home/clawd/` if not absolute).
2. Extract agent blocks by parsing `### <agent-name>: <role>` headers.
3. For each agent, extract:
   - **Creates:** list of files (from the line after `**Creates:**`)
   - **Modifies:** list of files (from the line after `**Modifies:**`)
   - **Depends on:** agent name or "nothing"
   - **Description:** everything after the metadata until the next `###` or `## Verification`
4. **Validate file ownership:** If any file appears in two agents' Creates or Modifies lists, STOP and report the conflict. This is the critical constraint.
5. **Validate dependencies:** No circular deps. All referenced agents exist.
6. Extract the `## Verification` section for the final gate.
7. Show dispatch summary to user:

```
Dispatch Summary:
  Agent 1: <name> (<role>) — <N> files, depends on: <deps>
  Agent 2: <name> (<role>) — <N> files, depends on: <deps>
  ...
File ownership: OK (no conflicts)
Dependencies: OK (no cycles)
```

Confirm with user before proceeding.

## Phase 2: Execute Pre-flight

If the plan has a `## Pre-flight` section, execute those steps BEFORE dispatching agents. The lead (you) handles pre-flight directly.

## Phase 3: Dispatch Agents

For each agent block, spawn a background subagent using the Task tool:

```
Task(
  subagent_type="general-purpose",
  prompt=<agent prompt>,
  description=<short description>,
  run_in_background=True
)
```

**Agent prompt template:**

```
You are agent "<agent-name>" with role "<role>".

## Your Assignment
<description from plan>

## File Ownership (STRICT)
You ONLY create/modify these files:
Creates: <creates list>
Modifies: <modifies list>

DO NOT touch any files not in your lists. Other agents own other files.

## Working Directory
All paths are relative to /home/clawd/

## Context
<full plan context so agent understands the bigger picture>

## When Done
Verify your gate condition passes. Report what you created/modified and any issues.
```

**Dispatch order:**
- Agents with no dependencies: dispatch immediately (in parallel)
- Agents with dependencies: dispatch AFTER their dependency completes

## Phase 4: Monitor & Coordinate

1. For independent agents dispatched in parallel, use TaskOutput to monitor.
2. When an agent completes, check if any blocked agents can now be dispatched.
3. If an agent reports a problem, assess whether to retry or escalate to user.
4. Track completion status of all agents.

## Phase 5: Integrate & Verify

When all agents complete:

1. Reinstall the package: `cd /home/clawd && source .venv/bin/activate && pip install -e ".[dev,anthropic]"`
2. Run the verification section from the plan.
3. Report results:
   - If all pass: "All agents completed. Verification passed."
   - If failures: identify which agent's work has issues, report specifics.

## Fallback: Sequential Mode

If agent teams aren't available or background dispatch fails:
1. Run agents sequentially (respecting dependency order)
2. Independent agents still run in parallel via Task tool
3. Wait for each agent before dispatching dependents
4. Lead runs verification at the end

## Important Rules

- **Never touch files owned by another agent.** This is the #1 rule.
- **Agents are autonomous.** Don't micromanage — let them read source, write tests, iterate.
- **Each agent should verify its own gate** before reporting done.
- **Pre-flight is the lead's job.** Don't delegate pre-flight to agents.
- **Source the venv** before any Python commands: `source /home/clawd/.venv/bin/activate`
