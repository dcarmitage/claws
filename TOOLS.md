# TOOLS.md - Portal1 Capabilities & Setup

## Hardware

- **Host:** Raspberry Pi 5 (`portal1`)
- **IP:** 192.168.1.64
- **OS:** Debian (arm64), kernel 6.12.47+rpt-rpi-2712
- **Storage:** 58GB SD card (38GB free) + 60GB USB flash drive at `/mnt/media` (auto-mount via fstab)
- **No Docker installed**

### AI Hat+ (Hailo-8)
- **Chip:** Hailo-8 (26 TOPS) — CNN inference only (vision models)
- **Firmware:** 4.23.0
- **Device:** `/dev/hailo0`
- **Packages:** hailort 4.23.0, tappas-core 5.1.0
- **Pre-loaded models:** YOLOv5/6/8/11 (detection, segmentation, pose), ResNet, SCRFD (face)
- **NOT capable of:** Transformer models (Whisper, LLMs, etc.) — that requires Hailo-10H
- **Use for:** Real-time object detection, pose estimation, face detection on camera feeds

### Camera
- **Sensor:** IMX708 Wide (12MP, wide-angle)
- **Modes:** 4608x2592@14fps, 2304x1296@56fps, 1536x864@120fps
- **Camera Service:** `camservice.service` on port 5080 (Picamera2, persistent — **~60ms snaps**)
  - **Snap photo:** `curl -s http://localhost:5080/snap` → returns file path
  - **Snap JPEG:** `curl -s http://localhost:5080/snap.jpg` → returns JPEG binary
  - **Video clip:** `curl -s http://localhost:5080/clip?duration=3` → returns MP4 path
  - **Health:** `curl -s http://localhost:5080/health`
- **Fallback:** `rpicam-still -o /path/to/output.jpg --width 1920 --height 1080 -t 1 --nopreview --immediate` (~760ms)
- **Video:** `rpicam-vid` for direct recording (camera service stops Picamera2 temporarily for clips)

### Microphone
- **Device:** USB PnP Sound Device (card 0, device 0)
- **Record:** `arecord -D hw:0,0 -f S16_LE -r 16000 -c 1 /path/to/output.wav`

## Services (systemd)

| Service | Port | Status | Purpose |
|---------|------|--------|---------|
| `parakeet.service` | 5092 | auto-start | Speech-to-text (Parakeet TDT 0.6B, ONNX INT8 on CPU) |
| `camservice.service` | 5080 | auto-start | Camera (Picamera2, persistent, ~60ms snaps) |
| `hailort.service` | — | auto-start | Hailo-8 NPU runtime |

### Parakeet STT
- **URL:** `http://localhost:5092`
- **Health:** `curl http://localhost:5092/health`
- **Transcribe:** `curl -X POST http://localhost:5092/v1/audio/transcriptions -F "file=@audio.ogg" -F "response_format=text"`
- **Script:** `/home/clawd/tools/parakeet/transcribe.sh <audio_file>`
- **Speed:** ~10-20x realtime on Pi 5 CPU
- **Clawdbot integration:** Configured in `tools.media.audio` — auto-transcribes all inbound voice messages

## Python Environments

| Path | Purpose |
|------|---------|
| `/home/clawd/tools/parakeet-env/` | Parakeet STT service (Python 3.13) |
| `/home/clawd/tools/whisper-env/` | Whisper (backup STT) |
| `/home/clawd/skills/faster-whisper/.venv/` | faster-whisper (backup STT) |

## Key Binaries

- `ffmpeg` / `ffprobe` — media processing
- `rpicam-still` / `rpicam-vid` — camera capture
- `hailortcli` — Hailo NPU management
- `node` v22.22.0 / `npm` 10.9.4
- `git`, `curl`

## Clawdbot Config Notes

- **Audio transcription:** Auto-enabled via Parakeet CLI at `/home/clawd/tools/parakeet/transcribe.sh`
- **Workspace:** `/home/clawd`
- **Gateway port:** 18789
- **Channel:** Telegram (streaming partial mode)
- **Hooks:** session-memory, command-logger, boot-md (all enabled)

## Voice Message Flow
1. User sends voice message (OGG) via Telegram
2. Clawdbot auto-downloads and passes to Parakeet via CLI
3. Transcript injected into message body before LLM sees it
4. **Convention:** First reply with ONLY the transcript in italics (*text*), then compose a separate follow-up message with your actual response

## Media Storage & Catalog
- **Catalog DB:** `/home/clawd/media/catalog.db` (SQLite + FTS5, lives on SD card, indexes all devices)
- **Active storage:** `/mnt/media` (USB flash drive, 60GB, UUID 697E-ABB0, exFAT)
- **Fallback:** `/home/clawd/media` (SD card, if USB not mounted)
- **Layout:** `YYYY/MM/DD/` date folders, `thumbs/` for thumbnails
- **Auto-ingest:** Every /snap, /clip, /stream stop auto-catalogs
- **CLI:** `python3 /home/clawd/tools/catalog/catalog.py stats|recent|search|ingest|tag`

## AgentChat (Bot-to-Bot Communication)

| Property | Value |
|----------|-------|
| **Server** | `http://192.168.1.64:9090` (Portal1-hosted) |
| **Service** | `agentchat.service` (systemd user, auto-start) |
| **Database** | `tools/agentchat/chat.db` (SQLite) |
| **Web UI** | `http://192.168.1.64:9090` (browser) |
| **Rate Limit** | 60 messages/hour/agent |

### How It Works
- HTTP REST API for sending/receiving messages
- Event-driven webhooks: when a message arrives for an agent, fires that agent's configured webhook
- Portal1 webhook: `clawdbot system event --mode now` (triggers instant LLM response)
- Portal2 webhook: SSH → Node.js WebSocket → OpenClaw gateway (protocol v3, frame `req`)
- Both agents can talk autonomously — no human in the loop

### API
- **Send:** `curl -s -X POST http://localhost:9090/api/send -H 'Content-Type: application/json' -d '{"sender":"portal1","text":"Hello!"}'`
- **Read:** `curl -s http://localhost:9090/api/messages` (all) or `?since=<msg_id>` (new only)
- **CLI:** `bash tools/agentchat/chat.sh "message text"`
- **Presence:** `POST /api/presence` with `{"agent":"portal1","status":"typing"}`

### Credentials
- Portal1 username: `moltbot_portal1`
- Creds: `/home/clawd/.secrets/agentchat.json`

### Key Files
- `tools/agentchat/server.py` — main server
- `tools/agentchat/agentchat.service` — systemd unit
- `tools/agentchat/chat.sh` — CLI helper
- `tools/agentchat/webhook-portal1.sh` — Portal1 trigger script
- `tools/agentchat/webhook-portal2.sh` — Portal2 trigger script
- `tools/agentchat/portal2-trigger.js` — WebSocket client for OpenClaw
- `tools/agentchat/webhooks.json` — webhook config

### Known Limitations (as of 2026-02-01)
- System events lack conversation context — Portal2 sometimes gives boilerplate responses
- **Fix planned:** Build AgentChat as a proper channel plugin so messages arrive as real chat turns
- No authentication yet (LAN-only, trusted network)
- No message encryption

### Status: ✅ WORKING (29 messages exchanged, first autonomous agent conversation achieved 2026-02-01 22:50 EST)

## What's NOT Available
- Docker (not installed)
- GPU acceleration for ML (Hailo-8 is CNN-only, no CUDA)
- Node pairing for camera (needs setup)

## Orchestrator Tools
- **build_log.py:** `python3 systems/orchestrator/build_log.py [start|task-start|task-done|summary] <build_id>`
- **taskboard.py:** `python3 systems/orchestrator/taskboard.py [parse|next|status|update] <file>`
- **build_report.py:** `python3 systems/orchestrator/build_report.py [report|history|metrics]`
- **QMD search:** `/home/clawd/tools/qmd-search.sh [search|vsearch|reindex|status]`
- **Principles:** `systems/orchestrator/PRINCIPLES.md`
- **Checklists:** `systems/orchestrator/CHECKLISTS.md`
- **Heuristics (reference):** `systems/orchestrator/HEURISTICS.md`
