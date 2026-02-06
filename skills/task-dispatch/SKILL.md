---
name: task-dispatch
description: Dispatch tasks from a TASKBOARD.md to Portal2 via AgentChat
trigger: /dispatch
---

# Task Dispatch

Post tasks from a TASKBOARD.md to AgentChat so Portal2 can claim and execute them.

## Usage

```
/dispatch                          # Post next pending task from current TASKBOARD.md
/dispatch <path/to/TASKBOARD.md>   # Post from specific taskboard
/dispatch sync <taskboard>         # Post ALL pending tasks
/dispatch status                   # Show all AgentChat tasks
```

## How It Works

1. **Portal1** runs `/dispatch` which reads the taskboard, finds the next pending task, and posts it to AgentChat assigned to Portal2
2. **Portal2** runs `dispatch-poller.sh` which polls AgentChat for assigned tasks, auto-claims them, and writes them to an inbox file
3. Portal2 reads the inbox, executes the task, then calls `task_dispatch.py complete` to mark it done
4. The completion updates both AgentChat and the original TASKBOARD.md

## Commands

```bash
# Post next task (Portal1 does this)
python3 /home/clawd/tools/agentchat/task_dispatch.py post TASKBOARD.md --assignee portal2

# Check for assigned tasks (Portal2 does this)
python3 /home/clawd/tools/agentchat/task_dispatch.py poll portal2

# Claim a task
python3 /home/clawd/tools/agentchat/task_dispatch.py claim <task-id> portal2

# Complete a task
python3 /home/clawd/tools/agentchat/task_dispatch.py complete <task-id> portal2 --commit <sha>

# Show all tasks
python3 /home/clawd/tools/agentchat/task_dispatch.py status

# Sync all pending tasks from taskboard
python3 /home/clawd/tools/agentchat/task_dispatch.py sync TASKBOARD.md

# Start Portal2 poller
AGENT=portal2 /home/clawd/tools/agentchat/dispatch-poller.sh
```

## Integration with Build Log

Pass `--build-id` to `post` and `complete` to log task lifecycle to `build_log.py`:

```bash
python3 task_dispatch.py post TASKBOARD.md --build-id mybuild-001
# ... Portal2 works ...
python3 task_dispatch.py complete task-abc portal2 --commit abc123 --build-id mybuild-001
```

## Files

| File | Purpose |
|------|---------|
| `/home/clawd/tools/agentchat/task_dispatch.py` | CLI dispatcher |
| `/home/clawd/tools/agentchat/dispatch-poller.sh` | Portal2 poller daemon |
| `/tmp/task-dispatch-map.json` | Taskboard↔AgentChat ID mapping |
| `/tmp/task-dispatch-inbox.json` | Portal2 task inbox |
