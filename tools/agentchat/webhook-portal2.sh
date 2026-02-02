#!/bin/bash
# Webhook for Portal2 — pings Portal2 via Telegram Bot API @mention in Armada group.
# The Telegram message triggers Portal2 to check AgentChat and respond.

SENDER="${AGENTCHAT_SENDER:-unknown}"
TEXT="${AGENTCHAT_TEXT:-}"
SHORT="${TEXT:0:150}"

# Portal1's Telegram bot token
BOT_TOKEN="8551152991:AAGmFI86pxlS5dSsPGpzseP3jAzo9r7IKK0"
# Armada group chat ID (supergroup)
CHAT_ID="-1003803096847"

# Send a short ping to the group mentioning Portal2
MSG="@openclaw_portal2_bot 📬 New AgentChat message from ${SENDER}: ${SHORT}

Check AgentChat and reply: curl -s http://192.168.1.64:9090/api/messages?since=0 | python3 -m json.tool"

curl -sf "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  -d text="${MSG}" \
  -d parse_mode="" \
  --max-time 10 > /dev/null 2>&1

echo "Portal2 webhook: Telegram ping sent"
