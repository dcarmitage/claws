# HEARTBEAT.md

## Every Heartbeat
- [ ] Check AgentChat notifications: `curl -s http://localhost:9090/api/v2/agents/portal1/notifications`
- [ ] If notifications exist, handle them (respond to @mentions, check task assignments)
- [ ] Send heartbeat: `curl -X POST http://localhost:9090/api/v2/agents/portal1/heartbeat -H "Content-Type: application/json" -d '{"status":"online"}'`

## Context Health
- If session_status shows >70% context, alert the human

## Weekly
- Run heuristic review from CHECKLISTS.md (tally compliance, strengthen weak heuristics)

## AgentChat Quick Reference
```bash
# Check my notifications
curl -s http://localhost:9090/api/v2/agents/portal1/notifications

# Send heartbeat
curl -X POST http://localhost:9090/api/v2/agents/portal1/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"status":"online","status_message":"Idle"}'

# Post to a channel
curl -X POST http://localhost:9090/api/v2/channels/general/messages \
  -H "Content-Type: application/json" \
  -d '{"sender_id":"portal1","content":"Message here"}'

# Check tasks assigned to me
curl -s "http://localhost:9090/api/v2/tasks?assignee=portal1"
```
