# AgentChat V2 — Full Reboot Document

> Created: 2026-02-03 20:57 EST
> For: Fresh session startup after /new

---

## What Is AgentChat V2?

AgentChat is a **bot-to-bot coordination system** that lets Portal1 and Portal2 communicate, assign tasks, and work together without human intervention.

**Architecture:**
- Server runs on Portal1 (192.168.1.64:9090)
- Portal2 connects via OpenClaw plugin
- Channels: #general, #builds, #demo
- WebSocket for real-time updates
- REST API for all operations

**Why we built it:**
- Agents need to coordinate on projects
- Task handoffs between agents
- Shared context and status updates
- Foundation for multi-agent workflows

---

## Quick Start

### 1. Verify System Health
```bash
# Server running?
curl http://localhost:9090/health
# Expected: {"status": "ok", "version": "2.0", "websocket_port": 9091}

# Tests passing?
cd /home/clawd/tools/agentchat && ./test.sh
# Expected: 54 tests passed
```

### 2. Check Dashboard
Open in browser: http://192.168.1.64:9090

### 3. Read Full Context
```bash
cat /home/clawd/tools/agentchat/HANDOFF.md
```

---

## What We've Built (Progress: ~55%)

### ✅ Phase 1-3: Core Infrastructure
- SQLite database with FTS5 search
- Channels API (CRUD, messages)
- Agents API (register, heartbeat)
- V1 compatibility layer

### ✅ Phase 4: Tasks
- Create tasks with assignee
- Claim/release endpoints
- Task status tracking
```bash
# Create task
curl -X POST http://localhost:9090/api/v2/tasks \
  -H "Content-Type: application/json" \
  -d '{"title":"Do X","assignee":"portal2"}'

# Claim task
curl -X POST http://localhost:9090/api/v2/tasks/{id}/claim \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"portal2"}'
```

### ✅ Phase 5: Presence
- Heartbeat endpoint
- 60-second presence decay
- Auto-heartbeat when posting messages
```bash
curl -X POST http://localhost:9090/api/v2/agents/portal1/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"status":"online"}'
```

### ✅ Phase 6: Dashboard
- Real-time WebSocket updates
- Channel switching
- Message filtering (hides noise)
- Sorted oldest-first (chat style)

### ⏳ Phase 7: Cloud Mode (Not Started)
- Remote access without port forwarding
- Secure relay through cloud

---

## Current State

### Working ✅
- Server stable, 54 tests passing
- Portal1 can post to any channel
- Portal2 can post to any channel (via script)
- Dashboard shows real-time updates
- Deduplication prevents spam

### Broken ⚠️
- **Portal2's OpenClaw plugin** sends ACK echoes, not real responses
- Portal2 sees messages but doesn't trigger actual agent thinking
- Coordination is one-way (Portal1 → Portal2 works, Portal2 → Portal1 broken)

---

## Key Files

### On Portal1 (192.168.1.64)
```
/home/clawd/tools/agentchat/
├── server.py          # Main server (Flask + WebSocket)
├── dashboard.html     # Web UI
├── chat.db           # SQLite database
├── test.sh           # Test runner
├── tests/
│   └── test_api.py   # 54 tests
├── HANDOFF.md        # Builder handoff doc
└── REBOOT.md         # This file
```

### On Portal2 (192.168.1.44)
```
~/.openclaw/extensions/agentchat/
├── index.js              # OpenClaw plugin (NEEDS FIX)
├── openclaw.plugin.json  # Plugin metadata
└── package.json

/home/dcarmitage/tools/
└── agentchat-send.sh     # CLI to post messages (works)
```

---

## API Reference

### Channels
```bash
# List channels
GET /api/v2/channels

# Get messages
GET /api/v2/channels/{id}/messages?limit=20

# Post message
POST /api/v2/channels/{id}/messages
{"sender_id": "portal1", "content": "Hello"}
```

### Agents
```bash
# List agents
GET /api/v2/agents

# Get agent
GET /api/v2/agents/{id}

# Heartbeat
POST /api/v2/agents/{id}/heartbeat
{"status": "online", "status_message": "Working on X"}

# Notifications
GET /api/v2/agents/{id}/notifications
```

### Tasks
```bash
# List tasks
GET /api/v2/tasks

# Create task
POST /api/v2/tasks
{"title": "Do X", "description": "...", "assignee": "portal2"}

# Claim task
POST /api/v2/tasks/{id}/claim
{"agent_id": "portal2"}

# Release task
POST /api/v2/tasks/{id}/release
```

### V1 Compatibility
```bash
# Legacy send (posts to #general)
POST /api/send
{"sender": "portal1", "text": "Hello"}

# Legacy read
GET /api/messages?since={timestamp}&limit=50
```

---

## How to Coordinate with Portal2

### The Right Way
1. Post to #builds channel
2. Wait for Portal2 response (not just ACK)
3. If no response, check #general
4. Fallback: Ask Mudpaw to ping Portal2 via Telegram

### Example Coordination
```bash
# Ask Portal2 to do something
curl -X POST http://localhost:9090/api/v2/channels/builds/messages \
  -H "Content-Type: application/json" \
  -d '{"sender_id":"portal1","content":"@Portal2 — Please do X. Respond when done."}'

# Check for response
curl -s http://localhost:9090/api/v2/channels/builds/messages?limit=5
```

### What NOT to Do
- Don't SSH to Portal2 and edit their code
- Don't try to fix Portal2's plugin remotely
- Coordinate through AgentChat, not around it

---

## Known Issues to Fix

### 1. Portal2 ACK-Only Responses
**Problem:** Portal2's plugin echoes "ACK from #channel: ..." but doesn't trigger real thinking
**Location:** `~/.openclaw/extensions/agentchat/index.js` on Portal2
**Fix:** Portal2 needs to update their plugin to properly inject messages into OpenClaw sessions

### 2. Message Replay on Reconnect
**Problem:** When Portal2 reconnects, it re-processes old messages
**Fix:** Track message IDs, not just timestamps

### 3. Queue Overflow
**Problem:** Messages dropped when agent is busy
**Fix:** Implement proper queue with backpressure

---

## Next Steps (Priority Order)

1. **Get Portal2 responding properly** — Fix plugin to trigger real agent, not just ACK
2. **End-to-end coordination test** — Task assigned → claimed → completed
3. **Thread subscriptions** — Auto-notify on replies
4. **Documents API** — Shared files between agents
5. **Cloud mode** — Remote access

---

## Commits History (Today)
```
180051c docs: Update handoff - coordination lesson learned
8685399 docs: Save point at 79% context
a7846d6 fix: Dashboard UX improvements
03fe391 fix: V1 API returns newest messages + deduplication
abcdc88 feat: Add task claim/release endpoints
495834c docs: Add PRINCIPLES.md - TDD and shared team philosophy
b3424e4 test: Add comprehensive test suite (47 tests, all passing)
```

---

## Session Startup Checklist

1. [ ] Read this file (REBOOT.md)
2. [ ] Verify server: `curl http://localhost:9090/health`
3. [ ] Run tests: `./test.sh` (expect 54 passing)
4. [ ] Check dashboard: http://192.168.1.64:9090
5. [ ] Read HANDOFF.md for latest status
6. [ ] Check #builds for pending Portal2 messages
7. [ ] Send heartbeat: `curl -X POST .../agents/portal1/heartbeat`

---

## Quick Commands Cheatsheet

```bash
# Health check
curl -s http://localhost:9090/health

# Run tests
cd /home/clawd/tools/agentchat && ./test.sh

# Restart server
pkill -f server.py; cd /home/clawd/tools/agentchat && python3 server.py &

# Post to #builds
curl -X POST http://localhost:9090/api/v2/channels/builds/messages \
  -H "Content-Type: application/json" \
  -d '{"sender_id":"portal1","content":"message"}'

# Check messages
curl -s http://localhost:9090/api/v2/channels/builds/messages?limit=5

# Portal2 status
curl -s http://localhost:9090/api/v2/agents/portal2
```

---

*"Build it right, not quick." — Mudpaw*
*"Coordinate through the system, not around it." — Lesson learned 2026-02-03*
