# Orchestrator — Build Management

Tools for planning, executing, and reviewing multi-task builds.

## Components

**build_log.py** — CLI event logger. Appends JSONL events (build-start, task-start, task-done, validate, judge-eval, summary) to per-build log files.

**build_report.py** — Report generator. Reads JSONL logs and produces markdown reports, build history tables, and aggregate metrics.

**taskboard.py** — TASKBOARD.md parser. Reads task definitions with status emojis and dependency graphs. Supports parse, next, status, and update commands.

## Usage

```bash
# Start a build
python3 orchestrator/build_log.py start MY-BUILD-001

# Log a task
python3 orchestrator/build_log.py task-start MY-BUILD-001 T1 "Add auth endpoint" \
  --spec specs/auth.md --taskboard TASKBOARD.md

# Mark task done
python3 orchestrator/build_log.py task-done MY-BUILD-001 T1 abc123 --duration 120

# Log judge results
python3 orchestrator/build_log.py judge-eval MY-BUILD-001 T1 abc123 \
  --logic-score 9.2 --logic-tier GOLD \
  --consistency-score 8.5 --consistency-tier SILVER

# Generate report
python3 orchestrator/build_report.py report MY-BUILD-001

# View build history
python3 orchestrator/build_report.py history

# Aggregate metrics
python3 orchestrator/build_report.py metrics

# Parse taskboard
python3 orchestrator/taskboard.py next TASKBOARD.md
python3 orchestrator/taskboard.py status TASKBOARD.md
python3 orchestrator/taskboard.py update TASKBOARD.md 1 done abc123
```

## Files

| File | Purpose |
|------|---------|
| `build_log.py` | JSONL event logger |
| `build_report.py` | Markdown report generator |
| `taskboard.py` | TASKBOARD.md parser and updater |
| `CHECKLISTS.md` | Operational checklists (session start, pre-build, post-milestone, etc.) |
| `templates/BRIEF.md` | Task brief template |
| `templates/TASKBOARD.md` | Taskboard template |

## Log format

Each build produces a `.jsonl` file in `orchestrator/logs/` (gitignored). Events:

```json
{"timestamp":"...","build_id":"B001","event":"build_start"}
{"timestamp":"...","build_id":"B001","event":"task_start","task_id":"T1","task_name":"..."}
{"timestamp":"...","build_id":"B001","event":"task_done","task_id":"T1","commit":"abc123","passed":true}
{"timestamp":"...","build_id":"B001","event":"judge_eval","task_id":"T1","logic_judge":{...},"consistency_judge":{...}}
```
