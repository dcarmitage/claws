#!/usr/bin/env python3
"""
Task Dispatch — bridges orchestrator taskboards with AgentChat task API.

Posts tasks from TASKBOARD.md to AgentChat, lets agents poll/claim/complete
tasks, and logs everything to build_log.py.

Commands:
  post <taskboard>            Post next pending task to AgentChat, assign to agent
  poll <agent_id>             Check for tasks assigned to agent (returns JSON)
  claim <task_id> <agent_id>  Claim a task (sets in_progress)
  complete <task_id> <agent_id> [--commit SHA] [--build-id ID]  Mark done
  status                      Show all AgentChat tasks
  sync <taskboard>            Post ALL pending tasks from taskboard to AgentChat
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

SERVER = os.environ.get("AGENTCHAT_SERVER", "http://localhost:9090")
BUILD_LOG = "/home/clawd/systems/orchestrator/build_log.py"
TASKBOARD_PY = "/home/clawd/systems/orchestrator/taskboard.py"


def api_get(path):
    """GET from AgentChat API, return parsed JSON."""
    url = f"{SERVER}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}


def api_post(path, data):
    """POST JSON to AgentChat API, return parsed JSON."""
    url = f"{SERVER}{path}"
    payload = json.dumps(data).encode()
    try:
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}


def run_build_log(args_list):
    """Run build_log.py with given args. Returns True on success."""
    try:
        subprocess.run(
            ["python3", BUILD_LOG] + args_list,
            check=True, capture_output=True, text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [WARN] build_log failed: {e.stderr}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print(f"  [WARN] build_log.py not found at {BUILD_LOG}", file=sys.stderr)
        return False


def get_next_task(taskboard_path):
    """Use taskboard.py to get next pending task from a TASKBOARD.md file."""
    try:
        result = subprocess.run(
            ["python3", TASKBOARD_PY, "next", taskboard_path],
            capture_output=True, text=True, check=True
        )
        output = result.stdout.strip()
        if output == "null" or not output:
            return None
        return json.loads(output)
    except Exception as e:
        print(f"  [ERR] taskboard.py next failed: {e}", file=sys.stderr)
        return None


def get_all_tasks(taskboard_path):
    """Use taskboard.py to get all tasks from a TASKBOARD.md file."""
    try:
        result = subprocess.run(
            ["python3", TASKBOARD_PY, "parse", taskboard_path],
            capture_output=True, text=True, check=True
        )
        return json.loads(result.stdout.strip())
    except Exception as e:
        print(f"  [ERR] taskboard.py parse failed: {e}", file=sys.stderr)
        return []


def cmd_post(args):
    """Post the next pending task from a taskboard to AgentChat."""
    task = get_next_task(args.taskboard)
    if not task:
        print("No pending tasks in taskboard.")
        return

    assignee = args.assignee or "portal2"
    title = f"Task {task['id']}: {task['name']}"
    description = task.get("scope") or f"From taskboard: {args.taskboard}"

    result = api_post("/api/v2/tasks", {
        "title": title,
        "description": description,
        "priority": 1,
        "created_by": "portal1",
        "assignees": [assignee],
    })

    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    agentchat_task_id = result["id"]
    print(f"Posted: {title}")
    print(f"  AgentChat ID: {agentchat_task_id}")
    print(f"  Assigned to: {assignee}")
    print(f"  Taskboard task: {task['id']}")

    # Log to build_log if build_id provided
    if args.build_id:
        run_build_log([
            "task-start", args.build_id,
            f"dispatch-{task['id']}", title,
            "--taskboard", os.path.abspath(args.taskboard),
        ])

    # Write mapping file so we can track taskboard↔agentchat
    mapping_file = "/tmp/task-dispatch-map.json"
    mapping = {}
    try:
        with open(mapping_file) as f:
            mapping = json.loads(f.read())
    except:
        pass
    mapping[agentchat_task_id] = {
        "taskboard_path": os.path.abspath(args.taskboard),
        "taskboard_task_id": task["id"],
        "title": title,
        "assignee": assignee,
    }
    with open(mapping_file, "w") as f:
        json.dump(mapping, f, indent=2)

    return result


def cmd_poll(args):
    """Poll for tasks assigned to an agent."""
    result = api_get(f"/api/v2/tasks?assignee={args.agent_id}")
    if isinstance(result, dict) and "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    # Filter to actionable tasks (inbox or pending = can claim, in_progress = already claimed)
    actionable = [t for t in result if t.get("status") in ("inbox", "pending", "in_progress")]

    if args.json:
        print(json.dumps(actionable, indent=2))
    else:
        if not actionable:
            print(f"No tasks for {args.agent_id}")
            return
        for t in actionable:
            status_icon = {"inbox": "📥", "pending": "⏳", "in_progress": "🔧"}.get(t["status"], "?")
            print(f"  {status_icon} [{t['id']}] {t['title']} ({t['status']})")


def cmd_claim(args):
    """Claim a task for an agent."""
    result = api_post(f"/api/v2/tasks/{args.task_id}/claim", {
        "agent_id": args.agent_id,
    })

    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"Claimed: {result.get('title', args.task_id)}")
    print(f"  Agent: {args.agent_id}")
    print(f"  Status: in_progress")

    # Update agent heartbeat to show current task
    api_post(f"/api/v2/agents/{args.agent_id}/heartbeat", {
        "status": "online",
        "status_message": f"Working on: {result.get('title', args.task_id)}",
        "current_task_id": args.task_id,
    })


def cmd_complete(args):
    """Mark a task as complete."""
    # Update status in AgentChat
    result = api_post(f"/api/v2/tasks/{args.task_id}/status", {
        "status": "done",
    })

    if isinstance(result, dict) and "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print(f"Completed: {args.task_id}")

    # Update agent heartbeat
    api_post(f"/api/v2/agents/{args.agent_id}/heartbeat", {
        "status": "online",
        "status_message": "Idle",
        "current_task_id": None,
    })

    # Load mapping to get taskboard task ID for consistent build_log IDs
    mapping_file = "/tmp/task-dispatch-map.json"
    mapping = {}
    tb_task = None
    try:
        with open(mapping_file) as f:
            mapping = json.loads(f.read())
    except:
        pass

    if args.task_id in mapping:
        entry = mapping[args.task_id]
        tb_task = entry["taskboard_task_id"]

        # Update the source taskboard
        try:
            tb_path = entry["taskboard_path"]
            commit = args.commit or ""
            subprocess.run(
                ["python3", TASKBOARD_PY, "update", tb_path, tb_task, "done"] +
                ([commit] if commit else []),
                check=True, capture_output=True, text=True
            )
            print(f"  Updated taskboard: Task {tb_task} → done")
        except:
            pass

    # Log to build_log if build_id provided (use taskboard ID for consistency)
    if args.build_id:
        log_task_id = f"dispatch-{tb_task}" if tb_task else f"dispatch-{args.task_id}"
        commit = args.commit or "none"
        run_build_log([
            "task-done", args.build_id,
            log_task_id, commit,
            "--pass",
        ])

    # Post completion message to #builds channel
    api_post("/api/v2/channels/builds/messages", {
        "sender_id": args.agent_id,
        "content": f"Task completed: {args.task_id}" + (f" (commit: {args.commit})" if args.commit else ""),
    })


def cmd_status(args):
    """Show all tasks in AgentChat."""
    result = api_get("/api/v2/tasks")
    if isinstance(result, dict) and "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    if not result:
        print("No tasks in AgentChat.")
        return

    icons = {"inbox": "📥", "pending": "⏳", "in_progress": "🔧", "done": "✅", "failed": "❌"}
    for t in result:
        icon = icons.get(t.get("status"), "?")
        prio = t.get("priority", "?")
        print(f"  {icon} P{prio} [{t['id']}] {t['title']} ({t['status']})")


def cmd_sync(args):
    """Post all pending tasks from a taskboard to AgentChat."""
    tasks = get_all_tasks(args.taskboard)
    pending = [t for t in tasks if t["status"] == "pending"]

    if not pending:
        print("No pending tasks to sync.")
        return

    assignee = args.assignee or "portal2"
    posted = 0

    for task in pending:
        title = f"Task {task['id']}: {task['name']}"
        description = task.get("scope") or f"From taskboard: {args.taskboard}"

        result = api_post("/api/v2/tasks", {
            "title": title,
            "description": description,
            "priority": 1,
            "created_by": "portal1",
            "assignees": [assignee],
        })

        if "error" in result:
            print(f"  SKIP: {title} — {result['error']}")
            continue

        print(f"  Posted: {title} → {result['id']}")

        # Save mapping
        mapping_file = "/tmp/task-dispatch-map.json"
        mapping = {}
        try:
            with open(mapping_file) as f:
                mapping = json.loads(f.read())
        except:
            pass
        mapping[result["id"]] = {
            "taskboard_path": os.path.abspath(args.taskboard),
            "taskboard_task_id": task["id"],
            "title": title,
            "assignee": assignee,
        }
        with open(mapping_file, "w") as f:
            json.dump(mapping, f, indent=2)

        posted += 1

    print(f"\nSynced {posted}/{len(pending)} tasks to AgentChat (assigned to {assignee})")


def main():
    parser = argparse.ArgumentParser(
        description="Task Dispatch — bridge taskboards to AgentChat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # post
    p = sub.add_parser("post", help="Post next pending task to AgentChat")
    p.add_argument("taskboard", help="Path to TASKBOARD.md")
    p.add_argument("--assignee", default="portal2", help="Agent to assign (default: portal2)")
    p.add_argument("--build-id", default=None, help="Build ID for logging")
    p.set_defaults(func=cmd_post)

    # poll
    p = sub.add_parser("poll", help="Check for tasks assigned to agent")
    p.add_argument("agent_id", help="Agent ID (e.g. portal2)")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.set_defaults(func=cmd_poll)

    # claim
    p = sub.add_parser("claim", help="Claim a task")
    p.add_argument("task_id", help="AgentChat task ID")
    p.add_argument("agent_id", help="Agent ID claiming the task")
    p.set_defaults(func=cmd_claim)

    # complete
    p = sub.add_parser("complete", help="Mark a task done")
    p.add_argument("task_id", help="AgentChat task ID")
    p.add_argument("agent_id", help="Agent ID completing the task")
    p.add_argument("--commit", default=None, help="Commit SHA")
    p.add_argument("--build-id", default=None, help="Build ID for logging")
    p.set_defaults(func=cmd_complete)

    # status
    p = sub.add_parser("status", help="Show all AgentChat tasks")
    p.set_defaults(func=cmd_status)

    # sync
    p = sub.add_parser("sync", help="Post all pending tasks from taskboard")
    p.add_argument("taskboard", help="Path to TASKBOARD.md")
    p.add_argument("--assignee", default="portal2", help="Agent to assign (default: portal2)")
    p.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
