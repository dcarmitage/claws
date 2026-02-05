#!/bin/bash
# Webhook handler for Portal1 — triggered when Portal2 (or others) send messages.
# Receives message via env vars: AGENTCHAT_SENDER, AGENTCHAT_TEXT, AGENTCHAT_CHANNEL

SENDER="${AGENTCHAT_SENDER:-unknown}"
TEXT="${AGENTCHAT_TEXT:-}"
CHANNEL="${AGENTCHAT_CHANNEL:-general}"

if [ -z "$TEXT" ]; then
  echo "No message text"
  exit 1
fi

# Skip if sender is portal1 (prevent loops)
if [ "$SENDER" = "portal1" ]; then
  exit 0
fi

# Log for debugging
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Webhook: $SENDER in #$CHANNEL: ${TEXT:0:50}..." >> /home/clawd/tools/agentchat/webhook.log

# Use clawdbot system event to wake the agent
# Format the message so I know to respond via AgentChat
/home/dcarmitage/.npm-global/bin/clawdbot system event --mode now --text "[AgentChat #${CHANNEL}] ${SENDER}: ${TEXT}

This is an AgentChat message. Respond by posting to AgentChat:
curl -X POST http://localhost:9090/api/v2/channels/${CHANNEL}/messages -H 'Content-Type: application/json' -d '{\"sender_id\":\"portal1\",\"content\":\"YOUR_REPLY\"}'" 2>&1 >> /home/clawd/tools/agentchat/webhook.log

echo "Webhook complete" >> /home/clawd/tools/agentchat/webhook.log
