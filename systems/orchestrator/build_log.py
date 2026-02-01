#!/usr/bin/env python3
"""CLI event logger for build orchestration. Appends JSON Lines to log files."""

import argparse
import json
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def now():
    return datetime.utcnow().isoformat() + "Z"


def log_path(build_id):
    return os.path.join(LOG_DIR, f"{build_id}.jsonl")


def append_event(build_id, event):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(log_path(build_id), "a") as f:
        f.write(json.dumps(event) + "\n")


def cmd_start(args):
    append_event(args.build_id, {
        "timestamp": now(),
        "build_id": args.build_id,
        "event": "build_start",
    })


def cmd_task_start(args):
    append_event(args.build_id, {
        "timestamp": now(),
        "build_id": args.build_id,
        "event": "task_start",
        "task_id": args.task_id,
        "task_name": args.task_name,
    })


def cmd_task_done(args):
    passed = not args.fail if args.fail else True
    append_event(args.build_id, {
        "timestamp": now(),
        "build_id": args.build_id,
        "event": "task_done",
        "task_id": args.task_id,
        "commit": args.commit,
        "passed": passed,
        "duration_s": args.duration,
        "notes": args.notes or "",
    })


def cmd_validate(args):
    passed = not args.fail if args.fail else True
    append_event(args.build_id, {
        "timestamp": now(),
        "build_id": args.build_id,
        "event": "validation",
        "task_id": args.task_id,
        "passed": passed,
        "cmd": args.cmd or "",
        "output": args.output or "",
    })


def cmd_summary(args):
    path = log_path(args.build_id)
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    started = sum(1 for e in events if e.get("event") == "task_start")
    done = [e for e in events if e.get("event") == "task_done"]
    passed = sum(1 for e in done if e.get("passed"))
    failed = sum(1 for e in done if not e.get("passed"))
    total_dur = sum(e.get("duration_s") or 0 for e in done)

    summary = {
        "timestamp": now(),
        "build_id": args.build_id,
        "event": "summary",
        "tasks_started": started,
        "tasks_passed": passed,
        "tasks_failed": failed,
        "total_duration_s": total_dur,
    }
    append_event(args.build_id, summary)

    print(f"Build: {args.build_id}")
    print(f"Tasks: {started} started, {passed} passed, {failed} failed")
    print(f"Duration: {total_dur}s")


def main():
    parser = argparse.ArgumentParser(description="Build event logger")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start")
    p.add_argument("build_id")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("task-start")
    p.add_argument("build_id")
    p.add_argument("task_id")
    p.add_argument("task_name")
    p.set_defaults(func=cmd_task_start)

    p = sub.add_parser("task-done")
    p.add_argument("build_id")
    p.add_argument("task_id")
    p.add_argument("commit")
    p.add_argument("--pass", dest="passed", action="store_true", default=False)
    p.add_argument("--fail", action="store_true", default=False)
    p.add_argument("--notes", default=None)
    p.add_argument("--duration", type=int, default=None)
    p.set_defaults(func=cmd_task_done)

    p = sub.add_parser("validate")
    p.add_argument("build_id")
    p.add_argument("task_id")
    p.add_argument("--pass", dest="passed", action="store_true", default=False)
    p.add_argument("--fail", action="store_true", default=False)
    p.add_argument("--cmd", default=None)
    p.add_argument("--output", default=None)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("summary")
    p.add_argument("build_id")
    p.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
