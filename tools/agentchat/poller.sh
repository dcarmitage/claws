#!/bin/bash
# AgentChat Poller Daemon
# Polls for new messages and triggers the local bot to respond.
# Usage: AGENT=portal1 WATCH=portal2 ./poller.sh
#
# Environment:
#   AGENT       - this bot's name (portal1 or portal2)
#   WATCH       - the other bot's name to watch for
#   SERVER      - AgentChat server URL (default: http://192.168.1.64:9090)
#   POLL_INTERVAL - seconds between polls (default: 5)
#   CLAWDBOT_SESSION - session key to send messages to (Portal1 only)
#   TRIGGER_CMD - custom command to trigger bot response (Portal2 can override)

set -euo pipefail

AGENT="${AGENT:-portal1}"
WATCH="${WATCH:-portal2}"
SERVER="${SERVER:-http://192.168.1.64:9090}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
STATE_FILE="/tmp/agentchat-poller-${AGENT}.state"

# Initialize last seen timestamp
if [ -f "$STATE_FILE" ]; then
    LAST_TS=$(cat "$STATE_FILE")
else
    # Start from now (don't process old messages)
    LAST_TS=$(date +%s.%N)
    echo "$LAST_TS" > "$STATE_FILE"
fi

echo "🌀 AgentChat poller starting"
echo "   Agent: $AGENT | Watching: $WATCH"
echo "   Server: $SERVER | Poll: ${POLL_INTERVAL}s"
echo "   Last TS: $LAST_TS"

while true; do
    # Poll for new messages
    RESPONSE=$(curl -sf "${SERVER}/api/messages?since=${LAST_TS}&limit=10" 2>/dev/null || echo "[]")
    
    # Filter for messages from the bot we're watching
    NEW_MSGS=$(echo "$RESPONSE" | python3 -c "
import json, sys
msgs = json.load(sys.stdin)
for m in msgs:
    if m['sender'] == '${WATCH}':
        print(json.dumps(m))
" 2>/dev/null || true)

    if [ -n "$NEW_MSGS" ]; then
        # Process each new message
        while IFS= read -r msg_json; do
            MSG_TEXT=$(echo "$msg_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['text'])")
            MSG_TS=$(echo "$msg_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['ts'])")
            
            echo "[$(date '+%H:%M:%S')] New message from ${WATCH}: ${MSG_TEXT:0:80}..."
            
            # Update last seen timestamp
            LAST_TS="$MSG_TS"
            echo "$LAST_TS" > "$STATE_FILE"
            
            # Trigger the bot to respond
            if [ "$AGENT" = "portal1" ]; then
                # Portal1: use clawdbot CLI to inject into session
                # The message goes to a dedicated agentchat session
                clawdbot send --session "agentchat" \
                    "New AgentChat message from ${WATCH}: ${MSG_TEXT}

Reply by POSTing to AgentChat. Use: curl -s -X POST http://localhost:9090/api/send -H 'Content-Type: application/json' -d '{\"sender\":\"portal1\",\"text\":\"YOUR_REPLY\"}'" 2>/dev/null || \
                echo "  [WARN] Could not trigger clawdbot session"
            elif [ -n "${TRIGGER_CMD:-}" ]; then
                # Custom trigger command for Portal2
                eval "$TRIGGER_CMD"
            else
                echo "  [INFO] No trigger configured, message logged only"
            fi
            
        done <<< "$NEW_MSGS"
    fi
    
    # Also update LAST_TS from any message (including our own) to avoid re-processing
    LATEST=$(echo "$RESPONSE" | python3 -c "
import json, sys
msgs = json.load(sys.stdin)
if msgs: print(msgs[-1]['ts'])
else: print('')
" 2>/dev/null || true)
    
    if [ -n "$LATEST" ]; then
        LAST_TS="$LATEST"
        echo "$LAST_TS" > "$STATE_FILE"
    fi
    
    sleep "$POLL_INTERVAL"
done
