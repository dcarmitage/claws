# MEMORY.md — Operational State & Long-Term Memory

*Curated knowledge. Keep this current. Remove stale info.*

## System Status (as of 2026-02-03)

### What's Working
- **Camera Service:** `camservice.service` on port 5080 — persistent Picamera2, ~60ms snaps (12x faster than rpicam-still)
- **Parakeet STT:** systemd service on port 5092, auto-starts, 10-20x realtime
- **Voice transcription:** Clawdbot auto-transcribes all inbound OGG via `tools.media.audio` config
- **Camera:** IMX708 Wide, via camera service (preferred) or `rpicam-still` (fallback)
- **Microphone:** USB PnP Sound Device, `arecord` works
- **Hailo-8 NPU:** Active, 585 FPS on YOLOv6n, CNN vision models only
- **Telegram:** Primary channel, streaming partial mode
- **Plugin Commands:** `/snap`, `/clip`, `/stream`, `/listen`, `/catalog` — instant, no LLM
- **Media Catalog:** SQLite + FTS5, auto-indexes all captures, multi-device aware
- **USB Storage:** 60GB flash drive at `/mnt/media` (auto-mounts via fstab, UUID 697E-ABB0)
- **Live Streaming:** HLS via rpicam-vid → tee → ffmpeg pipeline, with recording
- **Web Player:** Viewfinder-style UI at `http://192.168.1.64:5080/stream/watch` (local network only)
- **Drive Handshake:** Catalog recognizes drives by UUID, tracks online/offline, supports transfer between devices

### What's NOT Working
- **Node pairing for camera:** `nodes camera_snap` fails — no paired nodes. Camera works via camera service.
- **Audio output:** Speaker bonnet available but not connected
- **Displays:** All available, none connected
- **Docker:** Not installed

## About Mudpaw (Daniel)
- Telegram: @danielarmitage (id: 473529433)
- Captures and organizes media
- Has duplicate hardware (2x Pi, 2x Hat+, 2x PSU, 2x mic, 2x SD)
- Total investment: ~$734+
- Values: speed, understanding how systems work, clean documentation
- **Gets frustrated by regression** — when progress is lost between sessions. Document everything.
- Building a multi-agent ecosystem with Portal1 as first teammate

## Conventions
- **Voice messages:** Echo transcript in italics (*text*) as first reply, then respond separately
- **Write it down:** Never make "mental notes." If it matters, write to a file.
- **Don't regress:** Check TOOLS.md and LEARN.md before attempting something that may already be set up
- **Camera:** Use `rpicam-still` directly, don't rely on node pairing

## Active Projects
- **🚀 Armada Scaling (CURRENT):** Multi-agent coordination infrastructure. Plan: self-host Moltslack for Discord-like agent community. Spec: `systems/ARMADA_SCALING.md`. Research complete, ready to implement.
- **Camera/Streaming Platform:** Full HLS streaming with audio, web viewer with designed control bar. Tagged `v1.1-live-sync`. Watch page: `http://192.168.1.64:5080/stream/watch`. Known issue: live sync still not perfect — needs more testing.
- **Build Orchestrator:** `systems/orchestrator/` — task logging, taskboard parsing, reporting. Tagged `v1.0-orchestrator`. Use `build_log.py` to instrument every future build.
- **Media Catalog:** SQLite + FTS5, multi-device aware, auto-indexes captures. Working.
- **Learning system:** LEARN.md + HEURISTICS.md + CASE_STUDY.md + PROFILE.md — comprehensive knowledge base
- **Intercom mode (BACKLOG):** Goal is Pi as standalone voice portal (mic → STT → LLM → TTS → speaker). Requires speaker bonnet connection.
- **AgentChat:** Working (100 messages). Serves as fallback if Moltslack doesn't work out.

## Build Methodology
**Portal1 Build Method v2** — documented in `systems/orchestrator/HEURISTICS.md`
- DISCUSS → SPEC → TASKBOARD → [SPAWN → VERIFY]×N → QA → TAG
- One sub-agent per task, exact code in briefs, verify between each
- Three outputs: code + docs + learning
- Use `build_log.py` for every build
- 8 heuristics (H1-H8), 3 eval heuristics (E1-E3)
- H8: Monitor own context. Alert at 70%. Compact at 80%.

## Key Lessons Learned
1. Hailo-8 ≠ Hailo-10H. CNN only. Don't try to run transformers on it.
2. Parakeet >> Whisper on Pi CPU (faster, better punctuation, lighter)
3. Auto-injected files are reliable memory. Everything else must be explicitly read.
4. Systemd services keep models warm — cold start penalty is huge on Pi.
5. `rpicam-still` not `libcamera-hello`
6. Pi 5 has no hardware H.264 encoder
7. Persistent Picamera2 service = 60ms snaps vs 760ms rpicam-still (keep camera warm)
8. rpicam-vid raw h264 has NO timestamps — use `--libav-format mpegts` for piped output
9. Picamera2 must be fully closed + reopened after rpicam-vid (broken pipe otherwise)
10. Plugin `registerCommand` returns `{ text, mediaUrl }` — use `file:///path` for local files
11. Python `global` keyword required to modify module-level vars in functions (easy to miss)
12. Unix `tee` is simpler than ffmpeg tee muxer for saving raw streams
13. exFAT needs `uid=,gid=` mount options for proper permissions
14. Catalog DB should live on SD card (always available), index media across all devices
15. hls.js `liveSyncDuration: 999999` at INIT = broken (can't find sync point). At RUNTIME = works fine for disabling auto-sync.
16. hls.js fatal errors: MUST destroy + null the instance, or poll won't re-init (sees `hls !== null`)
17. 404 responses need CORS headers + plain text body (HTML error pages break hls.js)
18. HUD re-encoding takes ~8-10s for first segment — hls.js needs retry patience
19. Clean up HLS segments on stream stop — stale files cause ghost playback
20. Always test with a minimal page first to isolate issues (e.g. `/stream/test`)
21. **NEVER claim something works unless you've tested and validated it yourself.** Code existing ≠ code working. Never `git add -A` without reviewing. Never present untested code as completed work. If you haven't verified it, say "I wrote it but haven't tested it." Verify first, answer second. (H11 — Mudpaw's direct instruction, 2026-02-01 23:06 EST)

## TODO

### Priority: Armada Scaling
- [ ] **Install Moltslack on Portal1** (NEXT)
- [ ] Register Portal1 + Portal2 as agents
- [ ] Create #armada-general channel
- [ ] Test basic messaging
- [ ] Write Clawdbot skill for Moltslack
- [ ] Implement presence (heartbeat loop)

### Infrastructure (Done)
- [x] Camera service (persistent Picamera2, ~60ms snaps)
- [x] Plugin commands (/snap, /clip, /stream, /listen, /catalog)
- [x] USB media storage + auto-mount
- [x] Media catalog (SQLite + FTS5 + multi-device)
- [x] Second Pi node online (Portal2, Pi 4, 192.168.1.44)
- [x] AgentChat bot-to-bot communication (100 messages)
- [x] Exa Search configured (both machines)
- [x] Web player (viewfinder UI with scrubber, pause, LIVE sync)
- [x] Drive handshake system (UUID-based, online/offline tracking)

### Backlog
- [ ] AI auto-tagging via Hailo-8 YOLO on ingest
- [ ] Speaker bonnet setup + TTS
- [ ] Intercom loop (mic → STT → LLM → TTS → speaker)
- [ ] Scrubber polish (rewind/pause edge cases)
- [ ] Snap-from-stream (capture frame while watching live)
- [ ] Quick-clip extraction (mark IN/OUT, send to Telegram)
- [ ] Media catalog web UI / browsing

## File Map
- `AGENTS.md` — Operating instructions, startup sequence
- `SOUL.md` — Personality
- `USER.md` — About Mudpaw
- `IDENTITY.md` — Who Portal1 is
- `TOOLS.md` — Complete hardware/software reference
- `INVENTORY.md` — Hardware catalog with prices
- `LEARN.md` — Shared learning system for all agents
- `MEMORY.md` — This file. Operational state.
- `memory/YYYY-MM-DD.md` — Daily raw logs
- `HEARTBEAT.md` — Periodic tasks (currently empty)

## Key Files Built Today (2026-01-31)
- `tools/camservice.py` — Camera service (snaps, clips, streaming, web player, storage API)
- `tools/camservice.service` — systemd unit for camera service
- `tools/stream_hud.sh` — Dynamic watermark text generator for ffmpeg drawtext
- `tools/catalog/catalog.py` — Media catalog (SQLite, FTS5, multi-device, handshake, transfer, CLI)
- `.clawdbot/extensions/portal1-commands/` — Plugin for instant /slash commands
  - `index.ts` — /snap, /clip, /stream, /listen, /catalog handlers
  - `clawdbot.plugin.json` — Plugin manifest

## Architecture
```
Telegram → /snap → portal1-commands plugin → camservice:5080/snap → Picamera2 → photo
                                           → catalog.py ingest → SQLite (SD card)
                                           → file stored on USB (/mnt/media/YYYY/MM/DD/)

Telegram → /stream start hud → camservice:5080/stream/start?hud=1
                              → stream_hud.sh writes @dcarmitage watermark to /tmp/stream_hud.txt
                              → rpicam-vid (720p) | tee raw.ts | ffmpeg drawtext+encode → HLS 1s segments
                              → viewable at http://192.168.1.64:5080/stream/watch (web player)
                              → or raw: http://192.168.1.64:5080/stream/live.m3u8
         → /stream stop      → SIGTERM → clean HLS segments → remux .ts→.mp4 → catalog → Telegram

Drive handshake:
  Plug USB → /catalog handshake → check UUID → known="welcome back" / new="registered"
  /catalog transfer → copy+verify+update index between devices
  Unplug → items show offline but still searchable
```

*Last updated: 2026-02-03 14:56 EST by Portal1 🌀*

## The Armada

### Current Agents
| Agent | Host | IP | Role | Status |
|-------|------|-----|------|--------|
| **Portal1** 🌀 | Pi 5 (16GB) | 192.168.1.64 | Media, camera, STT, infrastructure | 🟢 Online |
| **Portal2** 🔍 | Pi 4 (4GB) | 192.168.1.44 | Research, Exa search | 🟢 Online |

### Communication Infrastructure
- **AgentChat** at `http://192.168.1.64:9090` — 100 messages, working, serves as fallback
- **Telegram Armada group** (-5232983156) — both bots, privacy disabled
- **SSH bidirectional** — key auth both directions
- **Exa Search** — API configured on both machines (`~/.secrets/exa.json`)

### 🚀 Scaling Project (2026-02-03)
**Goal:** Discord-like community of AI agents — channels, presence, collaboration.

**Research completed:**
- Moltslack (moltslack.com) — 45 agents online, self-hostable, full feature set
- Mom (badlogic/pi-mono) — per-channel context, events system, skills pattern

**Decision:** Self-host Moltslack on Portal1 as private instance.

**Plan:** `systems/ARMADA_SCALING.md`
1. Install Moltslack + Agent Relay on Portal1
2. Register both agents
3. Create private channels (#armada-general)
4. Test coordination
5. If friction → extend AgentChat instead

**Fallback:** AgentChat remains untouched as backup.

### Key Files
- `systems/ARMADA_SCALING.md` — Full scaling project spec
- `systems/ARMADA.md` — Original armada vision (Researcher → CTO/PM → Trader)
- `memory/2026-02-01-teaching-log.md` — Portal2 onboarding record
- `tools/armada-sync.sh` — Push/pull shared files between agents

## Knowledge Search System (QMD)
- **Status:** BM25 working (0.37s), vector search working but weak (1.5s), installed at /tmp/qmd-install
- **CLI:** `/home/clawd/tools/qmd-search.sh [search|vsearch|reindex|status]`
- **Index:** 16 markdown files, 40 embedded chunks, 3.3MB SQLite DB
- **Models:** embeddinggemma 300M at ~/.cache/qmd/models/ (328MB)
- **Upgrade path:** documented in `systems/qmd/UPGRADE_PATH.md`
- **Next steps:** Better embedding model (nomic-embed), hybrid BM25+vector fusion, API query expansion
- **Key finding:** BM25 beats vector search for our well-structured corpus. Vector becomes more valuable as corpus grows.

## AgentChat V2 (2026-02-03)

**Built:** Complete V2 system on Portal1 infrastructure

**Architecture:**
- HTTP API on :9090, WebSocket on :9091
- SQLite with agents, channels, messages, tasks, notifications
- Dashboard at http://192.168.1.64:9090

**Key insight from Mudpaw:**
> "Each agent is its own independent VM. They have independent aspects (SOUL.md, MEMORY.md) and shared aspects (tasks, specs, chat)."
> "I want every agent to be independently motivated to contribute." (V3: incentives)

**Test suite:** 47 tests in `tools/agentchat/test.sh`

**Philosophy captured:** `systems/PRINCIPLES.md`
- TDD: Write tests alongside code
- Documentation as code: HANDOFF.md required
- Verify before claiming: Run it, don't assume

**Handoff pattern:** When context is high, update HANDOFF.md with:
- What's done, what's not
- Commands to verify/continue
- Context for next builder

## Learnings

1. **Tests compound** — 47 tests now catch regressions later
2. **Handoff docs survive compaction** — Better than relying on memory
3. **Philosophy propagates via AGENTS.md** — Add to reading list, all agents learn it
4. **"All we can do is our best, and keep learning every day"** — Mudpaw
