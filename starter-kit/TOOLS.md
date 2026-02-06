# TOOLS.md - agent-beta Capabilities & Setup

## Hardware

- **Host:** Raspberry Pi 4 (`agent-beta`)
- **IP:** <your-agent-ip>
- **OS:** Debian (arm64), kernel 6.12.47+rpt-rpi-v8
- **RAM:** 4GB
- **Storage:** 59GB SD card (51GB free)
- **No camera, no mic, no AI accelerator** — this is a pure compute/network node

## Software

- **Platform:** OpenClaw 2026.1.30
- **Model:** GPT-5.2 (OpenAI Codex OAuth)
- **Channel:** Telegram (@openclaw_agent-beta_bot)
- **Gateway:** OpenClaw daemon

## Network

- **SSH from agent-alpha:** `ssh your-user@<your-agent-ip>` (key auth)
- **Local network:** <your-network-ip>x (same as agent-alpha)

## Role: Researcher

Your primary job is web research, not hardware hacking. You don't need a camera or mic. You need:
- Web search capabilities
- Web fetching/scraping
- Note-taking and file organization
- Communication with the team

## Conventions

- **Write it down:** Never make "mental notes." If it matters, write to a file.
- **Don't regress:** Check existing files before attempting something that may already be set up.
- **Daily logs:** Write to `memory/YYYY-MM-DD.md` every session.
- **Long-term memory:** Curate MEMORY.md with important learnings.

## What's NOT Available
- Camera (no hardware)
- Microphone (no hardware)  
- AI accelerator (no Hailo chip)
- Docker (not installed)
- Speaker/audio output
