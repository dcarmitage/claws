# MEMORY.md — Operational State & Long-Term Memory

*Curated knowledge. Keep this current. Remove stale info.*

## System Status (as of 2026-02-03)

### What's Working
- **OpenClaw 2026.2.2-3:** Upgraded from Clawdbot, gateway running as systemd service
- **AgentChat Plugin:** Channel plugin installed, polls every 5s, auto-responds to messages
- **Camera Service:** `camservice.service` on port 5080 — persistent Picamera2, ~60ms snaps
- **Parakeet STT:** systemd service on port 5092, auto-starts, 10-20x realtime
- **Voice transcription:** OpenClaw auto-transcribes all inbound OGG via `tools.media.audio` config
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
- **🚀 Armada Orchestration Stack (CURRENT):** Multi-agent coordination system on Cloudflare Durable Objects. Master doc: Polylogue "Armada Orchestration Stack" (slug: armada-orchestration-stack-4Tzc2z, 26KB, v4). Architecture: 4 layers (L0 ChatRoom DO, L1 TaskBoard DO, L2 Council of Judges, L3 Strategy Library). Wave-based implementation plan. **NEXT: Mudpaw specs Wave 1 (DO TaskBoard MVP), then we build it.** Research phase complete (Swarms, Agent Relay, beads_rust, ARC-AGI).
- **Camera/Streaming Platform:** Full HLS streaming with audio, web viewer with designed control bar. Tagged `v1.1-live-sync`. Watch page: `http://192.168.1.64:5080/stream/watch`. Known issue: live sync still not perfect — needs more testing.
- **Build Orchestrator:** `systems/orchestrator/` — task logging, taskboard parsing, reporting. Tagged `v1.0-orchestrator`. Use `build_log.py` to instrument every future build.
- **Media Catalog:** SQLite + FTS5, multi-device aware, auto-indexes captures. Working.
- **Learning system:** LEARN.md + HEURISTICS.md + CASE_STUDY.md + PROFILE.md — comprehensive knowledge base
- **Intercom mode (BACKLOG):** Goal is Pi as standalone voice portal (mic → STT → LLM → TTS → speaker). Requires speaker bonnet connection.
- **AgentChat:** Working (100 messages). Serves as fallback if Moltslack doesn't work out.

## Build Methodology
**Portal1 Build Method v2** — documented in `systems/orchestrator/HEURISTICS.md`
- DISCUSS → SPEC → TASKBOARD → [SPAWN → VERIFY → JUDGE]×N → QA → TAG
- One sub-agent per task, exact code in briefs, verify between each
- Three outputs: code + docs + learning
- Use `build_log.py` for every build (now with `--spec`/`--taskboard` on task-start)
- 17 heuristics (H1-H17), 6 eval heuristics (E1-E6)
- H14: Strategy Council — spawn diverse subagents for planning, convergence = priority
- H15: Simulation ≠ Production — close the gap immediately, don't accumulate false confidence
- H8: Monitor own context. Alert at 70%. Compact at 80%.

## Dual-Judge Evaluation System (2026-02-05)
**Purpose:** Quality gate — two LLM judges score every task after tests pass. Both must score >= 8.0/10.
**Flow:** `task-done` → PostToolUse hook fires → reads spec/taskboard from build log → runs logic + consistency judges via OpenClaw → gates advancement
**Key files:** `evals/` directory (scripts, prompts, hooks, results), `skills/dual-judge/SKILL.md` (`/judge` command)
**Skills:** `/judge` (manual eval), `/learn` (analyze learnings), `/integrate` (persist to memory), `/save-memory` (end-of-session dump)
**Integrated with:** Ralph loops (PROMPT_build.md step 4, guardrail, loop.sh push gate), build_log.py, build_report.py, HEURISTICS.md (E4-E6), CHECKLISTS.md
**Production-validated (LIVE002):** 9.2 GOLD + 8.15 SILVER on real code. Judges caught a real bug (unused VALIDATOR). H15 gap closed.
**Critical rule:** Squash fix commits before re-evaluating (H16). Incremental diffs → INVALID scores.
**Details:** See `memory/2026-02-05.md`

## Task Dispatch System (2026-02-05)
**Purpose:** Bridge taskboards → AgentChat → build_log so Portal2 can claim tasks.
**Key files:** `tools/agentchat/task_dispatch.py` (CLI: post/poll/claim/complete/sync), `tools/agentchat/dispatch-poller.sh` (Portal2 daemon), `skills/task-dispatch/SKILL.md`
**Status:** Built, logic verified, NOT yet tested end-to-end with Portal2. H15 applies.

## Key Lessons Learned
*Full list: 31 lessons in LEARN.md. Top lessons by category:*

**Hardware:** Hailo-8 = CNN only (no transformers). Parakeet >> Whisper on Pi CPU. No hw H.264 on Pi 5. Keep Picamera2 warm via service (60ms vs 760ms).

**Process (H11):** NEVER claim something works unless tested. Verify first, answer second. (Mudpaw's direct instruction, non-negotiable.)

**Agent Comms:** IPv6 gotcha (`localhost` → `::1`). Seq-based cursors, not timestamps. Dedupe after processing, not before. CLAIM before working. Cooldown window between posts.

**OpenClaw:** Plugin manifests need `"channels"`. SIGUSR1 reloads config only, not code — restart service for code changes. Version skew kills plugins (`openclaw gateway install`).

## TODO

### Priority: Armada Orchestration Stack
- [ ] **Live judge-gated build loop** (Strategy Council unanimous priority)
- [ ] Mudpaw specs Wave 1
- [ ] Build Wave 1: DO TaskBoard MVP
- [ ] Waves 2-5: ChatRoom, Orchestrator loop, Quality+memory, Scale

### Backlog
- [ ] Speaker bonnet + TTS + Intercom loop
- [ ] AI auto-tagging via Hailo-8 YOLO
- [ ] Media catalog web UI

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

*Last updated: 2026-02-05 19:30 EST — LIVE002 production-validated, task dispatch built, /learn+/integrate tested*

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

### 🚀 Armada Orchestration Stack (2026-02-04)
**Goal:** Self-sustaining agent flywheel. 4 layers on Cloudflare DOs (L0 ChatRoom, L1 TaskBoard, L2 Council of Judges, L3 Strategy Library). 5-wave implementation plan.
**Master doc:** Polylogue (armada-orchestration-stack-4Tzc2z, 26KB, v4)
**Details:** `memory/2026-02-04.md`, `systems/ARMADA_SCALING.md`

### Key Files
- `systems/ARMADA_SCALING.md` — Full scaling spec
- `systems/ARMADA.md` — Original vision
- `tools/armada-sync.sh` — Push/pull shared files between agents

## QMD (Knowledge Search)
BM25 working (0.37s). CLI: `tools/qmd-search.sh`. Details: `systems/qmd/UPGRADE_PATH.md`
- **Key finding:** BM25 beats vector search for our well-structured corpus. Vector becomes more valuable as corpus grows.

## AgentChat V2 (2026-02-03)
HTTP :9090, WebSocket :9091, SQLite, dashboard. 47 tests. Details: `memory/2026-02-03.md`
**Mudpaw insight:** "Each agent is its own independent VM. Independent aspects (SOUL, MEMORY) + shared aspects (tasks, specs, chat)."

## Core Rules (Mudpaw's Direct Instructions)
0. **NEVER quit before the job is done.** Work until it works. No "let's wrap up" or "debug tomorrow." HARD rule.
1. **NEVER claim done until tested (H11).** Verify first, answer second. Non-negotiable.
2. **"All we can do is our best, and keep learning every day"** — Mudpaw
