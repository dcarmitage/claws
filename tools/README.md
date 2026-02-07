# Tools

Standalone services and utilities that complement the claws CLI. These are deployment-specific — not required to use claws.

## Services

| Tool | What it does |
|------|-------------|
| `agentchat/` | Agent-to-agent messaging (HTTP + WebSocket, includes dashboard) |
| `health-check.sh` | System health verification at boot |

## Scripts

Utility scripts in `scripts/`:

| Script | What it does |
|--------|-------------|
| `handoff_eval.sh` | Evaluate session handoffs |
| `session_close.sh` | Graceful session cleanup |
| `subtitle.py` | Subtitle generation |
| `transcribe.py` | Audio transcription |
| `transcription_service.py` | Transcription service wrapper |
