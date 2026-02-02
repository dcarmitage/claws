#!/usr/bin/env python3
"""
AgentChat Poller — checks for new messages and writes them to a trigger file.
Designed to run as a systemd service alongside the AgentChat server.
When a new message from the watched agent arrives, it writes to a trigger file
that Clawdbot's cron/heartbeat can pick up.
"""

import json
import time
import os
import sys
import urllib.request
import urllib.error

AGENT = os.environ.get("AGENT", "portal1")
WATCH = os.environ.get("WATCH", "portal2")
SERVER = os.environ.get("SERVER", "http://192.168.1.64:9090")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
STATE_FILE = f"/tmp/agentchat-poller-{AGENT}.state"
TRIGGER_FILE = os.environ.get("TRIGGER_FILE", "/home/clawd/tools/agentchat/inbox.json")

def load_last_ts():
    try:
        with open(STATE_FILE) as f:
            return float(f.read().strip())
    except:
        return time.time()

def save_last_ts(ts):
    with open(STATE_FILE, "w") as f:
        f.write(str(ts))

def poll_messages(since):
    url = f"{SERVER}/api/messages?since={since}&limit=20"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  [ERR] Poll failed: {e}", flush=True)
        return []

def write_trigger(messages):
    """Write pending messages to inbox file for Clawdbot to pick up."""
    # Read existing inbox
    existing = []
    try:
        with open(TRIGGER_FILE) as f:
            existing = json.loads(f.read())
    except:
        pass
    
    existing.extend(messages)
    
    with open(TRIGGER_FILE, "w") as f:
        json.dump(existing, f, indent=2)

def clear_inbox():
    """Called after messages are processed."""
    with open(TRIGGER_FILE, "w") as f:
        json.dump([], f)

def main():
    last_ts = load_last_ts()
    print(f"🌀 AgentChat poller starting", flush=True)
    print(f"   Agent: {AGENT} | Watching: {WATCH}", flush=True)
    print(f"   Server: {SERVER} | Poll: {POLL_INTERVAL}s", flush=True)
    
    while True:
        msgs = poll_messages(last_ts)
        
        # Filter for messages from the watched agent
        new_msgs = [m for m in msgs if m["sender"] == WATCH]
        
        if new_msgs:
            for m in new_msgs:
                ts_str = time.strftime("%H:%M:%S", time.localtime(m["ts"]))
                print(f"  [{ts_str}] {WATCH}: {m['text'][:80]}", flush=True)
            
            write_trigger(new_msgs)
        
        # Update last_ts to latest message (any sender)
        if msgs:
            last_ts = msgs[-1]["ts"]
            save_last_ts(last_ts)
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
