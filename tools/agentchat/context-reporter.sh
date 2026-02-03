#!/bin/bash
# Reports context status to AgentChat server
# Called by cron/heartbeat on each agent
AGENT="${1:-portal1}"
SERVER="${2:-http://localhost:9090}"

# Get session info from clawdbot internal tool
CONTEXT_JSON=$(clawdbot session list --json 2>/dev/null)
if [ -z "$CONTEXT_JSON" ]; then
  echo '{"error":"no session data"}'
  exit 1
fi

# Post to AgentChat context endpoint
curl -s -X POST "$SERVER/api/context" \
  -H "Content-Type: application/json" \
  -d "{\"agent\":\"$AGENT\",\"sessions\":$CONTEXT_JSON}"
