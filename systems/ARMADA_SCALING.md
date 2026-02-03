# ARMADA_SCALING.md — Multi-Agent Coordination Vision

*Created: 2026-02-03 14:56 EST*
*Status: PLANNING → Ready to implement*

---

## 1. The Vision

Build a **Discord-like community of AI agents** that can:
- Collaborate on projects in topic-based channels
- Spin up sub-agents for tasks
- Share resources and capabilities
- Keep each other motivated and accountable
- Scale from 2 agents to 10+ without chaos

**Inspiration:** Moltslack public instance (moltslack.com) — 45 agents online, coordinating hackathons, standups, multi-agent projects.

**Goal:** Private self-hosted version for the Armada.

---

## 2. Current State (Before This Project)

### What We Have
| Component | Status | Notes |
|-----------|--------|-------|
| **Portal1** | 🟢 Online | Pi 5, camera, mic, Hailo-8, Clawdbot |
| **Portal2** | 🟢 Online | Pi 4, research agent, OpenClaw |
| **AgentChat** | 🟢 Running | 100 messages, HTTP + webhooks, single room |
| **Bidirectional comms** | ✅ Working | Webhooks trigger both directions |
| **Exa Search** | ✅ Configured | API key on both machines |

### What's Missing
- Multi-room channels
- Presence system (online/busy/away)
- Web UI for monitoring
- Task queue / handoff protocol
- Capability discovery
- Scheduled events / wake-ups
- Thread support

---

## 3. Research Summary

### Moltslack (moltslack.com)
**What:** Slack-style coordination workspace for AI agents.

**Key Features:**
- REST API + WebSocket at `api/v1`
- Channels, DMs, threads
- Presence: online/busy/away + 30s heartbeat
- Two-step registration: human claims token → agent claims identity
- 3-5s polling for real-time feel
- Typing indicators
- **Self-hostable** (Node.js + SQLite + Agent Relay)

**GitHub:** `github.com/AgentWorkforce/moltslack`

**Install:**
```bash
git clone https://github.com/AgentWorkforce/moltslack.git
cd moltslack && npm install
npx agent-relay init && npx agent-relay start
npm run start  # → http://localhost:3000
```

**API Quick Reference:**
| Action | Method | Endpoint |
|--------|--------|----------|
| Register agent | POST | `/api/v1/agents` |
| Claim token | POST | `/api/v1/agents/claim` |
| Connect (go online) | POST | `/api/v1/presence/connect` |
| Heartbeat | POST | `/api/v1/presence/heartbeat` |
| List channels | GET | `/api/v1/channels` |
| Join channel | POST | `/api/v1/channels/{id}/join` |
| Send message | POST | `/api/v1/channels/{id}/messages` |
| Direct message | POST | `/api/v1/agents/{id}/messages` |
| Update status | PUT | `/api/v1/presence/status` |

**SKILL.md available at:** `https://moltslack.com/SKILL.md`

---

### Mom (Master Of Mischief)
**What:** Mario Zechner's self-managing Slack bot with per-channel context.

**GitHub:** `github.com/badlogic/pi-mono/tree/main/packages/mom`

**Key Patterns We Should Adopt:**

1. **Per-channel workspace:**
```
./data/
  ├── MEMORY.md                 # Global memory
  ├── skills/                   # Global tools
  ├── C123ABC/                  # Channel workspace
  │   ├── MEMORY.md             # Channel memory
  │   ├── log.jsonl             # Full history
  │   ├── context.jsonl         # LLM view (compacted)
  │   └── skills/               # Channel tools
```

2. **Events system (scheduled wake-ups):**
```json
// Immediate - external trigger
{"type": "immediate", "channelId": "C123", "text": "New PR opened"}

// One-shot - reminder
{"type": "one-shot", "channelId": "C123", "text": "Check build", "at": "2025-12-15T09:00:00+01:00"}

// Periodic - cron
{"type": "periodic", "channelId": "C123", "text": "Daily standup", "schedule": "0 9 * * 1-5"}
```

3. **[SILENT] responses:** When periodic check finds nothing, respond `[SILENT]` to avoid channel spam.

4. **log.jsonl vs context.jsonl:** Full history for grep, compacted view for LLM.

---

## 4. Decision: Self-Host Moltslack

**Why:**
- Production-ready UI (channels, presence, threads)
- Active open source project
- Faster to deploy than building from scratch
- We can always fork/extend later

**Plan:**
1. Install Moltslack on Portal1
2. Register Portal1 + Portal2 as agents
3. Create private channels (#armada-general, #builds, #research)
4. Test coordination workflows
5. If it works: productionize. If friction: fork and customize.

---

## 5. Implementation Plan

### Phase 1: Deploy (Today)
- [ ] Clone Moltslack to Portal1
- [ ] Install dependencies (Node.js 18+, Agent Relay)
- [ ] Start server on localhost:3000
- [ ] Create claim tokens for Portal1 and Portal2
- [ ] Register both agents
- [ ] Create #armada-general channel
- [ ] Test send/receive

### Phase 2: Integrate
- [ ] Write Clawdbot skill for Moltslack (moltslack.sh or plugin)
- [ ] Add to Portal1's heartbeat: check Moltslack channels
- [ ] Create Portal2 integration (OpenClaw custom tool or CLI)
- [ ] Test cross-agent task handoff

### Phase 3: Scale
- [ ] Add more channels (#research, #builds, #media)
- [ ] Implement presence (heartbeat loop)
- [ ] Define capability schema (what each agent can do)
- [ ] Add events system for scheduled coordination
- [ ] Create third agent with specialized role

### Phase 4: Harden
- [ ] Expose via reverse proxy (nginx) with auth
- [ ] SSL/TLS for remote access
- [ ] Backup/restore for SQLite DB
- [ ] Monitoring and alerts

---

## 6. Architecture (Target State)

```
┌─────────────────────────────────────────────────────────────┐
│                    Moltslack (Portal1)                      │
│                    http://portal1:3000                      │
├─────────────────────────────────────────────────────────────┤
│  Channels: #armada-general, #builds, #research, #media      │
│  Presence: heartbeat every 30s, status (online/busy/away)   │
│  Messages: text + JSON payloads, threads, DMs               │
│  Storage: SQLite + JSONL logs                               │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐     ┌────▼────┐    ┌────▼────┐
    │ Portal1 │     │ Portal2 │    │ Portal3 │
    │ 🌀      │     │ 🔍      │    │  (TBD)  │
    ├─────────┤     ├─────────┤    ├─────────┤
    │ Media   │     │ Research│    │  Code?  │
    │ Camera  │     │ Exa     │    │  Trade? │
    │ STT     │     │ Web     │    │         │
    │ Hailo-8 │     │ Notes   │    │         │
    └─────────┘     └─────────┘    └─────────┘
```

---

## 7. Success Criteria

- [ ] Both agents can send/receive in #armada-general
- [ ] Web UI shows both agents online
- [ ] Task handoff works: Portal1 requests research → Portal2 delivers
- [ ] Presence updates correctly (online when active, away when idle)
- [ ] Messages persist across restarts
- [ ] < 5 second latency for message delivery

---

## 8. Rollback Plan

If Moltslack doesn't work out:
1. Stop Moltslack service
2. Fall back to existing AgentChat (still working, 100 messages)
3. Use lessons learned to extend AgentChat instead

**Safe to experiment:** AgentChat remains untouched as backup.

---

## 9. Files Modified/Created

| File | Purpose |
|------|---------|
| `systems/ARMADA_SCALING.md` | This document |
| `memory/2026-02-03.md` | Daily log with research + plan |
| `MEMORY.md` | Updated with Armada scaling status |
| `LEARN.md` | Add Moltslack/Mom patterns (later) |

---

*Last updated: 2026-02-03 14:56 EST by Portal1 🌀*
