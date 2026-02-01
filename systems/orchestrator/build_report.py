#!/usr/bin/env python3
"""Build report generator — reads JSONL build logs and generates markdown reports."""

import argparse
import json
import os
import glob
from datetime import datetime

LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


def fmt_duration(seconds):
    """Format seconds as Xm Ys or Xs."""
    s = int(seconds)
    if s >= 60:
        return f"{s // 60}m {s % 60}s"
    return f"{s}s"


def read_log(path):
    """Read a JSONL file and return list of event dicts."""
    events = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def parse_build(events):
    """Parse events into structured build data."""
    build_date = None
    build_id = None
    tasks = {}  # task_id -> dict
    task_order = []

    for ev in events:
        e = ev.get("event")
        if e == "build_start":
            build_id = ev.get("build_id")
            ts = ev.get("timestamp", "")
            try:
                build_date = ts[:10]
            except Exception:
                build_date = "unknown"
        elif e == "task_start":
            tid = ev.get("task_id")
            tasks[tid] = {"name": ev.get("task_name", tid), "start": ev.get("timestamp")}
            task_order.append(tid)
        elif e == "task_done":
            tid = ev.get("task_id")
            if tid not in tasks:
                tasks[tid] = {"name": tid}
                task_order.append(tid)
            tasks[tid]["passed"] = ev.get("passed", False)
            tasks[tid]["duration"] = ev.get("duration_s", 0)
            tasks[tid]["commit"] = ev.get("commit", "")
            tasks[tid]["done"] = True

    ordered_tasks = []
    for tid in task_order:
        t = tasks[tid]
        ordered_tasks.append(t)

    return {"build_id": build_id, "date": build_date, "tasks": ordered_tasks}


def cmd_report(args):
    """Generate detailed report for a single build."""
    path = os.path.join(LOGS_DIR, f"{args.build_id}.jsonl")
    if not os.path.exists(path):
        print(f"Error: Log file not found: {path}")
        return

    build = parse_build(read_log(path))
    tasks = build["tasks"]

    done_tasks = [t for t in tasks if t.get("done")]
    passed = sum(1 for t in done_tasks if t.get("passed"))
    failed = len(done_tasks) - passed
    total_tasks = len(tasks)
    total_dur = sum(t.get("duration", 0) for t in tasks)

    commits = [t["commit"] for t in done_tasks if t.get("commit")]
    commit_range = f"{commits[0]}..{commits[-1]}" if len(commits) >= 2 else (commits[0] if commits else "none")

    print(f"# Build Report: {args.build_id}")
    print(f"**Date:** {build['date']}")
    print(f"**Tasks:** {passed}/{total_tasks} passed ({failed} failed)")
    print(f"**Total duration:** {fmt_duration(total_dur)}")
    print(f"**Commits:** {commit_range}")
    print()
    print("| # | Task | Duration | Result | Commit |")
    print("|---|------|----------|--------|--------|")
    for i, t in enumerate(tasks, 1):
        dur = fmt_duration(t.get("duration", 0)) if t.get("done") else "—"
        result = "✅" if t.get("passed") else ("❌" if t.get("done") else "⏳")
        commit = t.get("commit", "—") or "—"
        print(f"| {i} | {t['name']} | {dur} | {result} | {commit} |")


def cmd_history(args):
    """Generate summary table of all builds."""
    files = sorted(glob.glob(os.path.join(LOGS_DIR, "*.jsonl")))
    if not files:
        print("No build logs found.")
        return

    print("# Build History")
    print()
    print("| Build | Date | Tasks | Passed | Failed | Avg Time | Total |")
    print("|-------|------|-------|--------|--------|----------|-------|")

    for f in files:
        build = parse_build(read_log(f))
        tasks = build["tasks"]
        done = [t for t in tasks if t.get("done")]
        passed = sum(1 for t in done if t.get("passed"))
        failed = len(done) - passed
        total_count = len(tasks)
        durations = [t.get("duration", 0) for t in done]
        total_dur = sum(durations)
        avg_dur = total_dur / len(durations) if durations else 0
        bid = build["build_id"] or os.path.basename(f).replace(".jsonl", "")
        print(f"| {bid} | {build['date']} | {total_count} | {passed} | {failed} | {fmt_duration(avg_dur)} | {fmt_duration(total_dur)} |")


def cmd_metrics(args):
    """Aggregate stats across all builds."""
    files = glob.glob(os.path.join(LOGS_DIR, "*.jsonl"))
    if not files:
        print("No build logs found.")
        return

    total_builds = len(files)
    all_durations = []
    total_passed = 0
    total_tasks = 0

    for f in files:
        build = parse_build(read_log(f))
        for t in build["tasks"]:
            total_tasks += 1
            if t.get("done"):
                all_durations.append(t.get("duration", 0))
                if t.get("passed"):
                    total_passed += 1

    total_done = len(all_durations)
    pass_rate = (total_passed / total_done * 100) if total_done else 0
    avg_dur = sum(all_durations) / len(all_durations) if all_durations else 0

    print(f"Total builds: {total_builds}")
    print(f"Total tasks: {total_tasks}")
    print(f"Pass rate: {pass_rate:.0f}% ({total_passed}/{total_done})")
    print(f"Avg task duration: {fmt_duration(avg_dur)}")
    if all_durations:
        print(f"Fastest task: {fmt_duration(min(all_durations))}")
        print(f"Slowest task: {fmt_duration(max(all_durations))}")


def main():
    parser = argparse.ArgumentParser(description="Build report generator")
    sub = parser.add_subparsers(dest="command")

    rpt = sub.add_parser("report", help="Detailed report for a build")
    rpt.add_argument("build_id", help="Build ID (matches log filename)")

    sub.add_parser("history", help="Summary of all builds")
    sub.add_parser("metrics", help="Aggregate metrics across all builds")

    args = parser.parse_args()
    if args.command == "report":
        cmd_report(args)
    elif args.command == "history":
        cmd_history(args)
    elif args.command == "metrics":
        cmd_metrics(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
