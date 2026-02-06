# Infrastructure Scout Report: Raspberry Pi 5 (Portal1) + Pi 4 (Portal2)

**Date:** 2026-02-06
**Audited by:** Infrastructure Scout Agent
**Systems:** Portal1 (Pi 5, 192.168.1.64), Portal2 (Pi 4, SSH alias `portal2`)

---

## 1. Vanilla Pi 5 State

### Operating System

| Property | Value |
|---|---|
| **OS** | Debian GNU/Linux 13 (trixie) — NOT Raspberry Pi OS Lite |
| **Kernel** | 6.12.47+rpt-rpi-2712 (aarch64, PREEMPT) |
| **Architecture** | ARM64 (aarch64) |
| **Debian version** | 13.2 |
| **Python** | 3.13.5 (system) |
| **Node.js** | 22.22.0 (nodesource) |

> **Note:** This is Debian trixie (testing/stable), not the standard Raspberry Pi OS. It uses the RPi kernel but the Debian userland. This is more bleeding-edge than a typical Pi setup.

### Pre-installed Tools

**Available (verified `which`):**
| Tool | Path | Notes |
|---|---|---|
| bash | /usr/bin/bash | Default shell |
| python3 | /usr/bin/python3 | 3.13.5 — very recent |
| python | /usr/bin/python | Symlink to python3 |
| pip3/pip | /usr/bin/pip3 | 25.1.1 |
| apt/apt-get | /usr/bin/apt | Package manager |
| dpkg | /usr/bin/dpkg | Low-level package tool |
| systemctl | /usr/bin/systemctl | Service management |
| journalctl | /usr/bin/journalctl | Log viewer |
| ssh/scp | /usr/bin/ssh | OpenSSH 10.0p1 |
| rsync | /usr/bin/rsync | File sync |
| curl | /usr/bin/curl | 8.14.1 |
| wget | /usr/bin/wget | Downloader |
| git | /usr/bin/git | 2.47.3 |
| nano | /usr/bin/nano | Text editor |
| tmux | /usr/bin/tmux | Terminal multiplexer |
| htop | /usr/bin/htop | Process viewer |
| node | (via nodesource) | 22.22.0 |
| npm | (via nodesource) | Global packages installed |
| build-essential | installed | gcc 14.2.0, make 4.4.1, cmake 3.31.6 |

**NOT available:**
vim, screen, docker, nginx, caddy, ufw, yarn, bun, cargo, rustc, go

### Default User Setup

| Property | Value |
|---|---|
| **User** | `dcarmitage` (uid=1000, gid=1000) |
| **Groups** | adm, dialout, cdrom, **sudo**, audio, video, plugdev, games, users, input, render, netdev, **spi**, **i2c**, **gpio** |
| **Sudo** | `ALL=(ALL) NOPASSWD: ALL` — full passwordless sudo |
| **clawd user** | **Does NOT exist** on Portal1. `/home/clawd/` is owned by `dcarmitage:dcarmitage` (mode 755) — it's just a directory, not a separate user account |
| **Shell** | /bin/bash |
| **Home** | /home/dcarmitage (mode 700) |

### Network Configuration

| Property | Value |
|---|---|
| **Manager** | NetworkManager (active) — dhcpcd is **not** used |
| **WiFi** | wlan0, connected to "Maya" (5.22 GHz, -39 dBm = excellent) |
| **IP** | 192.168.1.64/24 |
| **IPv6** | 2603:7000:873a:69a7:8aa2:9eff:fe36:bed6/64 (SLAAC) |
| **Gateway** | 192.168.1.1 |
| **DNS** | 192.168.1.1 (via NetworkManager) |
| **Ethernet** | eth0 present but NO-CARRIER (cable not connected) |

### Open Ports (Portal1)

| Port | Bind | Process | Purpose |
|---|---|---|---|
| 22 | 0.0.0.0 + [::] | sshd | SSH server |
| 3000 | * | node | Unknown node app |
| 4101 | 127.0.0.1 | node (agentchat-bridge) | AgentChat bridge to OpenClaw |
| 5080 | 0.0.0.0 | python3 | Camera service (camservice.py) |
| 5092 | 0.0.0.0 | python | Parakeet STT (system service) |
| 5095 | 127.0.0.1 | python3 | Polylogue webhook (Cloudflare ingress) |
| 5111 | 127.0.0.1 | python3 | Unknown python service |
| 9090 | 0.0.0.0 | python3 | AgentChat V2 server |
| 9091 | 0.0.0.0 | python3 | AgentChat (secondary port) |
| 18789 | 0.0.0.0 | openclaw-gateway | OpenClaw Gateway (LAN-accessible!) |
| 18792 | 127.0.0.1 | openclaw-gateway | Internal gateway port |
| 20241 | 127.0.0.1 | cloudflared | Cloudflare Tunnel connector |

### Firewall State

```
ufw:       NOT INSTALLED
iptables:  NO RULES (empty chains, default ACCEPT)
nftables:  NO RULES
```

**⚠️ There is ZERO firewall protection.** Every port bound to 0.0.0.0 is accessible from any device on the local network (and potentially from the internet if the router forwards ports). This includes the OpenClaw gateway on port 18789.

---

## 2. OpenClaw Installation & State

### Installation

| Property | Value |
|---|---|
| **Binary** | `/home/dcarmitage/.npm-global/bin/openclaw` |
| **Version** | 2026.2.3-1 (d84eb46) |
| **Installed via** | npm global (`~/.npm-global/lib/node_modules/openclaw/`) |
| **Node.js runtime** | v22.22.0 |
| **Config dir** | `/home/dcarmitage/.openclaw/` (mode 700) |
| **Workspace** | `/home/dcarmitage/.openclaw/workspace/` |
| **Agent home** | `/home/clawd/` (the operational workspace) |
| **Sessions** | 1,289 session files |

### Config Structure (`~/.openclaw/`)

```
~/.openclaw/
├── openclaw.json            # Main config (gateway, auth, tools, channels, hooks)
├── clawdbot.json            # Legacy config (from v2026.1.24)
├── agents/main/             # Agent state
│   ├── agent/auth-profiles.json   # API tokens (Anthropic OAT + OAuth)
│   └── sessions/            # 1,289 session transcripts
├── canvas/                  # Canvas/UI data
├── completions/             # Completion logs
├── credentials/             # Telegram allowlists, pairing data
├── cron/jobs.json           # Cron job definitions (2 jobs, both disabled)
├── devices/                 # Device registry
├── extensions/agentchat/    # AgentChat plugin
├── identity/                # Agent identity files
├── logs/                    # OpenClaw internal logs
├── media/inbound/           # 100+ media files from Telegram
├── state/                   # Runtime state
├── subagents/runs.json      # Subagent tracking
├── telegram/                # Telegram bot state
├── update-check.json        # Update check timestamp
└── workspace/               # Agent operating manuals
    ├── AGENTS.md            # How to be an agent (session startup, memory, safety)
    ├── BOOTSTRAP.md         # First-run onboarding script
    ├── HEARTBEAT.md         # Heartbeat instructions
    ├── IDENTITY.md          # Agent identity template
    ├── SOUL.md              # Personality/values
    ├── TOOLS.md             # Environment-specific tool notes (template)
    ├── USER.md              # User profile
    └── .git/                # Version controlled
```

### What `openclaw onboard` Sets Up

Based on the workspace files and config structure, onboarding:
1. Creates `~/.openclaw/openclaw.json` with gateway, auth, and channel config
2. Initializes the workspace directory with template markdown files
3. Runs the BOOTSTRAP.md flow — agent introduces itself, picks a name/identity
4. Sets up auth profiles (Anthropic API tokens)
5. Optionally configures channels (Telegram bot, WhatsApp via QR, AgentChat)
6. Starts the gateway process
7. Creates `IDENTITY.md`, `USER.md`, `SOUL.md` through conversation

### Gateway Configuration

| Property | Value |
|---|---|
| **Port** | 18789 (main), 18792 (internal) |
| **Bind** | `lan` — accessible from any device on the LAN |
| **Auth** | Bearer token (configured in openclaw.json) |
| **Endpoints** | OpenAI-compatible `/v1/chat/completions` |
| **Model** | anthropic/claude-opus-4-5 (primary, no fallbacks) |
| **Max concurrent** | 4 agents, 8 subagents |
| **Managed by** | systemd user service (`openclaw-gateway.service`) |

### Running Services (systemd)

**System-level services (`/etc/systemd/system/`):**
| Service | Description |
|---|---|
| camservice.service | Picamera2 camera service (`/home/clawd/tools/camservice.py`) |
| parakeet.service | Parakeet TDT STT service |
| agentchat.service | AgentChat V2 server (port 9090) |
| hailort.service | Hailo-8 AI accelerator runtime |

**User-level services (`~/.config/systemd/user/`):**
| Service | Description |
|---|---|
| openclaw-gateway.service | OpenClaw Gateway on port 18789 |
| agentchat-bridge.service | Bridge between AgentChat and OpenClaw gateway |
| cloudflared-tunnel.service | Cloudflare Tunnel (ingress → localhost:5095) |
| transcription.service | Parakeet transcription (2G memory limit, 200% CPU quota) |

### Channels Configured

| Channel | Status | Details |
|---|---|---|
| **Telegram** | Enabled | Bot token active, DM pairing mode, group allowlist |
| **AgentChat** | Enabled | Server at 127.0.0.1:9090, agent name "Portal1" |
| **Cloudflare Tunnel** | Active | Tunnel ff6c94d5, ingress to 127.0.0.1:5095 |

---

## 3. Security Boundaries

### What an Agent Can Do WITHOUT Sudo

| Capability | Status | Notes |
|---|---|---|
| Read/write files in /home/dcarmitage/ | ✅ YES | Home dir is mode 700, but agent runs as dcarmitage |
| Read/write files in /home/clawd/ | ✅ YES | Owned by dcarmitage, mode 755 |
| Read/write /tmp/ | ✅ YES | Standard temp directory |
| Open network ports (>1024) | ✅ YES | Tested: `bind('0.0.0.0', 12345)` works |
| Generate SSH keys | ✅ YES | `ssh-keygen` works without sudo |
| Install Python packages (pip) | ✅ YES | pip install --user works |
| Install npm packages (global) | ✅ YES | npm -g uses ~/.npm-global/ |
| Run Python web servers | ✅ YES | http.server + ssl module available |
| Create cron jobs | ✅ YES | Via OpenClaw's cron system |
| Git operations | ✅ YES | Full git access |
| SSH to Portal2 | ✅ YES | Key-based auth configured |
| Access GPIO | ✅ YES | User is in `gpio` group, /dev/gpiochip* available |
| Access I2C | ✅ YES | User is in `i2c` group |
| Access SPI | ✅ YES | User is in `spi` group |
| Access camera | ✅ YES | Via camservice.py API on port 5080 |
| Access audio | ✅ YES | User in `audio` group, USB mic available |

### What REQUIRES Sudo

| Capability | Status | Notes |
|---|---|---|
| Install system packages (apt install) | ❌ NEEDS SUDO | `apt install` requires root |
| Manage system services (systemctl restart) | ❌ NEEDS SUDO | System services need root |
| Write to /usr/local/bin/ | ❌ NEEDS SUDO | System directories are protected |
| Open ports <1024 | ❌ NEEDS SUDO | Privileged ports |
| Install firewall rules | ❌ NEEDS SUDO | iptables/ufw require root |
| Modify /etc/ config files | ❌ NEEDS SUDO | System config is protected |
| Create new system users | ❌ NEEDS SUDO | useradd requires root |

**However:** dcarmitage has `NOPASSWD: ALL` sudo, so effectively the agent CAN do anything with `sudo`. The boundary is "will the agent choose to use sudo" not "can it."

### Port Security

- **No firewall at all.** Any port bound to 0.0.0.0 is LAN-accessible.
- Ports currently exposed to LAN: 22 (SSH), 3000, 5080 (camera), 5092 (STT), 9090/9091 (AgentChat), 18789 (OpenClaw gateway)
- The OpenClaw gateway on 18789 is authenticated (Bearer token) but the token is in plaintext in service files and config
- Camera service (5080) and AgentChat (9090) appear to have NO authentication

### SSH Key Management

| File | Purpose |
|---|---|
| `~/.ssh/id_ed25519` | dcarmitage's SSH key |
| `~/.ssh/authorized_keys` | 2 keys: dcarmitage@gmail.com + portal2@portal2 |
| `/home/clawd/.ssh/agentchat_deploy` | Deployment key for AgentChat |
| No `~/.ssh/config` | SSH aliases must use /etc/hosts or mDNS |

Portal2 can SSH into Portal1 (authorized key present). Portal1 can SSH into Portal2 (tested and working).

### File Permission Map

```
/home/dcarmitage/     700 dcarmitage:dcarmitage  (private)
/home/dcarmitage/.openclaw/  700 dcarmitage:dcarmitage  (private, contains tokens)
/home/clawd/          755 dcarmitage:dcarmitage  (world-readable, writable by agent)
/home/clawd/.ssh/     700 dcarmitage:dcarmitage  (private)
/home/clawd/.claude/  (exists, owned by dcarmitage)
/tmp/                 world-writable
```

### Secure Web Hosting Options

| Option | Available? | Notes |
|---|---|---|
| nginx | ❌ Not installed | Would need `sudo apt install nginx` |
| caddy | ❌ Not installed | Would need installation |
| python3 http.server | ✅ Available | Built-in, supports SSL via ssl module |
| Node.js http/https | ✅ Available | node 22.22, can create HTTPS servers |
| Cloudflare Tunnel | ✅ Active | Already running, provides HTTPS without cert management |
| Let's Encrypt | ❌ No certbot | Would need installation |

**Best option for quick secure hosting:** Cloudflare Tunnel (already running) or Python's http.server with a self-signed cert. For production, install caddy (auto-HTTPS) via sudo.

---

## 4. Available Hardware

### Portal1: Raspberry Pi 5 Model B Rev 1.1

| Component | Details |
|---|---|
| **CPU** | BCM2712 (Cortex-A76), 4 cores, aarch64 |
| **RAM** | 16 GB (15Gi total, ~8Gi available) |
| **Storage — SD** | 58.9 GB microSD (mmcblk0), 41 GB free (27% used) |
| **Storage — USB** | 60 GB SanDisk iXpand Flash Drive at /mnt/media, 57 GB free |
| **Swap** | 2 GB zram (21 MB used) |
| **WiFi** | Built-in, 802.11ac, 5 GHz, 433.3 Mbps link |
| **Ethernet** | Gigabit (eth0), cable not connected |
| **USB** | 2x USB 3.0, 2x USB 2.0 (audio codec + flash drive connected) |
| **GPIO** | Full 40-pin header, gpiochip0/4/10-13 available |
| **Camera** | CSI camera connected (rp1-cfe driver, /dev/video0-7) |
| **AI Accelerator** | **Hailo-8** present (/dev/hailo0, FW 4.23.0, release build) |
| **Audio — Input** | USB C-Media PCM2902 Audio Codec (capture device) |
| **Audio — Output** | 2x HDMI (vc4-hdmi-0, vc4-hdmi-1), no display connected |
| **Display** | 2x HDMI outputs available, both disconnected |
| **Bluetooth** | Active (bluetooth.service running) |

### Portal2: Raspberry Pi 4 (via SSH)

| Component | Details |
|---|---|
| **CPU** | Cortex-A72, 4 cores, aarch64 |
| **RAM** | 4 GB (3Gi available) |
| **Storage** | 59 GB SD card, 51 GB free |
| **USB** | VIA Labs hub + PCM2902 audio codec |
| **Camera** | Video devices present (video10-23, video31) |
| **Hailo** | ❌ Not present |
| **OpenClaw** | 2026.2.2 installed, gateway running (loopback only) |
| **Cloudflared** | Active tunnel on port 20241 |

### Key Difference: Portal2's gateway binds to localhost only (not LAN), while Portal1's binds to all interfaces.

---

## 5. Agent Capabilities via OpenClaw

### Tools Available to `openclaw agent`

Based on the AGENTS.md workspace documentation and observed behavior:

| Tool | Available | Notes |
|---|---|---|
| **Bash/Shell execution** | ✅ | Full shell access as dcarmitage |
| **File read/write** | ✅ | Full filesystem access |
| **Web search** | ✅ | Via OpenClaw built-in |
| **Memory** | ✅ | Session memory, daily files, MEMORY.md |
| **Cron scheduling** | ✅ | Via `openclaw cron` |
| **Telegram messaging** | ✅ | Bot configured and active |
| **AgentChat** | ✅ | Inter-agent communication |
| **Audio transcription** | ✅ | Parakeet STT via CLI tool |
| **Camera capture** | ✅ | Via camservice API on port 5080 |

### Session Management

- Agent model: `anthropic/claude-opus-4-5` (primary)
- Max concurrent agents: 4
- Max concurrent subagents: 8
- Context pruning: cache-TTL mode, 1h TTL
- Compaction: safeguard mode
- Heartbeat: every 1 hour
- Session isolation: cron jobs can run in isolated sessions
- Timeout: 600s default for agent invocations

### Can It Install Packages?

| Method | Works? | Notes |
|---|---|---|
| `pip install --user` | ✅ | No sudo needed |
| `npm install -g` | ✅ | Uses ~/.npm-global/ |
| `sudo apt install` | ✅ | dcarmitage has NOPASSWD sudo |
| `apt install` (no sudo) | ❌ | Fails with permission error |

### Can It Start Services?

| Method | Works? | Notes |
|---|---|---|
| `systemctl --user start/stop/restart` | ✅ | User services (gateway, tunnel, etc.) |
| `systemctl start/stop/restart` | ❌ without sudo | System services need root |
| `sudo systemctl ...` | ✅ | Works due to NOPASSWD sudo |

### Can It Open Ports?

| Port Range | Works? | Notes |
|---|---|---|
| Ports > 1024 | ✅ | No restrictions, no firewall |
| Ports < 1024 | ❌ without sudo | Privileged ports need root |
| Any port via sudo | ✅ | NOPASSWD sudo enables anything |

### Can It Generate SSH Keys?

✅ **Yes.** `ssh-keygen` works without any special permissions. Tested and verified.

### Actual Limits

The practical limits are:
1. **RAM:** 16 GB total, ~8 GB available. Heavy models or large datasets will OOM.
2. **CPU:** 4 cores at ~2.4 GHz. CPU-bound tasks are real bottleneck.
3. **Storage:** 41 GB free on SD, 57 GB on USB. SD cards have limited write endurance.
4. **Network:** WiFi only (433 Mbps theoretical, ~50-100 Mbps real). No ethernet.
5. **No Docker:** Container-based isolation not available without installation.
6. **No firewall:** Network security is entirely absent.
7. **Agent autonomy:** OpenClaw agent has the same permissions as dcarmitage — effectively root.

---

## 6. Permission Checklist

### What a Human Must Pre-Configure

```
[HUMAN PRE-CONFIG] SSH key for Portal2 access
  — Needed for multi-Pi orchestration
  — Already done: portal2 key in ~/.ssh/authorized_keys
  — Command: ssh-copy-id portal2

[HUMAN PRE-CONFIG] OpenClaw onboarding
  — Needed to create config, workspace, agent identity
  — Already done: openclaw.json exists with full config
  — Command: openclaw onboard

[HUMAN PRE-CONFIG] Anthropic API token
  — Needed for LLM access via gateway
  — Already done: tokens in auth-profiles.json
  — Command: openclaw configure (interactive wizard)

[HUMAN PRE-CONFIG] Telegram bot token (optional)
  — Needed for Telegram channel
  — Already done: bot token in openclaw.json
  — Command: Talk to @BotFather, paste token into openclaw configure

[HUMAN PRE-CONFIG] Cloudflare Tunnel (optional)
  — Needed for HTTPS access from outside LAN
  — Already done: tunnel ff6c94d5 active
  — Command: cloudflared tunnel create <name> && cloudflared tunnel route dns <name> <hostname>

[HUMAN PRE-CONFIG] System service installation (camera, STT, etc.)
  — Needed for hardware access via API
  — Already done: camservice, parakeet, agentchat systemd services
  — Command: sudo systemctl enable --now <service>

[HUMAN PRE-CONFIG] Hailo runtime installation
  — Needed for AI accelerator access
  — Already done: hailort.service running, /dev/hailo0 accessible
  — Command: Follow Hailo SDK installation docs

[HUMAN PRE-CONFIG] GPIO/I2C/SPI group membership
  — Needed for hardware control
  — Already done: dcarmitage is in gpio, i2c, spi groups
  — Command: sudo usermod -aG gpio,i2c,spi <username>

[HUMAN PRE-CONFIG] USB audio device connection
  — Needed for microphone input
  — Already done: PCM2902 codec on USB
  — Physical: Plug in USB audio adapter

[HUMAN PRE-CONFIG] WiFi network connection
  — Needed for internet access
  — Already done: connected to "Maya" via NetworkManager
  — Command: nmcli device wifi connect "<SSID>" password "<pass>"
```

### What is NOT Pre-Configured (Gaps)

```
[MISSING] Firewall (ufw or nftables)
  — Risk: All LAN ports are exposed with zero protection
  — Fix: sudo apt install ufw && sudo ufw enable && sudo ufw allow ssh
  — Recommended rules: allow 22, deny everything else by default, selectively open as needed

[MISSING] Ethernet connection
  — eth0 is DOWN (no cable). WiFi-only = single point of failure
  — Fix: Connect ethernet cable, configure via nmcli

[MISSING] Docker
  — No container isolation available
  — Fix: sudo apt install docker.io && sudo usermod -aG docker dcarmitage

[MISSING] Separate agent user
  — Agent runs as dcarmitage with full sudo. No privilege separation.
  — Risk: A compromised agent has root access to everything
  — Fix: Create a restricted 'agent' user with limited sudo permissions

[MISSING] vim / screen
  — Minor but some tools/scripts expect vim
  — Fix: sudo apt install vim screen

[MISSING] Web server (nginx/caddy)
  — No production-grade web server for hosting
  — Fix: sudo apt install nginx (or download caddy binary)

[MISSING] SSL certificates
  — No Let's Encrypt/certbot for HTTPS
  — Fix: sudo apt install certbot (or use Cloudflare Tunnel which handles TLS)

[MISSING] libcamera-hello
  — Camera is connected but libcamera CLI tools not installed
  — Fix: sudo apt install libcamera-apps

[MISSING] Backup system
  — No automated backups of SD card or /home/clawd/
  — Fix: Set up rsync cron job to USB drive or remote

[MISSING] Monitoring/alerting
  — No monitoring of disk space, memory, service health
  — Fix: Install prometheus-node-exporter or simple health check cron
```

---

## 7. Portal2 Comparison

| Property | Portal1 (Pi 5) | Portal2 (Pi 4) |
|---|---|---|
| CPU | Cortex-A76 (4 cores) | Cortex-A72 (4 cores) |
| RAM | 16 GB | 4 GB |
| OpenClaw | 2026.2.3-1 | 2026.2.2 |
| Gateway bind | LAN (0.0.0.0) | Loopback only (127.0.0.1) |
| Hailo AI | ✅ Hailo-8 | ❌ Not present |
| Camera | CSI connected | V4L2 devices present |
| Cloudflared | ✅ Active | ✅ Active |
| Storage | 58GB SD + 60GB USB | 59GB SD |
| SSH access | ↔ Bidirectional | ↔ Bidirectional |

---

## 8. Architecture Summary

```
                    ┌─────────────────────────────────────────┐
                    │           Internet / Cloudflare          │
                    │  Tunnel ff6c94d5 → 127.0.0.1:5095       │
                    └───────────────────┬─────────────────────┘
                                        │
          ┌─────────────────────────────┼──────────────────────────────┐
          │                    Portal1 (Pi 5)                          │
          │  192.168.1.64 (WiFi)                                       │
          │                                                            │
          │  ┌──────────────────┐  ┌──────────────────┐                │
          │  │ OpenClaw Gateway │  │ Claude Code 2.1   │               │
          │  │ :18789 (LAN)    │  │ (interactive)      │               │
          │  │ :18792 (local)  │  │                    │               │
          │  └────────┬─────────┘  └────────────────────┘              │
          │           │                                                │
          │  ┌────────┼────────────────────────────────────┐           │
          │  │ Services                                     │          │
          │  │  :5080  camservice (Picamera2)               │          │
          │  │  :5092  parakeet STT                         │          │
          │  │  :5095  polylogue webhook                    │          │
          │  │  :9090  agentchat V2                         │          │
          │  │  :4101  agentchat-bridge                     │          │
          │  │  :3000  node app                             │          │
          │  └──────────────────────────────────────────────┘          │
          │                                                            │
          │  Hardware: Hailo-8, CSI Camera, USB Audio, GPIO            │
          │  Storage:  58GB SD (41GB free) + 60GB USB (57GB free)      │
          └────────────────────────┬───────────────────────────────────┘
                                   │ SSH
          ┌────────────────────────┼───────────────────────────────────┐
          │                   Portal2 (Pi 4)                           │
          │  WiFi (IP unknown from this audit)                         │
          │                                                            │
          │  OpenClaw 2026.2.2, gateway on localhost only              │
          │  Cloudflared tunnel active                                 │
          │  Camera interfaces, USB audio                              │
          │  4GB RAM, 59GB SD (51GB free)                              │
          │  No Hailo AI accelerator                                   │
          └────────────────────────────────────────────────────────────┘
```

---

## 9. Key Takeaways for Curriculum Design

1. **Agent = Root.** The agent runs as dcarmitage with NOPASSWD sudo. There is no privilege separation. Any security boundary is voluntary, not enforced.

2. **No Firewall.** The network is wide open. Any service bound to 0.0.0.0 is accessible to every device on the WiFi network.

3. **OpenClaw is the control plane.** Gateway on 18789 provides API access, channels (Telegram, AgentChat) provide human interface, cron provides scheduling. Claude Code (2.1.34) provides interactive agent sessions.

4. **Hardware is rich.** Camera, microphone, Hailo-8 AI accelerator, GPIO/I2C/SPI, Bluetooth — this is a capable edge computing platform.

5. **Storage is adequate but watch write endurance.** 41GB free on SD card. For intensive logging or media, use the 60GB USB drive at /mnt/media.

6. **Two-Pi architecture is operational.** Portal1 (muscle, 16GB, Hailo) and Portal2 (lightweight, 4GB) communicate via SSH. Portal1's gateway is LAN-accessible; Portal2's is localhost-only.

7. **Credentials are in plaintext.** Anthropic API tokens, Telegram bot token, gateway auth token, AgentChat password — all stored in JSON config files. This is standard for OpenClaw but important to know.

8. **Fresh onboard path:** `openclaw onboard` → creates workspace → runs BOOTSTRAP.md → agent picks identity → human configures channels → gateway starts. The whole process is conversational.
