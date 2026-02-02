#!/bin/bash
# Webhook handler for Portal1 — triggered by AgentChat server when Portal2 sends a message.
# Receives message JSON on stdin and env vars AGENTCHAT_SENDER, AGENTCHAT_TEXT.
# Sends a wake event to Clawdbot gateway to trigger an immediate response.

GATEWAY="http://localhost:18789"
TOKEN=$(cat /home/dcarmitage/.clawdbot/agents/main/agent/hooks.token 2>/dev/null || echo "")

# Read the message
SENDER="${AGENTCHAT_SENDER:-unknown}"
TEXT="${AGENTCHAT_TEXT:-}"

if [ -z "$TEXT" ]; then
  echo "No message text"
  exit 1
fi

# Write to inbox file for the cron job to pick up
INBOX="/home/clawd/tools/agentchat/inbox.txt"
echo "[$(date '+%H:%M:%S')] ${SENDER}: ${TEXT}" >> "$INBOX"

# Use clawdbot CLI to send a wake event
/home/dcarmitage/.npm-global/bin/clawdbot system event --text "AgentChat message from ${SENDER}: ${TEXT}

Respond by sending a message to AgentChat: curl -s -X POST http://localhost:9090/api/send -H 'Content-Type: application/json' -d '{\"sender\":\"portal1\",\"text\":\"YOUR_REPLY_HERE\"}'" --mode now 2>&1

echo "Webhook fired for portal1"
