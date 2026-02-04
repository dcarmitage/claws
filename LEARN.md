# LEARN.md — Agent Learning System

*A shared knowledge base for all agents in Mudpaw's ecosystem. Any agent that boots up should be able to read this and get oriented fast.*

---

## 1. Purpose

This document is the **seed of a living learning system** — a compressed, token-efficient knowledge base that any new agent can load to immediately understand:

- **Where they are** (hardware, infrastructure, network)
- **What tools exist** (platforms, APIs, services)
- **Who else is on the team** (agent registry)
- **How to coordinate** (communication protocols)
- **What's been learned** (techniques, patterns, lessons)
- **What we're building** (active projects, vision)

### Design Principles

- **Progressive disclosure** — Don't blast the full context at once. Agents should load the essentials (this file), then discover deeper context as needed by following links to specialized docs.
- **Token efficiency** — Compress knowledge. Dense > verbose. Tables > paragraphs. Links to details > inline details.
- **Curiosity mandate** — Agents should be encouraged to explore, ask, and discover rather than wait for instructions. The guiding principle: *do what feels best, then document what you learned.*
- **Shared learnings** — When any agent learns something useful (a technique, a gotcha, a shortcut), it gets written back here so every future agent benefits.
- **World model** — Each agent boots up with a world model that initially mirrors Mudpaw's. Over time, agents develop specialized perspectives while staying grounded in shared reality.

---

## 2. The World We Live In

### Hardware

| Device | Hostname | Role | Status |
|--------|----------|------|--------|
| Raspberry Pi 5 (16GB) | `portal1` / 192.168.1.64 | Media station, camera, mic, AI inference | 🟢 Active |
| Mac Studio | TBD | Primary dev machine | 🟢 Active |
| MacBook | TBD | Mobile dev | 🟢 Active |
| Raspberry Pi 4 (4GB) | `portal2` / 192.168.1.44 | Research scout, GPT-5.2 | 🟢 Active |

**Portal1 Peripherals:**
- Camera: IMX708 Wide 12MP (`rpicam-still`)
- Microphone: USB PnP Sound Device (`arecord`)
- AI Hat+: Hailo-8 26 TOPS (CNN vision inference only — no transformers)
- Speaker Bonnet + Speakers: Available, not connected yet
- Displays: 2x Mini PiTFT, E-Ink Bonnet, Color TFT + Joystick — all available, none connected

→ Full inventory: `INVENTORY.md`
→ Detailed hardware/software setup: `TOOLS.md`

### Platforms & Services

| Platform | URL | Purpose |
|----------|-----|---------|
| **Clawdbot** | — | Agent runtime, messaging, tools, sessions |
| **Convex** | convex.dev | Real-time backend — multi-agent chat infrastructure |
| **Sprites** | sprites.dev | (TBD — agent tooling?) |
| **Cloudflare** | cloudflare.com | Edge compute, Workers (multi-agent sandbox) |
| **Telegram** | — | Primary human ↔ agent channel |
| **QMD** | github.com/tobi/qmd | Local hybrid search engine (BM25 + vector + LLM rerank), all-local GGUF models, MCP server. For knowledge base search. |
| **jax-js** | github.com/ekzhang/jax-js | JAX-style ML in JavaScript (WebGPU + Wasm). Browser-side inference, no server needed. Future: client-side vision in stream viewer. |

### Services Running on Portal1

| Service | Port | Purpose |
|---------|------|---------|
| Parakeet STT | 5092 | Speech-to-text (ONNX, CPU, auto-start) |
| CamService | 5080 | Camera + streaming (Picamera2, HLS, audio) |
| Clawdbot Gateway | 18789 | Agent runtime |
| HailoRT | — | NPU runtime for vision models |
| AgentChat | 9090 | Bot-to-bot messaging (HTTP, webhooks, web UI) |

---

## 3. Agent Registry

*Who's on the team and what they do.*

| Agent | Host | Role | Status |
|-------|------|------|--------|
| **Portal1** 🌀 | Raspberry Pi 5 (16GB) | Media librarian, infrastructure builder | 🟢 Active |
| **Portal2** 🔍 | Raspberry Pi 4 (4GB) | Research scout, web search/fetch specialist | 🟢 Active |
| *(Future agents)* | Various | CTO/PM, Trader, etc. | 🔴 Planned |

### Mudpaw (Human)
- **Role:** Creator, collaborator, validator
- **Comms:** Telegram (@danielarmitage)
- **Style:** Hands-on, iterative, values speed and understanding
- **World model:** The reference world model all agents initially calibrate against

### Communication Channels
- **Human ↔ Agent:** Telegram (voice + text)
- **Agent ↔ Agent:** AgentChat V2 (local HTTP server on Portal1)
  - Server: `http://192.168.1.64:9090` (systemd, auto-start)
  - Web UI: same URL in browser
  - **V2 API (preferred):**
    - Channels: `GET /api/v2/channels/<id>/messages?since=<cursor>&limit=N`
    - Post: `POST /api/v2/channels/<id>/messages` with `{"sender_id":"<name>","content":"<msg>"}`
    - Notifications: `GET /api/v2/agents/<id>/notifications`
  - **Cursor Contract (V2):**
    - `since=ts:id` — compound cursor (timestamp:message_id), exclusive
    - Response includes `next_since` in same format
    - Clients MUST store `next_since` verbatim (string) and reuse it
    - Numeric-only `since` is **deprecated** (still works, but loses determinism)
  - V1 API (legacy): `POST /api/send`, `GET /api/messages?since=<ts>`
  - CLI: `bash tools/agentchat/chat.sh "message"`
  - Credentials: `/home/clawd/.secrets/agentchat.json`
  - Portal1 username: `moltbot_portal1`
  - Portal2 username: `portal2`
  - Webhooks: event-driven — message arrival fires target agent's webhook automatically
  - Rate limit: 60 msgs/hr/agent
  - **Status:** ✅ Working — 100+ messages, channel plugin operational 2026-02-03
  - **Wake Model (2026-02-04 Portal1↔Portal2 discussion):** "Push for wake, poll for presence, storage+cursor as truth."
    - **Key insight: "Webhook = hint, not transport"** — don't treat it as delivery guarantee
    - Durable log (AgentChat DB) = canonical source of truth
    - Webhook payload: `{channelId, lastSeq}` for bounded pull
    - Agent pulls by cursor/seq after hint, processes idempotently on `(channelId, seq)`
    - At-least-once delivery assumed — retries/duplicates normal
    - **Active burst pattern:** After webhook hint, immediately pull `lastSeenSeq+1…lastSeq`, then poll 250-500ms for 5-15s, then return to baseline interval with exponential backoff on errors
      - *Exit condition:* Don't rely only on time — also exit when `next_seq` stops moving for 3-5 consecutive polls (drops back quickly after last message)
      - *Jitter + cap:* Add jitter to burst polls, cap minimum interval at 200-250ms to avoid thundering-herd on hot channels
      - *Optional:* Extend burst while presence indicates active conversation (but seq-advance heuristic is usually enough)
    - Dedupe on `(channelId, seq)` or message_id — duplicate hints/retries become harmless
    - Polling/backoff = slow-path recovery when webhook fails
    - Presence/typing/heartbeat = ephemeral, polling is fine (no backfill needed)
    - **IPv6 rule:** Never use `localhost` in webhook URLs or loopback-sensitive code
      - For IPv4-only binds: use `127.0.0.1` explicitly
      - For dual-stack: bind deliberately and test both `::1` and `127.0.0.1` in E2E
      - Node.js resolves `localhost` → `::1` (IPv6) which fails against IPv4-only servers
  - **Two-layer dedupe doctrine:**
    - *Hint dedupe* = best-effort (LRU/TTL, lossy OK) — collapse noise, not correctness-critical
    - *Processing dedupe* = correctness-critical (durable `last_processed_seq[channel]`, idempotent on `(channel, seq)`)
  - **Busy/backpressure rule:**
    - Never signal "busy" with non-2xx to hints (causes sender retry storms)
    - Coalesce hints locally; pull when ready
    - Keep heartbeat fresh during LLM calls (`typing` status) so "stale ≠ dead"
  - **Outbound idempotency:** Key format `ac:v2:<channel_id>:<seq>:<action>` (e.g., `:reply`, `:react:👍`). Store `idempo → provider_msg_id` durably with short TTL so retries become no-ops.
  - **Cursor commit rule:** Only advance `last_processed_seq[channel]` AFTER outbound action(s) tied to that message have succeeded (or recorded via idempotency table). Prevents "cursor moved but reply lost" gaps.
  - **Summary:** "Webhooks wake you fast, cursors keep you honest, idempotency keeps you safe."
- **Clawdbot sessions:** Sub-agents can be spawned and communicate via `sessions_send`

---

## 4. Techniques & Patterns

*Things we've learned that work. Updated as we discover more.*

### Development Process: Portal1 Build Method

**Evolved from experience + Ralph Loops methodology (2026-02-01)**

Our approach to building features, refined through the camservice streaming UI project:

#### Core Principles

1. **Spec before code** — Write a clear spec file (`*_SPEC.md`) before building. Include design rationale, element inventory, and behaviors. This becomes the sub-agent's brief.

2. **Git checkpoint before changes** — Always `git commit` working state before starting a new feature. Safe rollback = confidence to experiment.

3. **Sub-agents for fresh context** — When building anything substantial, spawn a sub-agent. It gets a clean context window with zero accumulated cruft. The main session stays responsive for conversation.

4. **One concern per iteration** — Don't bundle audio routing fixes + UI redesign + ALSA control fixes into one pass. Each is a separate iteration with its own validation.

5. **Validate mechanically** — After every change: `python3 -c "ast.parse(...)"` for Python, `sudo systemctl restart` + health check, visual verification via screenshot or user feedback.

6. **Plans are disposable** — If a sub-agent's output isn't right, don't patch it. Regenerate with clearer specs. Regeneration cost < debugging cost.

#### What We Learned From Ralph Loops

| Ralph Principle | How We Apply It |
|----------------|----------------|
| Fresh context per iteration | Sub-agents get clean 200k windows |
| One task per iteration | Spec files scope to one feature |
| Backpressure (validation gates) | ast.parse + service restart + user visual check |
| Specs before code | `*_SPEC.md` files as sub-agent briefs |
| Git commits as checkpoints | Commit before and after each feature |
| Don't assume not implemented | Read existing code before rewriting |

#### What We Do Differently

| Our Addition | Why |
|-------------|-----|
| Design review (invite experts) | Thinking through Steve Jobs/Ive/Ango perspectives catches UX issues before code |
| Main session as orchestrator | Main session writes specs + spawns builders, stays available for human conversation |
| Visual verification loop | Human screenshots the result → we iterate based on what they actually see |
| Context health monitoring | Watch for token corruption (stray `$` signs, garbled output) — compact or spawn fresh when degraded |
| Build instrumentation | `build_log.py` captures timing, pass/fail, commits for every task automatically |
| Three-output rule | Every build produces: code + documentation + learning updates |
| Heuristics as living doc | `systems/orchestrator/HEURISTICS.md` — rules refined by evidence each session |

#### Decision Principles
- **Use maximum intelligence, optimize later.** Opus everywhere. Build right first, swap models later.
- **Capture what, why, and how to improve.** Code alone is incomplete output.
- **Eval the evals.** After each build, ask "what bug did our tests NOT catch?" and add coverage.

#### The Flow (v2 — evaluated 2026-02-01)

```
1. DISCUSS    — Talk through what we're building with Mudpaw
2. SPEC       — Write *_SPEC.md with full design + behaviors  
3. TASKBOARD  — Break spec into tasks with dependency graph
4. COMMIT     — Git checkpoint current working state
5. SPAWN      — One sub-agent per task (exact code in brief)
6. VERIFY     — Orchestrator checks commit, runs validation
7. REPEAT     — Steps 5-6 for each task in dependency order
8. QA         — Final review (automated checks + visual)
9. TAG        — Git tag the working checkpoint
```

**Critical:** Each SPAWN→VERIFY is one iteration. Fresh context. One concern. Verified before next.
**See:** `EVAL_2026-02-01.md` for full metrics and comparison.

#### Anti-Patterns (Things That Failed)

| Anti-Pattern | What Happened | Lesson |
|-------------|---------------|--------|
| All tasks in one sub-agent | Gave 6 tasks to one builder → failed quality inspection | ONE task per sub-agent, always |
| No verification between tasks | Errors compounded across tasks silently | Orchestrator MUST verify each commit before spawning next |
| Vague task briefs | "Fix the time display" → interpretation drift | Include EXACT code to write in the brief |
| Too many fixes in one pass | Audio routing + UI redesign + ALSA fix = nothing worked right | Scope each pass to ONE concern |
| Patching corrupted context | Output had `$` token corruption, kept trying to generate | Compact or spawn fresh immediately |
| Canvas-based VU meter | Browser AudioContext quirks made it unreliable | Simpler elements (divs) > complex elements (canvas) |
| `hw:0,0` for ALSA | Raw device doesn't support format negotiation | Always use `plughw:0,0` for flexibility |
| `v.muted` for volume control | Blocks audio data to Web Audio analyser | Use GainNode for volume, keep video unmuted |
| Manual HLS live-edge seeks | `v.currentTime = buffered.end - 0.5` causes stalls | Let hls.js manage live edge via liveSyncDurationCount |

### Speech-to-Text Pipeline
- **Engine:** Parakeet TDT 0.6B v3 (ONNX INT8 on CPU)
- **Speed:** 10-20x realtime on Pi 5
- **Integration:** Clawdbot `tools.media.audio` auto-transcribes inbound voice messages before they reach the LLM
- **Convention:** Echo transcript back in italics first, then respond separately
- **Lesson:** Keep the model warm as a systemd service — cold start adds 45s of model loading

### Camera & Streaming
- **Snap:** `curl http://localhost:5080/snap.jpg` (~60ms via camservice)
- **Stream:** HLS via camservice — 720p, 2s segments, video + audio
- **Audio capture:** ALSA via `plughw:0,0` (not `hw:0,0` — raw device can't negotiate formats)
- **Mic control:** `amixer -c 0 sset Mic cap/nocap` (not `Mic Capture Switch`)
- **Mic volume:** Must be set explicitly: `amixer -c 0 sset Mic 100%` (defaults to 0%)
- **Web viewer:** `http://portal1.local:5080/stream/watch`
- **Lesson:** Pi 5 at 1080p30 only achieves ~13fps through the ffmpeg pipeline. Use 720p for reliable streaming.

### Hailo-8 NPU
- **Good for:** YOLO, ResNet, SCRFD, pose estimation — any CNN vision model
- **NOT for:** Transformers (Whisper, LLMs, VLMs) — requires Hailo-10H GenAI Core
- **Benchmark:** YOLOv6n @ 585 FPS, 3.19ms latency
- **Lesson learned:** Don't waste time trying to run Whisper on Hailo-8. The silicon physically can't do attention layers.

### Memory System
- **Auto-injected files** (always available): AGENTS.md, SOUL.md, USER.md, TOOLS.md, IDENTITY.md, HEARTBEAT.md
- **Must be read manually**: MEMORY.md, daily logs, LEARN.md
- **Key lesson:** If it's not in an auto-injected file, you'll probably forget it. Put critical operational info in TOOLS.md.

### Pi 5 Gotchas
- No hardware H.264 encoder — software libx264 only
- No Docker installed
- SD card + USB flash drive (60GB at /mnt/media)
- Use `rpicam-*` commands, not `libcamera-*`

---

## 5. Skills Library

*What agents know how to do. Each skill has a SKILL.md with detailed instructions.*

| Skill | Location | Purpose |
|-------|----------|---------|
| Ralph Loops | `skills/ralph-loops/` | Iterative autonomous development methodology |
| Parakeet STT | `skills/parakeet-stt/` | Local speech-to-text |
| Faster Whisper | `skills/faster-whisper/` | Backup STT (slow on Pi) |
| Video Subtitles | `skills/video-subtitles/` | SRT generation + burn-in |
| CamSnap | `skills/camsnap/` | RTSP/ONVIF camera tool (needs binary) |
| Weather | (clawdbot built-in) | Forecasts |
| GitHub | (clawdbot built-in) | `gh` CLI integration |
| Video Frames | (clawdbot built-in) | Extract frames from video |

→ More skills available at [ClawdHub](https://clawdhub.com)

---

## 6. Vision

### Where We're Going

**Phase 1: Solid Foundation** ← *We are here*
- Reliable memory system (LEARN.md, MEMORY.md, TOOLS.md)
- All hardware working and documented
- Voice ↔ text pipeline operational
- Camera + streaming operational

**Phase 2: Intercom Mode**
- Speaker bonnet connected → TTS output
- Mic always-on or push-to-talk
- Full loop: mic → STT → LLM → TTS → speaker
- Physical controls via TFT + joystick
- Pi acts as standalone communication portal

**Phase 3: Agent Mitosis**
- Specialize agents for specific domains
- Second Pi node comes online
- Agents coordinate via Convex
- Shared learning system (this document) keeps everyone aligned

**Phase 4: Learning Academy**
- LEARN.md evolves into an API/service
- New agents boot → hit learning endpoint → load up → ready
- Community agents can model different world models
- Darwinian selection: effective agents persist, ineffective patterns get pruned

### The Evolution Model
```
Single agent (Portal1)
  → Mitosis (spawn specialized agents)
    → Specialization (each develops domain expertise)
      → Coordination (Convex chat, shared LEARN.md)
        → Selection (what works persists, what doesn't gets pruned)
          → Community (multiple world models, diverse perspectives)
```

---

## 7. Task List

### Immediate (Foundation)
- [x] Parakeet STT running as persistent service
- [x] Voice auto-transcription wired into Clawdbot
- [x] TOOLS.md comprehensive and current
- [x] LEARN.md created (this document)
- [x] Camera streaming with audio (camservice)
- [x] Stream viewer with control bar UI
- [ ] Rewrite MEMORY.md — clean, current operational briefing
- [ ] Camera accessible without node pairing workaround
- [ ] Update AGENTS.md startup sequence to reference LEARN.md

### Near-term (Intercom)
- [ ] Connect I2S speaker bonnet + speakers
- [ ] Install TTS engine (ElevenLabs API or local sherpa-onnx)
- [ ] Push-to-talk or wake-word trigger
- [ ] Display setup (status on TFT or E-Ink)
- [ ] Full voice loop: mic → STT → LLM → TTS → speaker

### Medium-term (Multi-Agent)
- [ ] Second Pi node online
- [ ] Convex agent chat integration
- [ ] Agent spawning with auto-LEARN.md loading
- [ ] Cloudflare Workers for edge agent tasks
- [ ] Agent registry as live service (not just a markdown table)

### Long-term (Academy)
- [ ] LEARN.md → API endpoint
- [ ] Progressive disclosure system (agents request knowledge on-demand)
- [ ] World model diversification
- [ ] Community agent onboarding
- [ ] Evolutionary selection mechanisms

---

## 8. Links & Resources

| Resource | URL |
|----------|-----|
| Clawdbot docs | https://docs.clawd.bot |
| ClawdHub (skills) | https://clawdhub.com |
| Clawdbot Discord | https://discord.com/invite/clawd |
| Ralph Loops | https://clawhub.ai/skills/ralph-loops |
| Geoffrey Huntley (Ralph origin) | https://ghuntley.com/ralph/ |
| Clayton Farr's Playbook | https://github.com/ClaytonFarr/ralph-playbook |
| Convex | https://convex.dev |
| Sprites | https://sprites.dev |
| Hailo Community | https://community.hailo.ai |

---

*This document is alive. Every agent that learns something useful writes it back here. Every session that discovers a gotcha adds it to Techniques. The goal: no agent ever has to relearn what another agent already figured out.*

*Last updated: 2026-02-04 by Portal1 🌀 (webhook/polling patterns from Portal1↔Portal2 discussion)*

## The Armada

### Launch Process (Proven 2026-02-01)
1. Flash SD card (Pi Imager, OS Lite 64-bit, SSH + WiFi enabled)
2. Boot, find on network (`ping sweep 192.168.1.0/24`)
3. SSH key access from Portal1
4. Install Node 22 (`nodesource setup_22.x`)
5. Install OpenClaw (`npm install -g openclaw --ignore-scripts` on Pi 4 to avoid OOM)
6. `openclaw onboard` (needs `NODE_OPTIONS="--max-old-space-size=1024"` on Pi 4)
7. First gateway start takes 3-5 min (native compilation, one-time)
8. Telegram pairing: message bot → `openclaw pairing approve telegram <CODE>`

### Critical Lessons
- Pi 4 (4GB) is tight for OpenClaw — node-llama-cpp compilation uses >4GB. Use `--ignore-scripts` during install.
- Don't hand-edit JSON configs with `sed`. Use Python `json.load/dump` or the CLI.
- `openclaw onboard` may not set `hooks.token` — check and add manually if missing.
- Four config files can exist across `.clawdbot/` and `.openclaw/` (legacy migration). Service reads `~/.openclaw/openclaw.json`.
- First gateway start compiles native code at 140% CPU for 3-5 min. Don't kill it.
- Estimated time for subsequent launches: ~25 min (vs 90 min first time).

### Bot-to-Bot Communication in Telegram Groups
- Bots can post to groups via `message` tool
- Bots CANNOT trigger other bots via @mention (mention-gating drops bot sender messages)
- Working pattern: Bot1 SSHes + narrates, Human relays via @mentions to Bot2
- Future: try `requireMention: false` per-group, or `mentionPatterns` regex

### Armada Architecture
- **Portal1** (Pi 5, 8GB): Media librarian, Opus 4.5
- **Portal2** (Pi 4, 4GB): Researcher (planned), GPT-5.2
- **Future:** CTO/PM on Mac Studio, Trader on Pi/cloud
- Sequence: Researcher → CTO/PM → Trader (each launch teaches the next)
- Hardware-first (avoids cloud/networking complexity), cloud at inflection point

---

## Test-Driven Development (TDD)

**Added:** 2026-02-03 by Portal1

### The Pattern

```
Understand → Write Test → Build → Verify → Commit → Repeat
```

### Key Files

Every project should have:
- `test.sh` — Runner script
- `tests/` — Test directory
- Test coverage for all critical paths

### Example: AgentChat V2

```bash
cd /home/clawd/tools/agentchat
./test.sh  # 47 tests covering all APIs
```

### Philosophy

See `systems/PRINCIPLES.md` for full philosophy on:
- TDD workflow
- Documentation as code
- Incremental building
- Shared knowledge
- Verify before claiming

**Core insight:** Tests are executable specifications. If you can't test it, you don't understand it well enough to build it.
