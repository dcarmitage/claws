# Orchestrator — Specification

## Job To Be Done
When building features iteratively with sub-agents, I need a system that automatically tracks what was built, how long it took, whether it passed, and what I learned — so that every build session produces both working code AND institutional knowledge.

## Problem Statement
Currently the orchestrator (main session) manually:
- Writes TASKBOARD.md by hand
- Spawns builders one at a time
- Verifies results by running commands manually
- Updates TASKBOARD status by hand
- Writes evaluations retroactively

This works but loses data. Build timing, token costs, pass/fail rates, and patterns aren't captured systematically. Future sessions can't learn from past builds because the data isn't structured.

## Solution
A lightweight Python toolkit that the orchestrator calls between spawns to:
1. **Log** — Record each task's lifecycle (start, complete, validate, metrics)
2. **Report** — Generate build reports from structured logs
3. **Template** — Provide consistent taskboard and brief formats

The orchestrator (me) still makes all decisions. The tool captures data automatically.

## Non-Goals
- NOT a loop runner (that's Ralph)
- NOT replacing the orchestrator's judgment
- NOT a CI/CD system
- NOT complex — it's a logging + reporting tool

## Components

### 1. Build Logger (`build_log.py`)
Records events to a JSON Lines file (`build_log.jsonl`):

```python
# Log a task start
log_task_start(build_id, task_id, task_name, brief_summary)

# Log a task complete
log_task_complete(build_id, task_id, commit_hash, pass_fail, duration_seconds, notes)

# Log a validation result
log_validation(build_id, task_id, command, pass_fail, output)

# Log a build summary
log_build_summary(build_id, total_tasks, passed, failed, total_duration)
```

Each log entry:
```json
{
  "timestamp": "2026-02-01T15:30:00Z",
  "build_id": "stream-ui-v1.1",
  "event": "task_complete",
  "task_id": "fix-1",
  "task_name": "HLS live sync tuning",
  "commit": "23dc5ff",
  "passed": true,
  "duration_s": 25,
  "notes": ""
}
```

### 2. Build Reporter (`build_report.py`)
Reads `build_log.jsonl` and generates:

**Summary report** (markdown):
```
# Build Report: stream-ui-v1.1
- Tasks: 3/3 passed
- Duration: 1m 48s
- Avg task time: 36s
- Commits: 23dc5ff → e41992d
```

**Metrics over time** (for continuous improvement):
```
# Build History
| Build | Date | Tasks | Pass Rate | Avg Time | Method |
|-------|------|-------|-----------|----------|--------|
| stream-ui-v1.0 | 2026-02-01 | 5/5 | 100% | 36s | orchestrated |
| stream-ui-v1.1 | 2026-02-01 | 3/3 | 100% | 24s | orchestrated |
```

### 3. Taskboard Parser (`taskboard.py`)
Reads TASKBOARD.md and returns structured data:
```python
tasks = parse_taskboard("TASKBOARD.md")
# Returns: [{"id": "task-1", "name": "...", "status": "done", "commit": "...", "depends_on": []}]

next_task = get_next_task(tasks)
# Returns first task where status == "pending" and all dependencies are "done"
```

### 4. Templates
Standard formats for taskboards and task briefs:

**TASKBOARD template:**
```markdown
# TASKBOARD — [Project Name]
## Baseline: [commit hash]
## Tasks
### Task 1: [Name] ⬜
**Scope:** [what files/areas]
**Depends on:** [none | task N]
**Changes:** [description]
**Validate:** [commands]
**Commit message:** [message]
```

**Brief template** (what gets sent to sub-agent):
```
You have ONE task. Do it precisely, validate, commit, done.
**Task:** [name]
**File:** [path] — [scope constraint]
**Changes:** [exact code or description]
**Validate:** [commands]
**Commit:** [command]
Report PASS or FAIL.
```

## File Structure
```
systems/orchestrator/
├── SPEC.md              # This file
├── build_log.py         # Event logger
├── build_report.py      # Report generator
├── taskboard.py         # Taskboard parser
├── templates/
│   ├── TASKBOARD.md     # Template
│   └── BRIEF.md         # Template
└── logs/                # Build log storage
    └── *.jsonl
```

## Usage Pattern
```
# Orchestrator workflow:
1. python3 build_log.py start "stream-ui-v1.1"
2. python3 build_log.py task-start "stream-ui-v1.1" "fix-1" "HLS config"
3. [spawn sub-agent]
4. [sub-agent completes]
5. python3 build_log.py task-done "stream-ui-v1.1" "fix-1" "23dc5ff" --pass
6. python3 build_log.py task-start "stream-ui-v1.1" "fix-2" "Scrubber"
7. ...
8. python3 build_log.py report "stream-ui-v1.1"
9. python3 build_report.py history  # shows all builds
```

## Validation
- All Python files pass `python3 -c "import ast; ast.parse(...)"`
- `build_log.py` CLI produces valid JSONL
- `build_report.py` produces valid markdown
- `taskboard.py` parses the actual TASKBOARD.md files we created today
- Round-trip test: log events → generate report → report matches logged data
