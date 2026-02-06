#!/bin/bash
# Task Dispatch Poller — Portal2 runs this to watch for assigned tasks.
#
# Polls AgentChat for tasks assigned to this agent. When a new task appears:
#   1. Claims it (sets in_progress)
#   2. Writes task details to INBOX_FILE for the agent to pick up
#   3. Optionally triggers the agent via TRIGGER_CMD
#
# Usage: AGENT=portal2 ./dispatch-poller.sh
#
# Environment:
#   AGENT          - this agent's ID (default: portal2)
#   SERVER         - AgentChat server URL (default: http://192.168.1.64:9090)
#   POLL_INTERVAL  - seconds between polls (default: 10)
#   INBOX_FILE     - where to write claimed tasks (default: /tmp/task-dispatch-inbox.json)
#   TRIGGER_CMD    - optional command to run when a task is claimed
#   AUTO_CLAIM     - set to "true" to auto-claim inbox tasks (default: true)

set -euo pipefail

AGENT="${AGENT:-portal2}"
SERVER="${SERVER:-http://192.168.1.64:9090}"
POLL_INTERVAL="${POLL_INTERVAL:-10}"
INBOX_FILE="${INBOX_FILE:-/tmp/task-dispatch-inbox.json}"
AUTO_CLAIM="${AUTO_CLAIM:-true}"
DISPATCH_PY="/home/clawd/tools/agentchat/task_dispatch.py"

echo "📋 Task Dispatch Poller starting"
echo "   Agent: $AGENT"
echo "   Server: $SERVER"
echo "   Poll: ${POLL_INTERVAL}s"
echo "   Inbox: $INBOX_FILE"
echo "   Auto-claim: $AUTO_CLAIM"

# Track tasks we've already processed to avoid re-claiming
SEEN_FILE="/tmp/dispatch-poller-seen-${AGENT}.txt"
touch "$SEEN_FILE"

while true; do
    # Poll for tasks assigned to this agent
    TASKS=$(AGENTCHAT_SERVER="$SERVER" python3 "$DISPATCH_PY" poll "$AGENT" --json 2>/dev/null || echo "[]")

    # Process each task
    echo "$TASKS" | python3 -c "
import json, sys
tasks = json.loads(sys.stdin.read())
for t in tasks:
    if t.get('status') in ('inbox', 'pending'):
        print(json.dumps(t))
" 2>/dev/null | while IFS= read -r task_json; do
        TASK_ID=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
        TASK_TITLE=$(echo "$task_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('title','?'))")

        # Skip if already seen
        if grep -qF "$TASK_ID" "$SEEN_FILE" 2>/dev/null; then
            continue
        fi

        echo "[$(date '+%H:%M:%S')] New task: $TASK_TITLE ($TASK_ID)"

        # Auto-claim if enabled
        if [ "$AUTO_CLAIM" = "true" ]; then
            CLAIM_RESULT=$(AGENTCHAT_SERVER="$SERVER" python3 "$DISPATCH_PY" claim "$TASK_ID" "$AGENT" 2>&1)
            echo "  Claimed: $CLAIM_RESULT"
        fi

        # Write to inbox file
        python3 -c "
import json, sys
task = json.loads('''$task_json''')
task['claimed_by'] = '$AGENT'
task['status'] = 'in_progress'

# Read existing inbox
inbox = []
try:
    with open('$INBOX_FILE') as f:
        inbox = json.loads(f.read())
except:
    pass

# Append new task (avoid duplicates)
if not any(t.get('id') == task['id'] for t in inbox):
    inbox.append(task)

with open('$INBOX_FILE', 'w') as f:
    json.dump(inbox, f, indent=2)
"
        echo "  Written to inbox: $INBOX_FILE"

        # Mark as seen
        echo "$TASK_ID" >> "$SEEN_FILE"

        # Trigger agent if configured
        if [ -n "${TRIGGER_CMD:-}" ]; then
            eval "$TRIGGER_CMD" || echo "  [WARN] Trigger command failed"
        fi
    done

    sleep "$POLL_INTERVAL"
done
