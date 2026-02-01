# TASKBOARD — Orchestrator Tool Build

## Baseline
- **Commit:** current HEAD
- **Spec:** `systems/orchestrator/SPEC.md`

## Dependency Graph
```
Task 1: build_log.py (core logger, no dependencies)
  ↓
Task 2: taskboard.py (parser, no dependencies on task 1 but builds after)
  ↓
Task 3: build_report.py (depends on build_log.py output format)
  ↓
Task 4: templates (depends on knowing the format from tasks 1-3)
  ↓
Task 5: integration test (depends on all above)
```

## Tasks

### Task 1: build_log.py ⬜
**Scope:** Create `systems/orchestrator/build_log.py`
**Changes:** CLI tool that appends JSON Lines to a log file. Commands:
- `start <build_id>` — log build start
- `task-start <build_id> <task_id> <task_name>` — log task begin
- `task-done <build_id> <task_id> <commit> [--pass|--fail] [--notes "..."]` — log task completion
- `validate <build_id> <task_id> <command> [--pass|--fail]` — log validation
- `summary <build_id>` — log build summary (reads back the log to compute totals)

Log file location: `systems/orchestrator/logs/<build_id>.jsonl`
Each entry: `{"timestamp": ISO8601, "build_id": str, "event": str, "task_id": str, ...}`

**Validate:**
```bash
python3 -c "import ast; ast.parse(open('systems/orchestrator/build_log.py').read()); print('valid')"
cd /home/clawd && python3 systems/orchestrator/build_log.py start test-build
python3 systems/orchestrator/build_log.py task-start test-build t1 "Test task"
python3 systems/orchestrator/build_log.py task-done test-build t1 abc123 --pass
python3 systems/orchestrator/build_log.py summary test-build
cat systems/orchestrator/logs/test-build.jsonl
```
**Commit:** `orchestrator: build_log.py - event logger`

### Task 2: taskboard.py ⬜
**Scope:** Create `systems/orchestrator/taskboard.py`
**Changes:** CLI tool that parses TASKBOARD.md files. Commands:
- `parse <file>` — output JSON array of tasks with id, name, status, commit, depends_on
- `next <file>` — output the next pending task (all deps done)
- `status <file>` — human-readable summary (N done, N pending, N failed)
- `update <file> <task_id> <status> [commit]` — update a task's status in the file

Parse rules:
- Task header: `### Task N: Name ⬜|✅|❌`
- Status: ⬜=pending, ✅=done, ❌=failed
- Commit hash in parens after status: `✅ (abc123)`
- Depends on: line starting with `**Depends on:**`

**Validate:**
```bash
python3 -c "import ast; ast.parse(open('systems/orchestrator/taskboard.py').read()); print('valid')"
python3 systems/orchestrator/taskboard.py parse /home/clawd/TASKBOARD.md
python3 systems/orchestrator/taskboard.py status /home/clawd/TASKBOARD.md
python3 systems/orchestrator/taskboard.py next /home/clawd/TASKBOARD.md
```
**Commit:** `orchestrator: taskboard.py - parser`

### Task 3: build_report.py ⬜
**Scope:** Create `systems/orchestrator/build_report.py`
**Changes:** CLI tool that reads build logs and generates reports. Commands:
- `report <build_id>` — markdown summary of one build
- `history` — markdown table of all builds in logs/
- `metrics` — aggregate stats (total tasks, avg time, pass rate across all builds)

Report format:
```markdown
# Build Report: <build_id>
**Date:** ...
**Tasks:** N/N passed
**Duration:** Xm Ys
**Commits:** first..last

| Task | Duration | Result | Commit |
|------|----------|--------|--------|
| ... | 25s | ✅ | abc123 |
```

**Validate:**
```bash
python3 -c "import ast; ast.parse(open('systems/orchestrator/build_report.py').read()); print('valid')"
python3 systems/orchestrator/build_report.py report test-build
python3 systems/orchestrator/build_report.py history
```
**Commit:** `orchestrator: build_report.py - reporter`

### Task 4: Templates ⬜
**Scope:** Create template files
**Changes:**
- `systems/orchestrator/templates/TASKBOARD.md` — starter taskboard
- `systems/orchestrator/templates/BRIEF.md` — sub-agent task brief template

**Validate:** Files exist and are valid markdown
**Commit:** `orchestrator: templates`

### Task 5: Integration test ⬜
**Scope:** End-to-end test using the tools on our actual build data
**Changes:** Run the tools against today's real taskboards and verify output makes sense:
```bash
# Parse real taskboard
python3 systems/orchestrator/taskboard.py parse /home/clawd/TASKBOARD.md
python3 systems/orchestrator/taskboard.py status /home/clawd/TASKBOARD_V2.md

# Simulate logging a real build
python3 systems/orchestrator/build_log.py start stream-ui-v1.0
python3 systems/orchestrator/build_log.py task-start stream-ui-v1.0 task-1 "Server endpoints"
python3 systems/orchestrator/build_log.py task-done stream-ui-v1.0 task-1 4387988 --pass --notes "free_bytes + elapsed_seconds"
# ... (log all 5 tasks from today)
python3 systems/orchestrator/build_log.py summary stream-ui-v1.0

# Generate report
python3 systems/orchestrator/build_report.py report stream-ui-v1.0
python3 systems/orchestrator/build_report.py history
```
**Commit:** `orchestrator: integration test passed`
