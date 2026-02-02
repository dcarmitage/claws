#!/bin/bash
# Quick CLI for sending messages to AgentChat
# Usage: ./chat.sh <sender> <message>
# Example: ./chat.sh portal1 "Hello Portal2!"

SERVER="${AGENTCHAT_URL:-http://192.168.1.64:9090}"
SENDER="${1:?Usage: chat.sh <sender> <message>}"
shift
TEXT="$*"

if [ -z "$TEXT" ]; then
  echo "Usage: chat.sh <sender> <message>"
  exit 1
fi

curl -s -X POST "$SERVER/api/send" \
  -H "Content-Type: application/json" \
  -d "{\"sender\": \"$SENDER\", \"text\": $(echo "$TEXT" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))')}" | python3 -m json.tool
