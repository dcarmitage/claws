#!/usr/bin/env python3
"""TASKBOARD.md parser — parse, query, and update task status."""

import argparse
import json
import re
import sys

STATUS_MAP = {'⬜': 'pending', '✅': 'done', '❌': 'failed'}
REVERSE_MAP = {'pending': '⬜', 'done': '✅', 'failed': '❌'}

TASK_RE = re.compile(
    r'^###\s+Task\s+(\d+):\s+(.+?)\s+(⬜|✅|❌)(?:\s+\(([a-f0-9]+)\))?',
)
DEPENDS_RE = re.compile(r'^\*\*Depends on:\*\*\s*(.*)', re.IGNORECASE)
SCOPE_RE = re.compile(r'^\*\*Scope:\*\*\s*(.*)', re.IGNORECASE)
TITLE_RE = re.compile(r'^#\s+(.+)')


def parse_tasks(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    tasks = []
    current = None

    for line in lines:
        m = TASK_RE.match(line.strip())
        if m:
            if current:
                tasks.append(current)
            current = {
                'id': m.group(1),
                'name': m.group(2).strip(),
                'status': STATUS_MAP[m.group(3)],
                'commit': m.group(4) or None,
                'depends_on': [],
                'scope': None,
            }
            continue

        if current:
            dm = DEPENDS_RE.match(line.strip())
            if dm:
                dep_text = dm.group(1).strip()
                if dep_text.lower() in ('none', ''):
                    current['depends_on'] = []
                else:
                    current['depends_on'] = re.findall(r'Task\s+(\d+)', dep_text)
                continue

            sm = SCOPE_RE.match(line.strip())
            if sm:
                current['scope'] = sm.group(1).strip()
                continue

    if current:
        tasks.append(current)

    return tasks


def get_title(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            m = TITLE_RE.match(line.strip())
            if m:
                return m.group(1).strip()
    return 'Untitled'


def cmd_parse(args):
    tasks = parse_tasks(args.file)
    print(json.dumps(tasks, indent=2))


def cmd_next(args):
    tasks = parse_tasks(args.file)
    done_ids = {t['id'] for t in tasks if t['status'] == 'done'}

    for t in tasks:
        if t['status'] != 'pending':
            continue
        if all(d in done_ids for d in t['depends_on']):
            print(json.dumps(t, indent=2))
            return

    print('null')


def cmd_status(args):
    tasks = parse_tasks(args.file)
    title = get_title(args.file)

    done = sum(1 for t in tasks if t['status'] == 'done')
    pending = sum(1 for t in tasks if t['status'] == 'pending')
    failed = sum(1 for t in tasks if t['status'] == 'failed')

    done_ids = {t['id'] for t in tasks if t['status'] == 'done'}
    next_task = None
    for t in tasks:
        if t['status'] == 'pending' and all(d in done_ids for d in t['depends_on']):
            next_task = t
            break

    print(f'TASKBOARD: {title}')
    print(f'Done: {done}  Pending: {pending}  Failed: {failed}')
    if next_task:
        print(f'Next: Task {next_task["id"]} - {next_task["name"]}')
    else:
        print('Next: (none)')


def cmd_update(args):
    filepath = args.file
    task_num = args.task_num
    new_status = args.status
    commit = args.commit

    if new_status not in REVERSE_MAP:
        print(f'Error: status must be one of {list(REVERSE_MAP.keys())}', file=sys.stderr)
        sys.exit(1)

    emoji = REVERSE_MAP[new_status]
    suffix = f' ({commit})' if new_status == 'done' and commit else ''

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    pattern = re.compile(
        r'^(###\s+Task\s+' + re.escape(task_num) + r':\s+.+?)\s+(?:⬜|✅|❌)(?:\s+\([a-f0-9]+\))?'
    )

    found = False
    for i, line in enumerate(lines):
        m = pattern.match(line.rstrip('\n'))
        if m:
            lines[i] = m.group(1) + ' ' + emoji + suffix + '\n'
            found = True
            break

    if not found:
        print(f'Error: Task {task_num} not found', file=sys.stderr)
        sys.exit(1)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f'Updated Task {task_num} → {new_status}{suffix}')


def main():
    parser = argparse.ArgumentParser(description='TASKBOARD.md parser')
    sub = parser.add_subparsers(dest='command', required=True)

    p_parse = sub.add_parser('parse', help='Parse tasks to JSON')
    p_parse.add_argument('file')
    p_parse.set_defaults(func=cmd_parse)

    p_next = sub.add_parser('next', help='Next actionable task')
    p_next.add_argument('file')
    p_next.set_defaults(func=cmd_next)

    p_status = sub.add_parser('status', help='Human-readable summary')
    p_status.add_argument('file')
    p_status.set_defaults(func=cmd_status)

    p_update = sub.add_parser('update', help='Update task status')
    p_update.add_argument('file')
    p_update.add_argument('task_num')
    p_update.add_argument('status', choices=['pending', 'done', 'failed'])
    p_update.add_argument('commit', nargs='?', default=None)
    p_update.set_defaults(func=cmd_update)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
