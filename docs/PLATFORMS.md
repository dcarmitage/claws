# Platform Support

claws runs on any machine with Python 3.11+ and a terminal.

## Supported platforms

| Platform | Status | Notes |
|----------|--------|-------|
| **Linux** (x86_64, arm64) | Fully supported | Tested on Ubuntu, Debian, Raspberry Pi OS |
| **macOS** (Intel, Apple Silicon) | Fully supported | Native Python 3.11+ required |
| **Windows** (WSL2) | Supported | Use WSL2 with Ubuntu; native Windows not tested |

## Requirements

| Dependency | Minimum version | Purpose |
|-----------|----------------|---------|
| Python | 3.11+ | Core CLI and all Python tools |
| pip | 21+ | Package installation |
| git | 2.30+ | Version control, event log |

## Optional dependencies

These are only needed for specific features:

| Dependency | Purpose |
|-----------|---------|
| Node.js 20+ | AgentChat dashboard |
| jq 1.6+ | JSON processing in shell scripts |
| curl 7.0+ | LLM API calls from shell |
| sqlite3 3.35+ | AgentChat message storage |
| ffmpeg | Audio/video transcription tools |

## Installation

```bash
pip install claws
claws init
```

claws works the same way on all supported platforms. Hardware-specific features (camera, microphone, AI accelerator) are available as optional tools when the hardware is present.
