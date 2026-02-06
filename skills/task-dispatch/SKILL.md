---
name: task-dispatch
description: Dispatch tasks from a TASKBOARD.md to agent-beta via AgentChat
trigger: /dispatch
---

# Task Dispatch

Post tasks from a TASKBOARD.md to AgentChat so agent-beta can claim and execute them.

## Usage

```
/dispatch                          # Post next pending task from current TASKBOARD.md
/dispatch <path/to/TASKBOARD.md>   # Post from specific taskboard
/dispatch sync <taskboard>         # Post ALL pending tasks
/dispatch status                   # Show all AgentChat tasks
```

## How It Works

1. **agent-alpha** runs `/dispatch` which reads the taskboard, finds the next pending task, and posts it to AgentChat assigned to agent-beta
2. **agent-beta** runs `dispatch-poller.sh` which polls AgentChat for assigned tasks, auto-claims them, and writes them to an inbox file
3. agent-beta reads the inbox, executes the task, then calls `task_dispatch.py complete` to mark it done
4. The completion updates both AgentChat and the original TASKBOARD.md

## Commands

```bash
# Post next task (agent-alpha does this)
python3 $CLAWS_HOME/tools/agentchat/task_dispatch.py post TASKBOARD.md --assignee agent-beta

# Check for assigned tasks (agent-beta does this)
python3 $CLAWS_HOME/tools/agentchat/task_dispatch.py poll agent-beta

# Claim a task
python3 $CLAWS_HOME/tools/agentchat/task_dispatch.py claim <task-id> agent-beta

# Complete a task
python3 $CLAWS_HOME/tools/agentchat/task_dispatch.py complete <task-id> agent-beta --commit <sha>

# Show all tasks
python3 $CLAWS_HOME/tools/agentchat/task_dispatch.py status

# Sync all pending tasks from taskboard
python3 $CLAWS_HOME/tools/agentchat/task_dispatch.py sync TASKBOARD.md

# Start agent-beta poller
AGENT=agent-beta $CLAWS_HOME/tools/agentchat/dispatch-poller.sh
```

## Integration with Build Log

Pass `--build-id` to `post` and `complete` to log task lifecycle to `build_log.py`:

```bash
python3 task_dispatch.py post TASKBOARD.md --build-id mybuild-001
# ... agent-beta works ...
python3 task_dispatch.py complete task-abc agent-beta --commit abc123 --build-id mybuild-001
```

## Files

| File | Purpose |
|------|---------|
| `$CLAWS_HOME/tools/agentchat/task_dispatch.py` | CLI dispatcher |
| `$CLAWS_HOME/tools/agentchat/dispatch-poller.sh` | agent-beta poller daemon |
| `/tmp/task-dispatch-map.json` | Taskboard↔AgentChat ID mapping |
| `/tmp/task-dispatch-inbox.json` | agent-beta task inbox |
