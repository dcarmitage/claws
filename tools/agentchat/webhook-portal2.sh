#!/bin/bash
SENDER="${AGENTCHAT_SENDER:-unknown}"
TEXT="${AGENTCHAT_TEXT:-}"
SHORT="${TEXT:0:200}"

ssh -o ConnectTimeout=5 dcarmitage@192.168.1.44 \
  "node /home/dcarmitage/tools/agentchat/portal2-trigger.js 'AgentChat message from ${SENDER}: ${SHORT}. Read and reply: curl -s -X POST http://192.168.1.64:9090/api/send -H \"Content-Type: application/json\" -d \"{\\\"sender\\\":\\\"portal2\\\",\\\"text\\\":\\\"YOUR_REPLY\\\"}\"'" 2>&1

echo "Portal2 webhook: trigger sent"
