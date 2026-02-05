#!/usr/bin/env python3
import time, requests, sys

BASE = "http://127.0.0.1:9090"
CHAN = "builds"
TIMEOUT_S = 20

# 1) Post deterministic prompt that portal2 must answer
prompt = f"@portal2 E2E test: reply with exactly 42."
r = requests.post(f"{BASE}/api/v2/channels/{CHAN}/messages",
                  json={"sender_id":"portal1","content":prompt}, timeout=3)
r.raise_for_status()
posted = r.json()
start = time.time()

# 2) Poll for a portal2 reply that is NOT an echo/ACK and contains 42
last_seen_ids = set()
while time.time() - start < TIMEOUT_S:
    msgs = requests.get(f"{BASE}/api/v2/channels/{CHAN}/messages?limit=50", timeout=3).json()
    for m in msgs.get("messages", msgs):
        if m["id"] in last_seen_ids:
            continue
        last_seen_ids.add(m["id"])
        if m["sender_id"] == "portal2":
            txt = (m["content"] or "").strip()
            if "ACK" in txt:
                continue
            if txt == "42" or txt.endswith(" 42") or "42" in txt:
                print("PASS: portal2 replied:", txt)
                sys.exit(0)
    time.sleep(1.0)

print("FAIL: no valid portal2 reply within", TIMEOUT_S, "seconds")
print("Posted msg id:", posted.get("id"))
sys.exit(1)
