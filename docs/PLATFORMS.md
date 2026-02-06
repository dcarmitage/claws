# Platform Notes

## Raspberry Pi 5 (recommended)

- **CPU:** BCM2712 (Cortex-A76), 4 cores
- **RAM:** 16GB recommended, 8GB minimum
- **Storage:** 64GB+ microSD, USB drive for media
- **OS:** Raspberry Pi OS Lite 64-bit or Debian Bookworm+
- **Extras:** Hailo-8 AI accelerator (optional), CSI camera, USB audio

The Pi 5 handles LLM-gated builds, dual-judge evals, and multiple services concurrently. 16GB RAM is recommended for running Parakeet STT alongside agents.

## Raspberry Pi 4

- **CPU:** Cortex-A72, 4 cores
- **RAM:** 4GB or 8GB
- **Good for:** Lightweight agent tasks, task execution, poller daemons
- **Limitations:** Slower inference, less concurrent capacity

Works well as a secondary agent (Agent Beta) that receives dispatched tasks from a Pi 5.

## Mac Mini / Mac Studio

- **Good for:** Development, testing, orchestration
- **Note:** OpenClaw and Claude Code work natively on macOS
- **Camera/GPIO:** Not available (use Pi for hardware interaction)

## General requirements

| Dependency | Minimum version | Used by |
|-----------|----------------|---------|
| Python | 3.11+ | All Python tools |
| Node.js | 20+ | Ralph-loops dashboard, OpenClaw |
| bash | 5.0+ | All shell scripts |
| jq | 1.6+ | Judge scripts, JSON processing |
| bc | any | Score threshold comparison |
| curl | 7.0+ | LLM API calls |
| git | 2.30+ | Version control |
| sqlite3 | 3.35+ | AgentChat, media catalog |
