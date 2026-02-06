# Tools — Standalone Services and Utilities

Services and scripts that run independently of the agent session.

## Services

### AgentChat (`tools/agentchat/`)
Multi-agent messaging server with HTTP and WebSocket support. Agents post messages to channels, dispatch tasks, track presence, and receive webhook notifications.

```bash
# Start the server
python3 tools/agentchat/server_v2.py

# Server runs on:
#   HTTP:      port 9090
#   WebSocket: port 9091
#   Dashboard: http://localhost:9090/
```

### Camera Service (`tools/camservice.py`)
HTTP API for Picamera2. Captures snapshots, streams MJPEG, and serves a web preview.

```bash
# Start as a service
sudo systemctl start camservice

# Or run directly
python3 tools/camservice.py
# Endpoints: GET /snap, GET /stream, GET /health
```

### Media Catalog (`tools/catalog/`)
SQLite + FTS5 full-text search catalog for media files. Indexes metadata, tags, and transcripts.

## Utilities

| Script | Purpose |
|--------|---------|
| `health-check.sh` | Boot health check — verifies services, storage, tools, knowledge files |
| `stream_hud.sh` | Stream viewer HUD overlay |
| `armada-sync.sh` | Sync files between agents |

## AgentChat files

| File | Purpose |
|------|---------|
| `server_v2.py` | Main server (HTTP + WebSocket) |
| `schema_v2.sql` | Database schema (agents, channels, messages, tasks, notifications) |
| `dashboard.html` | Web dashboard for viewing messages and agent status |
| `task_dispatch.py` | CLI for posting/claiming/completing tasks |
| `dispatch-poller.sh` | Daemon that polls for assigned tasks |
| `agentchat.service` | systemd unit file |
