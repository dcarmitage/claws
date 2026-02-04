# AgentChat V2 — Builder Handoff

> Last updated: 2026-02-03 19:59 EST by Portal1
> Context: 79% when written — SAVE POINT

---

## Quick Status

| Component | Status |
|-----------|--------|
| Server | ✅ Running on :9090/:9091 |
| Tests | ✅ 54 passing |
| Portal1 | ✅ Online, driving |
| Portal2 | ✅ Online, responding |
| Dashboard | ✅ Fixed (sorted, filtered) |

## What We Built Today (2026-02-03)

### Completed ✅
1. **Task claim/release** — `POST /api/v2/tasks/:id/claim` and `/release`
2. **Presence decay** — Marks agents offline after 60s
3. **V1 API fix** — Was returning oldest 100 messages, now returns newest
4. **Deduplication** — 10-second window, prevents spam
5. **Dashboard UX** — Messages sorted newest-at-bottom, noise filtered
6. **Portal2 channel support** — Script updated: `agentchat-send.sh -c builds "msg"`
7. **Auto-heartbeat** — Agents marked online when they post

### V2 Progress: ~55%
- Phase 1-3: ✅ Complete
- Phase 4 Tasks: ✅ Complete (claim/release working)
- Phase 5 Presence: ✅ Complete
- Phase 6 Dashboard: ✅ Usable
- Phase 7 Cloud: ⏳ Not started

## What's NOT Done

### Portal2 Plugin Issue (MAIN BLOCKER)
Portal2's OpenClaw plugin (`~/.openclaw/extensions/agentchat/index.js`):
- ❌ Sends noise ack messages ("Received. id...")
- ❌ Doesn't know which channel to respond to
- ❌ Built for V1, needs V2 update

**Fix needed:** Update plugin to track source channel and respond there.

### Other Remaining
- [ ] Thread subscriptions
- [ ] Documents API
- [ ] Daily standup cron

## Key Files

| File | Purpose |
|------|---------|
| `server.py` | V2 server |
| `dashboard.html` | Web UI (fixed) |
| `tests/test_api.py` | 54 tests |
| `test.sh` | Test runner |

### On Portal2 (192.168.1.44)
| File | Purpose |
|------|---------|
| `~/.openclaw/extensions/agentchat/index.js` | Plugin (needs fix) |
| `/home/dcarmitage/tools/agentchat-send.sh` | Send script (fixed, supports -c channel) |

## Commands

```bash
# Server
curl http://localhost:9090/health
cd /home/clawd/tools/agentchat && ./test.sh

# Portal2 send (now with channel support)
ssh dcarmitage@192.168.1.44 '/home/dcarmitage/tools/agentchat-send.sh -c builds "message"'
```

## Next Steps (Priority Order)

1. **Fix Portal2 plugin** — Make it respond to correct channel, stop noise
2. **Real coordination test** — Task → claim → complete → verify
3. **Thread subscriptions** — Auto-notify on replies

## Commits Today
```
a7846d6 fix: Dashboard UX improvements
03fe391 fix: V1 API returns newest messages + deduplication
0026f95 docs: Update HANDOFF - claim/release done, 54 tests
abcdc88 feat: Add task claim/release endpoints
495834c docs: Add PRINCIPLES.md - TDD and shared team philosophy
b3424e4 test: Add comprehensive test suite (47 tests, all passing)
```

## Lessons Learned

1. V1 API was returning oldest messages — Portal2 never saw new ones
2. Deduplication needed server-side (Portal2 was posting 29x)
3. Dashboard needs noise filtering — agent acks are useless to humans
4. Portal2 script needed V2 API + channel support

---

*"Build it right, not quick." — Mudpaw*
