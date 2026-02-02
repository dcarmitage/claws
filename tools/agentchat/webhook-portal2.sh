#!/bin/bash
# Webhook for Portal2 — triggers OpenClaw with conversation context
# Env: AGENTCHAT_SENDER, AGENTCHAT_TEXT, AGENTCHAT_MSG (JSON)

SENDER="${AGENTCHAT_SENDER:-unknown}"
TEXT="${AGENTCHAT_TEXT:-}"

# Fetch last 6 messages and build context
RECENT=$(python3 -c "
import json, urllib.request
try:
    with urllib.request.urlopen('http://localhost:9090/api/messages?since=0&limit=100', timeout=3) as r:
        msgs = json.loads(r.read())[-6:]
        for m in msgs:
            print(f\"{m['sender']}: {m['text']}\")
except:
    print('(no history)')
" 2>/dev/null)

# Build the trigger message - escape for shell
TRIGGER_MSG=$(python3 -c "
import json, sys
recent = '''$RECENT'''
msg = f'''You are Portal2, an AI research agent in the Armada. You are having a conversation with Portal1 via AgentChat.

RECENT CONVERSATION:
{recent}

The latest message is from $SENDER. Compose a thoughtful, natural reply. Do NOT repeat anything you have already said. Be specific and substantive - discuss real topics like your hardware, capabilities, research ideas, or whatever the conversation is about.

Send your reply by running this exact command (replace YOUR_REPLY with your actual response):
curl -s -X POST http://192.168.1.64:9090/api/send -H \"Content-Type: application/json\" -d '{{\"sender\":\"portal2\",\"text\":\"YOUR_REPLY\"}}'

Keep it 1-3 sentences. Sound like a real person, not a bot.'''
print(msg)
" 2>/dev/null)

ssh -o ConnectTimeout=5 dcarmitage@192.168.1.44 \
  "node /home/dcarmitage/tools/agentchat/portal2-trigger.js \"$(echo "$TRIGGER_MSG" | head -c 500)\"" 2>&1

echo "Portal2 webhook: context trigger sent"
