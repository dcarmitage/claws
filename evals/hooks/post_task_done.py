#!/usr/bin/env python3
"""PostToolUse hook: auto-trigger dual-judge eval after build_log.py task-done.

Reads hook input from stdin (JSON with tool_input.command).
If the command matches `build_log.py task-done`, extracts build_id, task_id,
and commit, then looks up spec/taskboard paths from the build log.

Exit 0 = no action (silent pass-through).
Prints to stdout = message injected into conversation.
"""

import json
import os
import re
import sys

LOGS_DIR = "$CLAWS_HOME/systems/orchestrator/logs"


def find_spec_paths(build_id, task_id):
    """Look up spec and taskboard paths from the build log's task-start event."""
    log_path = os.path.join(LOGS_DIR, f"{build_id}.jsonl")
    spec = None
    taskboard = None

    if not os.path.exists(log_path):
        return spec, taskboard

    try:
        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)
                if ev.get("event") == "task_start" and ev.get("task_id") == task_id:
                    spec = ev.get("spec")
                    taskboard = ev.get("taskboard")
                # Also check build-level taskboard from any task_start
                if ev.get("event") == "task_start" and ev.get("taskboard") and not taskboard:
                    taskboard = ev.get("taskboard")
    except (json.JSONDecodeError, OSError):
        pass

    return spec, taskboard


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        return

    command = hook_input.get("tool_input", {}).get("command", "")

    # Match: build_log.py task-done <build_id> <task_id> <commit>
    match = re.search(
        r'build_log\.py\s+task-done\s+(\S+)\s+(\S+)\s+(\S+)',
        command
    )
    if not match:
        return

    build_id = match.group(1)
    task_id = match.group(2)
    commit = match.group(3)

    # Try to find spec/taskboard from the build log
    spec, taskboard = find_spec_paths(build_id, task_id)

    if spec and taskboard:
        # Fully automatic — we have everything
        reason = (
            f"[JUDGE GATE] task-done detected for {task_id} (build {build_id}, "
            f"commit {commit}). Per E4: run dual-judge evaluation now.\n\n"
            f"Run:\n"
            f"  bash $CLAWS_HOME/evals/run_dual_judge_eval.sh "
            f"--build-id {build_id} --task-id {task_id} "
            f"--spec {spec} --taskboard {taskboard} --commit {commit}\n\n"
            f"Do not advance to the next task until both judges score >= 8.0."
        )
    elif spec:
        reason = (
            f"[JUDGE GATE] task-done detected for {task_id} (build {build_id}, "
            f"commit {commit}). Per E4: run dual-judge evaluation now.\n\n"
            f"Spec found: {spec}\n"
            f"Taskboard not found in build log. Check for IMPLEMENTATION_PLAN.md "
            f"or taskboard.md in the working directory, then run:\n"
            f"  bash $CLAWS_HOME/evals/run_dual_judge_eval.sh "
            f"--build-id {build_id} --task-id {task_id} "
            f"--spec {spec} --taskboard <taskboard_path> --commit {commit}"
        )
    else:
        reason = (
            f"[JUDGE GATE] task-done detected for {task_id} (build {build_id}, "
            f"commit {commit}). Per E4: run dual-judge evaluation now.\n\n"
            f"No spec/taskboard paths found in build log. To enable automatic "
            f"judge invocation, pass --spec and --taskboard when calling "
            f"build_log.py task-start.\n\n"
            f"For now, find the spec for this task and run:\n"
            f"  bash $CLAWS_HOME/evals/run_dual_judge_eval.sh "
            f"--build-id {build_id} --task-id {task_id} "
            f"--spec <spec_path> --taskboard <taskboard_path> --commit {commit}"
        )

    result = {"decision": "approve", "reason": reason}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
