# Case Study: Building an AI Build Orchestrator

## Abstract
This document tracks the development of a build orchestration system for AI agent sub-tasks. The system is being built BY the method it describes — a self-referential case study in iterative development with AI agents.

## Context
- **Environment:** Raspberry Pi 5 running Clawdbot (AI agent runtime)
- **Agent:** Portal1 (media librarian / infrastructure builder)
- **Human:** Mudpaw (collaborator, evaluator)
- **Date started:** 2026-02-01

## The Problem
When building software features using AI sub-agents, we discovered:
1. Giving one agent many tasks produces low-quality output (context accumulation)
2. Giving one agent one task with fresh context produces high-quality output
3. An orchestrator is needed to coordinate: what to build, in what order, and verify results
4. The orchestration process itself generates valuable data (timing, pass rates, patterns) that should be captured automatically for continuous improvement

## Methodology Evolution

### v0: Direct Build (Baseline)
- Human describes feature → agent builds it in one pass
- **Result:** Works for simple things, fails for complex features
- **Data captured:** None

### v1: Bulk Sub-Agent
- Write spec → spawn one sub-agent with all tasks
- **Result:** Failed quality inspection. Context accumulated across tasks.
- **Data captured:** Git commits (but all-or-nothing rollback)

### v2: Orchestrated Build
- Write spec → create TASKBOARD with dependency graph → spawn one builder per task → verify between each → QA
- **Result:** All tasks passed. Per-task rollback. Higher quality.
- **Data captured:** Git commits per task, manual evaluation after

### v3: Instrumented Orchestration (building now)
- Same as v2 but with automatic logging: build_log.py captures timing, pass/fail, commit hashes
- build_report.py generates reports and tracks improvement over time
- **Goal:** Every build session produces both working code AND structured learning data

## Experiments

### Experiment 1: Bulk vs Orchestrated (2026-02-01)

| Metric | Bulk (1 agent, 6 tasks) | Orchestrated (6 agents, 1 each) |
|--------|------------------------|--------------------------------|
| Quality | ❌ Failed inspection | ✅ 13/13 checks |
| Tokens per builder | ~35k | 13-28k (avg 20k) |
| Rollback granularity | All or nothing | Per task |
| Time | ~3 min | ~4 min |
| Data captured | 1 commit | 6 commits + eval |

**Finding:** Orchestrated approach uses LESS tokens per builder AND produces higher quality. The overhead of multiple spawns is minimal (~1 min extra) and pays for itself in quality and rollback granularity.

### Experiment 2: Task Brief Specificity (2026-02-01)

Compared vague vs precise task briefs:
- **Vague:** "Fix the time display to show elapsed time"
- **Precise:** Exact code to write, exact insertion points, exact validation commands

**Finding:** Precise briefs with exact code produce 100% first-pass success. Vague briefs occasionally need iteration. The extra time writing precise briefs (2-3 min) saves more time in rework.

### Experiment 3: Orchestrator Tool Build (2026-02-01, in progress)

Using the orchestrated method to build the orchestrator itself.
- Spec: `systems/orchestrator/SPEC.md`
- Metrics will be captured here as the build progresses.

| Task | Builder Time | Tokens | Pass? | Notes |
|------|-------------|--------|-------|-------|
| (recording as we build) | | | | |

## Key Principles (Evolving)

1. **One task, one agent, fresh context** — Non-negotiable. Accumulated context degrades output.
2. **Exact briefs > vague briefs** — Tell the builder WHAT to write, not just what to achieve.
3. **Verify between tasks** — The orchestrator MUST check each result before proceeding.
4. **Git checkpoint everything** — Every task gets a commit. Rollback is per-task.
5. **Capture data automatically** — If it's not logged, it didn't happen. Build the logging first.
6. **Plans are disposable** — Regenerate from spec rather than patching a drifting plan.
7. **Visual verification matters** — Automated checks catch syntax errors, not UX problems.

## Future Experiments
- [ ] Parallel task execution (independent tasks spawned simultaneously)
- [ ] LLM-as-judge for visual/UX quality
- [ ] Cross-session learning (builder agents reading past build logs)
- [ ] Cost optimization (Sonnet for simple tasks, Opus for complex)
- [ ] Automated taskboard generation from specs

## Related Files
- `systems/orchestrator/SPEC.md` — Tool specification
- `EVAL_2026-02-01.md` — First build evaluation
- `LEARN.md` — Agent learning system (methodology section)
- `TASKBOARD.md`, `TASKBOARD_V2.md` — Build coordination files
- `memory/2026-02-01.md` — Daily session log
