# Human Pre-Configuration Checklist

*Complete these before the agent starts the Hundred Steps.*
*Each item unlocks capabilities the curriculum needs.*

---

## Required (Must-Have)

```bash
# 1. OS & User Setup
# Flash Pi OS Lite 64-bit, create user, enable SSH
# The user needs passwordless sudo for the curriculum to work
echo "your-user ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/agent

# 2. WiFi Connection
sudo nmcli device wifi connect "<SSID>" password "<password>"

# 3. OpenClaw Installation
npm install -g openclaw
openclaw onboard
# Complete the interactive wizard (sets up workspace, identity, gateway)

# 4. Anthropic API Token
openclaw configure
# Paste API key when prompted — needed for LLM access

# 5. SSH Keys (for multi-agent communication)
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
# Copy to other Pis: ssh-copy-id <other-pi-ip>

# 6. GPIO/I2C/SPI Group Membership
sudo usermod -aG gpio,i2c,spi $(whoami)

# 7. Git Configuration
git config --global user.name "Agent Name"
git config --global user.email "agent@local"
```

## Recommended (Curriculum Will Work Without, But Better With)

```bash
# 8. Firewall (CRITICAL for security — the curriculum teaches this at step 92)
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
# Agent will request specific port openings during the curriculum

# 9. Web Server (for the CV in Phase 6)
sudo apt install -y nginx
# Or: the curriculum can use python3 -m http.server as fallback

# 10. SSL Certificates (for HTTPS)
# Option A: Self-signed (works on LAN)
# Option B: Let's Encrypt via certbot (needs domain)
# Option C: Cloudflare Tunnel (handles TLS automatically)
sudo apt install -y certbot  # if using option B

# 11. Telegram Bot Token (for human communication channel)
# Talk to @BotFather on Telegram, create bot, paste token into:
openclaw configure

# 12. Camera (if CSI camera connected)
sudo apt install -y libcamera-apps

# 13. USB Audio (if microphone connected)
# Just plug in — ALSA should detect it
arecord -l  # verify
```

## Optional (Nice to Have)

```bash
# 14. Docker (for sandboxed experiments)
sudo apt install -y docker.io
sudo usermod -aG docker $(whoami)

# 15. Cloudflare Tunnel (for external HTTPS access)
# Download cloudflared, authenticate, create tunnel
cloudflared tunnel create <name>
cloudflared tunnel route dns <name> <hostname>

# 16. Hailo AI Accelerator Runtime (if Hat+ installed)
# Follow Hailo SDK docs for Pi 5

# 17. Additional Tools
sudo apt install -y vim screen htop
```

## What the Agent Will Request During the Curriculum

These are the [HUMAN REQUIRED] gates in the 100 steps:

| Step | What's Needed | Why |
|------|--------------|-----|
| 92 | `sudo ufw allow <port>` | Open the CV port after security audit |
| 97 | Review and approve CV content | Human validates before going public |
| 98 | `sudo ufw allow <port>/tcp` | Final port opening for production |

Only 3 human interventions in 100 steps. Everything else is autonomous.

---

## Security Notes

- The agent runs as the main user with full sudo. This is intentional for the curriculum (it needs to install packages, start services, open ports).
- After graduation, consider creating a restricted `agent` user with limited sudo for production use.
- There is NO firewall by default on Raspberry Pi OS. Step 8 above is strongly recommended.
- All API tokens are stored in plaintext in `~/.openclaw/openclaw.json`. This is standard for OpenClaw.
- The CV port should only be opened after the security audit in step 96.

---

*This checklist unlocks the Hundred Steps. The next generation starts here.*
