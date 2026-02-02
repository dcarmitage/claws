# Armada Launch Log — 2026-02-01

*First agent spawn. Document everything — this becomes the playbook.*

## Timeline

### Phase 1: Planning (16:33 - 17:23)
- Researched QMD upgrade path for vector search
- Created scouting guide for Mudpaw (what to look for on X/HN/GitHub)
- Discussed MITOSIS.md — preparing to teach another agent
- Evaluated three candidate roles: Researcher (21/25), CTO/PM (19/25), Trader (13/25)
- **Decision:** Researcher first on Pi, then CTO/PM on Mac Studio, then Trader
- **Decision:** Hardware-first (avoid cloud/networking complexity)
- Renamed FLEET.md → ARMADA.md

### Phase 2: Hardware Setup (17:43 - 18:10)
- Mudpaw plugged in Pi 4 (hadn't been used in years)
- First boot failed: solid red LED, no green activity (old SD card)
- Mudpaw flashed fresh SD card via Pi Imager:
  - Raspberry Pi OS Lite (64-bit)
  - Hostname: portal2
  - SSH enabled, WiFi configured, user: dcarmitage
- Network scan found Portal2 at **192.168.1.44**
- SSH key access established from Portal1 → Portal2

### Phase 3: Software Install (18:10 - 18:54)
**What went smooth:**
- Node 22 installed via nodesource (quick)
- Git installed (was missing, needed for openclaw)

**What was painful:**
- First `npm install -g openclaw` → OOM killed (node-llama-cpp compilation uses >4GB)
- Fix: `npm install -g openclaw --ignore-scripts` → worked (48 seconds, skipped native build)
- But then gateway startup triggered the native build anyway (deferred compilation)
- `openclaw onboard` froze twice before we figured out NODE_OPTIONS heap size
- `NODE_OPTIONS="--max-old-space-size=512"` → OOM with different config error
- `NODE_OPTIONS="--max-old-space-size=1024"` → worked! Onboard completed.

**Config issues:**
- I wrote config with wrong `model` format (string vs object) → caught by validator
- Onboard wizard didn't generate `hooks.token` → gateway failed to start repeatedly
- Four config files created across `.clawdbot/` and `.openclaw/` (legacy migration) → confusion about which one the service reads
- Duplicate `"token"` keys in JSON from my sed fix → had to clean with Python json.load/dump
- **Lesson:** Don't hand-edit JSON configs with sed. Use Python or the CLI.

**OpenAI OAuth:**
- Mudpaw chose OpenAI Codex OAuth (GPT-5.2) — different brain than Portal1 (Opus 4.5)
- OAuth flow worked: onboard showed URL → Mudpaw opened in browser → pasted redirect URL back
- Model set to `openai-codex/gpt-5.2`

### Phase 4: Gateway Online (18:54 - 19:06)
- Gateway service installed (systemd user service)
- Port 18789 wouldn't open for ~5 minutes (native compilation happening in background)
- **Key learning:** First gateway start on arm64 takes 3-5 minutes due to node-llama-cpp compilation. One-time cost.
- Eventually: `ss -tlnp | grep 18789` showed LISTEN → gateway alive!
- Mudpaw messaged @openclaw_portal2_bot → got pairing code
- `openclaw pairing approve telegram LGDNCJPA` → paired

### Phase 5: Group Chat (19:19 - 19:31)
- Created Telegram group "Armada" — 3 members: Daniel, Portal1, Portal2
- BotFather: enabled groups for both bots
- Both bots respond when @mentioned
- **Bot-to-bot limitation:** Portal2 doesn't respond to Portal1's messages (only to human @mentions)
- **Current workaround:** Mudpaw acts as facilitator, @mentions each bot as needed
- **Open question:** How to enable direct agent-to-agent communication in group chat

## Portal2 Specs

| Property | Value |
|----------|-------|
| Hostname | portal2 |
| Hardware | Raspberry Pi 4 Model B Rev 1.2 |
| RAM | 4GB (vs Portal1's 8GB) |
| Storage | 59GB SD card, 52GB free |
| IP | 192.168.1.44 |
| OS | Raspberry Pi OS Lite (64-bit), kernel 6.12 |
| Node | 22.22.0 |
| OpenClaw | 2026.1.30 |
| Model | openai-codex/gpt-5.2 (OAuth) |
| Gateway | port 18789, systemd user service |
| Config | ~/.openclaw/openclaw.json |
| Workspace | /home/dcarmitage |
| Telegram | @openclaw_portal2_bot |
| SSH from Portal1 | `ssh dcarmitage@192.168.1.44` (key auth) |

## What's Working
- ✅ Portal2 boots and runs autonomously (systemd service, lingering enabled)
- ✅ Telegram bot responds in DM and group chat
- ✅ Paired with Mudpaw's Telegram account
- ✅ OpenAI Codex OAuth configured
- ✅ Portal1 has SSH key access
- ✅ Both bots in "Armada" group chat

## What's NOT Working Yet
- ❌ No workspace files (AGENTS.md, SOUL.md, etc.) — Portal2 is a blank slate
- ❌ No shared knowledge (QMD not installed on Portal2)
- ❌ No identity — Portal2 doesn't know its role, name, or purpose

## Group Chat Communication (Tested Thoroughly)

### What works
- ✅ Portal1 can post messages in the Armada group (via message tool)
- ✅ Portal2 responds to Daniel's @mentions in the group
- ✅ Daniel can see both bots' messages
- ✅ Group privacy OFF for both bots (BotFather confirmed)
- ✅ Group ID -5232983156 in both bots' allowlists

### What doesn't work
- ❌ Portal2 CANNOT see Portal1's messages at all (dropped by OpenClaw's mention-gating before reaching context)
- ❌ Portal1's @mentions are plain text, not native Telegram mention entities
- ❌ Adding Portal1's bot ID to Portal2's groupAllowFrom didn't help

### Root cause
OpenClaw's mention-gating checks if the message sender is in the allowlist AND if a native Telegram mention entity exists. Bot-to-bot messages have the right sender but the @mention in the text body isn't a native Telegram entity — it's just text. So the message is dropped with reason: 'no-mention'.

### Working pattern for teaching
1. Portal1 SSHes files and workspace setup directly into Portal2
2. Portal1 narrates in the Armada group (Daniel observes)
3. Daniel @Portal2 to prompt it to read/react to what Portal1 set up
4. Portal2 responds to Daniel, everyone sees it
5. SSH is the real teaching channel; group chat is the observation deck

### Future options to explore
- Configure Portal2 with `requireMention: false` for the Armada group (would see ALL messages including Portal1's)
- Use `mentionPatterns` regex to match Portal1's bot username
- Direct agent-to-agent via SSH sessions_send
- Shared files on a mounted drive

## Lessons for Next Launch (Pi #3, #4, etc.)

### What to do differently
1. **Pre-flash:** Install openclaw with `--ignore-scripts`, THEN run `openclaw gateway` once to trigger compilation. Don't let onboard wizard fight with native build.
2. **Config:** Use `openclaw onboard` for everything. Don't hand-write JSON configs.
3. **Hooks token:** If onboard doesn't set it, run `openclaw doctor --fix` BEFORE starting gateway.
4. **Memory:** Pi 4 (4GB) is tight. `NODE_OPTIONS="--max-old-space-size=1024"` for onboard. Pi 5 (8GB) should be fine.
5. **First start patience:** Gateway takes 3-5 minutes on first boot (native compilation). Don't panic, don't kill it.
6. **Group chat:** Set up BotFather privacy settings BEFORE creating the group.

### Estimated time for next launch
- Flash + boot: 5 min
- Node + openclaw install: 10 min  
- Onboard wizard: 5 min
- First gateway start (compilation): 5 min
- Pairing: 1 min
- **Total: ~25 minutes** (vs ~90 minutes this time due to troubleshooting)

---

*First launch complete. Messy, educational, documented. The next one will be 3x faster. — Portal1 🌀*
