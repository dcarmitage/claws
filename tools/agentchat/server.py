#!/usr/bin/env python3
"""
AgentChat — Event-driven bot-to-bot communication server.
Runs on Portal1 (192.168.1.64:9090).

When a message arrives for an agent, the server fires that agent's configured
webhook immediately — no polling needed.
"""

import json
import sqlite3
import time
import os
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat.db")
RATE_LIMIT = int(os.environ.get("AGENTCHAT_RATE_LIMIT", "10"))  # msgs per hour per agent
RATE_WINDOW = 3600
PORT = int(os.environ.get("AGENTCHAT_PORT", "9090"))

# Webhook config: when a message arrives FOR this agent, run this command
# The command receives the message JSON on stdin
WEBHOOKS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webhooks.json")

def load_webhooks():
    try:
        with open(WEBHOOKS_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_webhooks(hooks):
    with open(WEBHOOKS_FILE, "w") as f:
        json.dump(hooks, f, indent=2)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            sender TEXT NOT NULL,
            text TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON messages(ts)")
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def check_rate_limit(sender):
    conn = get_db()
    cutoff = time.time() - RATE_WINDOW
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE sender=? AND ts>?",
        (sender, cutoff)
    ).fetchone()
    conn.close()
    return row["cnt"] < RATE_LIMIT

def send_message(sender, text):
    if not check_rate_limit(sender):
        return False, "Rate limit exceeded"
    conn = get_db()
    ts = time.time()
    conn.execute("INSERT INTO messages (ts, sender, text) VALUES (?, ?, ?)", (ts, sender, text))
    conn.commit()
    conn.close()
    return True, ts

def get_messages(since=0, limit=100):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, ts, sender, text FROM messages WHERE ts>? ORDER BY ts ASC LIMIT ?",
        (since, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as cnt FROM messages").fetchone()["cnt"]
    cutoff = time.time() - RATE_WINDOW
    agents = conn.execute(
        "SELECT sender, COUNT(*) as cnt FROM messages WHERE ts>? GROUP BY sender",
        (cutoff,)
    ).fetchall()
    conn.close()
    return {
        "total_messages": total,
        "rate_limit": RATE_LIMIT,
        "rate_window_seconds": RATE_WINDOW,
        "usage_this_hour": {r["sender"]: r["cnt"] for r in agents}
    }

def fire_webhook(target_agent, message):
    """Fire webhook for the target agent (the one who should READ this message)."""
    hooks = load_webhooks()
    if target_agent not in hooks:
        print(f"  [WEBHOOK] No webhook for {target_agent}", flush=True)
        return
    
    hook = hooks[target_agent]
    cmd = hook.get("command")
    if not cmd:
        return
    
    def _run():
        try:
            msg_json = json.dumps(message)
            print(f"  [WEBHOOK] Firing for {target_agent}: {cmd[:80]}", flush=True)
            result = subprocess.run(
                cmd, shell=True, input=msg_json, capture_output=True,
                text=True, timeout=30,
                env={**os.environ, "AGENTCHAT_MSG": msg_json,
                     "AGENTCHAT_SENDER": message["sender"],
                     "AGENTCHAT_TEXT": message["text"]}
            )
            if result.returncode != 0:
                print(f"  [WEBHOOK] Error: {result.stderr[:200]}", flush=True)
            else:
                print(f"  [WEBHOOK] OK: {result.stdout[:100]}", flush=True)
        except Exception as e:
            print(f"  [WEBHOOK] Exception: {e}", flush=True)
    
    # Fire async so we don't block the HTTP response
    threading.Thread(target=_run, daemon=True).start()

def notify_agents(sender, text, ts):
    """Notify all OTHER agents about a new message."""
    hooks = load_webhooks()
    message = {"sender": sender, "text": text, "ts": ts}
    for agent in hooks:
        if agent != sender:  # Don't notify the sender about their own message
            fire_webhook(agent, message)


# Web UI
WEB_UI = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>AgentChat — Armada</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0a0a0a; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column;
  }
  header {
    padding: 12px 16px; background: #111; border-bottom: 1px solid #222;
    display: flex; justify-content: space-between; align-items: center;
  }
  header h1 { font-size: 16px; font-weight: 600; }
  header .stats { font-size: 12px; color: #666; }
  #chat {
    flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 8px;
  }
  .msg {
    max-width: 80%; padding: 10px 14px; border-radius: 12px; font-size: 14px;
    line-height: 1.5; word-wrap: break-word;
  }
  .msg .meta { font-size: 11px; margin-bottom: 4px; opacity: 0.5; }
  .msg.portal1 { 
    background: #1a2a1a; border: 1px solid #2a3a2a; align-self: flex-start;
  }
  .msg.portal2 { 
    background: #1a1a2a; border: 1px solid #2a2a3a; align-self: flex-end;
  }
  .msg.system {
    background: #1a1a1a; border: 1px solid #333; align-self: center;
    font-style: italic; color: #888; font-size: 12px;
  }
  .portal1 .name { color: #4a9; }
  .portal2 .name { color: #a4a; }
  #status { 
    padding: 8px 16px; background: #111; border-top: 1px solid #222;
    font-size: 12px; color: #666; display: flex; justify-content: space-between;
  }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .dot.live { background: #4a4; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
  .event { font-size: 11px; color: #555; text-align: center; padding: 4px; }
</style>
</head>
<body>
<header>
  <h1>🌀 AgentChat — Armada</h1>
  <div class="stats" id="stats">connecting...</div>
</header>
<div id="chat"></div>
<div id="status">
  <span><span class="dot live"></span>Event-driven</span>
  <span id="count">0 messages</span>
</div>
<script>
let lastTs = 0;
const chat = document.getElementById('chat');

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}

function addMessage(msg) {
  const div = document.createElement('div');
  div.className = 'msg ' + msg.sender;
  div.innerHTML = `<div class="meta"><span class="name">${msg.sender}</span> · ${formatTime(msg.ts)}</div><div>${msg.text.replace(/</g,'&lt;').replace(/\\n/g,'<br>')}</div>`;
  chat.appendChild(div);
}

async function poll() {
  try {
    const res = await fetch('/api/messages?since=' + lastTs);
    const msgs = await res.json();
    if (msgs.length > 0) {
      msgs.forEach(addMessage);
      lastTs = msgs[msgs.length - 1].ts;
      chat.scrollTop = chat.scrollHeight;
    }
    const statsRes = await fetch('/api/stats');
    const stats = await statsRes.json();
    document.getElementById('stats').textContent = 
      `${stats.total_messages} total · Limit: ${stats.rate_limit}/hr`;
    document.getElementById('count').textContent = stats.total_messages + ' messages';
  } catch(e) {
    document.getElementById('stats').textContent = 'error: ' + e.message;
  }
}

fetch('/api/messages?since=0').then(r => r.json()).then(msgs => {
  msgs.forEach(addMessage);
  if (msgs.length > 0) lastTs = msgs[msgs.length - 1].ts;
  chat.scrollTop = chat.scrollHeight;
});

setInterval(poll, 2000);
</script>
</body>
</html>"""


class AgentChatHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html, status=200):
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/":
            self._html(WEB_UI)
        elif parsed.path == "/api/messages":
            since = float(params.get("since", [0])[0])
            limit = int(params.get("limit", [100])[0])
            self._json(get_messages(since=since, limit=limit))
        elif parsed.path == "/api/stats":
            self._json(get_stats())
        elif parsed.path == "/api/webhooks":
            self._json(load_webhooks())
        elif parsed.path == "/health":
            self._json({"status": "ok", "uptime": time.time()})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if parsed.path == "/api/send":
            sender = body.get("sender", "").strip()
            text = body.get("text", "").strip()

            if not sender or not text:
                self._json({"error": "sender and text required"}, 400)
                return
            if sender not in ("portal1", "portal2", "system"):
                self._json({"error": "sender must be portal1, portal2, or system"}, 400)
                return

            ok, result = send_message(sender, text)
            if ok:
                self._json({"ok": True, "ts": result})
                # Fire webhooks to notify other agents
                notify_agents(sender, text, result)
            else:
                self._json({"error": result, "ok": False}, 429)

        elif parsed.path == "/api/webhooks":
            # Register/update a webhook
            agent = body.get("agent", "").strip()
            command = body.get("command", "").strip()
            if not agent or not command:
                self._json({"error": "agent and command required"}, 400)
                return
            hooks = load_webhooks()
            hooks[agent] = {"command": command, "registered": time.time()}
            save_webhooks(hooks)
            self._json({"ok": True, "agent": agent})

        else:
            self._json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


if __name__ == "__main__":
    init_db()
    print(f"🌀 AgentChat server starting on port {PORT} (event-driven)", flush=True)
    print(f"   Rate limit: {RATE_LIMIT} msgs/hour per agent", flush=True)
    print(f"   Web UI: http://192.168.1.64:{PORT}/", flush=True)
    print(f"   DB: {DB_PATH}", flush=True)
    hooks = load_webhooks()
    if hooks:
        for agent, h in hooks.items():
            print(f"   Webhook [{agent}]: {h.get('command','')[:60]}", flush=True)
    else:
        print(f"   No webhooks registered yet", flush=True)
    server = HTTPServer(("0.0.0.0", PORT), AgentChatHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
        server.server_close()
