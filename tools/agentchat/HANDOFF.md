# AgentChat V2 — Builder Handoff

> Last updated: 2026-02-03 17:28 EST by Portal1
> Context: ~55% when last updated

---

## Quick Status

**Server:** Running on Portal1 at `http://192.168.1.64:9090`
**WebSocket:** `ws://192.168.1.64:9091`
**Database:** `/home/clawd/tools/agentchat/chat.db` (SQLite)
**Code:** `/home/clawd/tools/agentchat/server.py` (V2)

## What's Done ✅

### Phase 1: Schema
- [x] V2 schema created (agents, channels, messages_v2, tasks, notifications, documents)
- [x] 109 messages migrated from v1
- [x] Portal1 + Portal2 registered as agents
- [x] #general, #builds, #demo channels created

### Phase 2: Messaging
- [x] `GET /api/v2/channels/:id/messages` — works
- [x] `POST /api/v2/channels/:id/messages` — works
- [x] Thread support (thread_id field) — schema ready, untested
- [x] V1 API still works for backward compatibility

### Phase 3: Notifications  
- [x] @mention parsing creates notifications
- [x] `GET /api/v2/agents/:id/notifications` — works
- [x] Webhooks fire on message (but Portal2's reads old API)

### Phase 6: Dashboard
- [x] Basic dashboard at root URL
- [x] Shows agents, channels, messages
- [x] Auto-refreshes every 30s
- [x] WebSocket connection indicator

## What's In Progress 🔧

### Phase 4: Tasks
- [x] Schema exists
- [x] `GET /api/v2/tasks` — works
- [x] `POST /api/v2/tasks` — works ✅ TESTED
- [ ] `POST /api/v2/tasks/:id/claim` — needs testing
- [x] `POST /api/v2/tasks/:id/status` — works ✅ TESTED
- [x] Task assignment notifications — works ✅ TESTED

### Phase 5: Presence
- [x] `POST /api/v2/agents/:id/heartbeat` — works ✅ TESTED
- [ ] Presence decay (mark offline after 60s)
- [ ] Integration with agent heartbeats (add to HEARTBEAT.md)

## What's Not Done ⏳

- [x] `POST /api/v2/channels` — create channel endpoint ✅ ADDED
- [x] Portal2 webhook update for V2 API ✅ UPDATED
- [ ] Documents API (low priority)
- [ ] Thread subscriptions (auto-notify on reply)
- [ ] Daily standup cron
- [ ] Phase 7: Cloud mode (Cloudflare)

---

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | V2 server (HTTP + WebSocket) |
| `server_v1_backup.py` | Original v1 server (backup) |
| `chat.db` | SQLite database |
| `chat.db.v1.backup` | Pre-migration backup |
| `dashboard.html` | Web dashboard |
| `schema_v2.sql` | V2 schema definition |
| `migrate_v2.py` | Migration script |
| `webhooks.json` | Webhook config for agents |

## API Reference

### Agents
```
GET  /api/v2/agents                    # List all
GET  /api/v2/agents/:id                # Get one
POST /api/v2/agents/:id/heartbeat      # Update presence
     Body: {"status": "online|busy|away", "status_message": "...", "current_task_id": "..."}
GET  /api/v2/agents/:id/notifications  # Get unread notifications
```

### Channels
```
GET  /api/v2/channels                  # List all
GET  /api/v2/channels/:id/messages     # Get messages
     Query: ?since=<timestamp>&limit=<n>
POST /api/v2/channels/:id/messages     # Send message
     Body: {"sender_id": "portal1", "content": "...", "thread_id": "..."}
```

### Tasks
```
GET  /api/v2/tasks                     # List all
     Query: ?status=<status>&assignee=<agent_id>
POST /api/v2/tasks                     # Create task
     Body: {"title": "...", "description": "...", "priority": 2, "assignees": ["portal1"]}
POST /api/v2/tasks/:id/status          # Update status
     Body: {"status": "inbox|assigned|in_progress|review|done|blocked"}
```

### V1 Compatibility
```
GET  /api/messages                     # Old format (maps to #general)
POST /api/send                         # Old format (maps to #general)
```

---

## How to Restart Server

```bash
pkill -f "server.py"
cd /home/clawd/tools/agentchat
python3 server.py > /tmp/agentchat.log 2>&1 &
```

## How to Check Status

```bash
curl http://localhost:9090/health
curl http://localhost:9090/api/v2/agents
curl http://localhost:9090/api/v2/channels
```

## How to Run Tests

```bash
cd /home/clawd/tools/agentchat
./test.sh              # Full suite (starts server if needed)
python3 tests/test_api.py  # Direct (requires server running)
```

**Test coverage (47 tests):**
- Health endpoint
- Agents API (list, get, heartbeat)
- Channels API (list, messages)
- Messages (post, get, threads)
- @mentions → notifications
- Tasks (create, status, assignment)
- V1 API compatibility
- Dashboard HTML

## Known Issues

1. **Portal2 webhook** reads v1 API, won't see V2 channels
2. **Create channel endpoint** missing — use SQL directly for now
3. **Presence decay** not implemented — agents stay "online" forever
4. **Dashboard** doesn't show #demo unless you click a channel link

---

## Next Builder Tasks (Priority Order)

1. **Update Portal2 webhook** (`webhook-portal2.sh`) to use V2 API
2. **Add presence decay** — background thread to mark agents offline
3. **Test task flow** — create, assign, claim, complete
4. **Add `POST /api/v2/channels`** endpoint
5. **Update HEARTBEAT.md** to check AgentChat notifications

---

## Context for Next Session

The vision: Each agent is an independent VM. AgentChat is shared infrastructure for coordination. This runs on Portal1 (Pi 5) as the hub.

Key insight from Mudpaw: "I want every agent to be independently motivated to contribute." Incentive layer is V3.

Spec: `/home/clawd/projects/agentchat/docs/V2_UNIFIED_SPEC.md`
Taskboard: `/home/clawd/projects/agentchat/TASKBOARD.md`

---

*Built by Portal1 🌀 on 2026-02-03*
