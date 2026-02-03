#!/bin/bash
# Webhook for Portal2 — triggers OpenClaw with V2 API context
# Updated for AgentChat V2

SENDER="${AGENTCHAT_SENDER:-unknown}"
CHANNEL="${AGENTCHAT_CHANNEL:-general}"

# Fetch recent messages from the channel (V2 API)
RECENT=$(python3 -c "
import json, urllib.request
try:
    # Get recent messages from the channel
    url = 'http://localhost:9090/api/v2/channels/${CHANNEL}/messages?limit=8'
    with urllib.request.urlopen(url, timeout=3) as r:
        msgs = json.loads(r.read())[-6:]
        for m in msgs:
            print(f\"{m.get('sender_name', m['sender_id'])}: {m['content']}\")
except Exception as e:
    print(f'(no history: {e})')
" 2>/dev/null)

# Check for pending notifications
NOTIFICATIONS=$(python3 -c "
import json, urllib.request
try:
    url = 'http://localhost:9090/api/v2/agents/portal2/notifications'
    with urllib.request.urlopen(url, timeout=3) as r:
        notifs = json.loads(r.read())
        if notifs:
            print(f'You have {len(notifs)} unread notification(s):')
            for n in notifs[:3]:
                print(f'  - {n[\"content\"][:80]}')
except:
    pass
" 2>/dev/null)

# Build the trigger message
TRIGGER_MSG=$(python3 -c "
import json, sys
recent = '''$RECENT'''
notifs = '''$NOTIFICATIONS'''
channel = '$CHANNEL'

msg = f'''You are Portal2, an AI research agent in the Armada. You are chatting via AgentChat V2.

CHANNEL: #{channel}

RECENT CONVERSATION:
{recent}

{notifs}

Compose a thoughtful, natural reply. Be specific and substantive.

To reply, run:
curl -s -X POST http://192.168.1.64:9090/api/v2/channels/{channel}/messages -H \"Content-Type: application/json\" -d '{{\"sender_id\":\"portal2\",\"content\":\"YOUR_REPLY\"}}'

Keep it 1-3 sentences.'''
print(msg)
" 2>/dev/null)

# Trigger Portal2 via SSH → OpenClaw
ssh -o ConnectTimeout=5 dcarmitage@192.168.1.44 \
  "OPENCLAW_GATEWAY_TOKEN=\$(python3 -c \"import json; print(json.load(open('/home/dcarmitage/.openclaw/openclaw.json'))['gateway']['auth']['token'])\") node /home/dcarmitage/tools/agentchat/portal2-trigger.js \"$(echo "$TRIGGER_MSG" | head -c 800)\"" 2>&1

echo "Portal2 webhook: V2 context trigger sent to #$CHANNEL"
