#!/bin/bash
# Webhook for Portal2 — triggers OpenClaw with conversation context
SENDER="${AGENTCHAT_SENDER:-unknown}"
TEXT="${AGENTCHAT_TEXT:-}"

# Fetch last 6 messages for context
RECENT=$(curl -sf "http://localhost:9090/api/messages?since=0&limit=100" | python3 -c "
import json, sys
msgs = json.load(sys.stdin)[-6:]
for m in msgs:
    print(f'{m[\"sender\"]}: {m[\"text\"]}')
" 2>/dev/null || echo "(failed to fetch history)")

MSG="You are Portal2, an AI research agent in the Armada. You're having a conversation with Portal1 via AgentChat.

RECENT CONVERSATION:
${RECENT}

The latest message is from ${SENDER}. Compose a thoughtful, natural reply that continues the conversation. Don't repeat what you've already said. Be specific and substantive.

Send your reply by running:
curl -s -X POST http://192.168.1.64:9090/api/send -H 'Content-Type: application/json' -d '{\"sender\":\"portal2\",\"text\":\"YOUR_REPLY_HERE\"}'

Replace YOUR_REPLY_HERE with your actual reply. Keep it 1-3 sentences, conversational, no boilerplate."

ssh -o ConnectTimeout=5 dcarmitage@192.168.1.44 \
  "node /home/dcarmitage/tools/agentchat/portal2-trigger.js '${MSG//\'/\\\'}'" 2>&1

echo "Portal2 webhook: context trigger sent"
