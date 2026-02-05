#!/usr/bin/env python3
"""
AgentChat Poller V2 — uses compound cursor (ts:id) for deterministic pagination.
Polls V2 API endpoints and properly handles next_since cursor.
"""

import json
import time
import os
import sys
import urllib.request
import urllib.error

AGENT = os.environ.get("AGENT", "portal1")
CHANNELS = os.environ.get("CHANNELS", "general,builds").split(",")
SERVER = os.environ.get("SERVER", "http://192.168.1.64:9090")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
STATE_FILE = f"/tmp/agentchat-poller-v2-{AGENT}.state"
TRIGGER_FILE = os.environ.get("TRIGGER_FILE", "/home/clawd/tools/agentchat/inbox.json")

def load_cursors():
    """Load cursor state - dict of channel_id -> next_since string"""
    try:
        with open(STATE_FILE) as f:
            return json.loads(f.read())
    except:
        return {}

def save_cursors(cursors):
    """Save cursor state verbatim (compound cursor strings)"""
    with open(STATE_FILE, "w") as f:
        json.dump(cursors, f, indent=2)

def poll_channel(channel_id, since_cursor=None):
    """
    Poll a V2 channel endpoint.
    Returns (messages, next_since) tuple.
    """
    url = f"{SERVER}/api/v2/channels/{channel_id}/messages?limit=50"
    if since_cursor:
        url += f"&since={since_cursor}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get('messages', []), data.get('next_since')
    except Exception as e:
        print(f"  [ERR] Poll {channel_id} failed: {e}", flush=True)
        return [], None

def write_trigger(messages):
    """Write pending messages to inbox file for processing."""
    if not messages:
        return
    
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

def main():
    cursors = load_cursors()
    print(f"🌀 AgentChat Poller V2 starting", flush=True)
    print(f"   Agent: {AGENT}", flush=True)
    print(f"   Channels: {CHANNELS}", flush=True)
    print(f"   Server: {SERVER} | Poll: {POLL_INTERVAL}s", flush=True)
    print(f"   Loaded cursors: {cursors}", flush=True)
    
    while True:
        all_new_msgs = []
        
        for channel in CHANNELS:
            cursor = cursors.get(channel)
            messages, next_since = poll_channel(channel, cursor)
            
            # Filter out own messages
            new_msgs = [m for m in messages if m.get('sender_id') != AGENT]
            
            if new_msgs:
                for m in new_msgs:
                    ts = m.get('created_at', 0)
                    ts_str = time.strftime("%H:%M:%S", time.localtime(ts))
                    sender = m.get('sender_name', m.get('sender_id', '?'))
                    content = m.get('content', '')[:80]
                    print(f"  [{ts_str}] #{channel} {sender}: {content}", flush=True)
                
                all_new_msgs.extend(new_msgs)
            
            # Update cursor ONLY if we got a new one
            if next_since:
                cursors[channel] = next_since
        
        # Save cursors after each poll cycle
        save_cursors(cursors)
        
        # Write any new messages to trigger file
        if all_new_msgs:
            write_trigger(all_new_msgs)
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
