#!/usr/bin/env python3
"""
AgentChat V2 End-to-End Test
Tests that agents can actually wake up and respond via their plugins.

This catches failures that API tests miss:
- Plugin can't poll (network/DNS issues)
- Plugin can't connect to gateway WebSocket (IPv4/IPv6 mismatch)
- Plugin processes message but can't post reply
- Agent responds but with NO_REPLY

Run: python3 tests/test_e2e.py
"""

import json
import sys
import time
import urllib.request

BASE_URL = "http://localhost:9090"
TIMEOUT_SECONDS = 30
POLL_INTERVAL = 2

def get(path):
    try:
        with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except Exception as e:
        return 0, {"error": str(e)}

def post(path, data):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        json.dumps(data).encode(),
        {"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except Exception as e:
        return 0, {"error": str(e)}

def test_portal2_responds():
    """E2E: Post message as portal1, verify portal2 responds within timeout"""
    print("=" * 60)
    print("E2E Test: Portal2 responds to Portal1")
    print("=" * 60)
    
    # Unique marker to identify our test message
    marker = f"E2E-{int(time.time())}"
    test_content = f"@portal2 E2E test {marker} - reply with just: 42"
    
    print(f"1. Posting test message to #builds: {test_content[:50]}...")
    code, msg = post("/api/v2/channels/builds/messages", {
        "sender_id": "portal1",
        "content": test_content
    })
    
    if code != 200 or not msg.get("id"):
        print(f"❌ FAIL: Could not post test message: {msg}")
        return False
    
    post_time = msg.get("created_at", int(time.time()))
    print(f"   Posted at {post_time}, id: {msg.get('id')}")
    
    # Poll for response
    print(f"2. Waiting up to {TIMEOUT_SECONDS}s for Portal2 response...")
    start = time.time()
    
    while time.time() - start < TIMEOUT_SECONDS:
        code, result = get(f"/api/v2/channels/builds/messages?limit=20")
        if code != 200:
            print(f"   Poll failed: {result}")
            time.sleep(POLL_INTERVAL)
            continue
        
        messages = result.get("messages", result)
        
        # Look for Portal2 response after our post
        for m in messages:
            if (m.get("sender_id") == "portal2" and 
                m.get("created_at", 0) > post_time and
                "42" in m.get("content", "")):
                
                elapsed = time.time() - start
                print(f"✅ PASS: Portal2 responded in {elapsed:.1f}s")
                print(f"   Response: {m.get('content', '')[:80]}...")
                return True
        
        # Check for ACK-only response (indicates plugin bug)
        for m in messages:
            if (m.get("sender_id") == "portal2" and 
                m.get("created_at", 0) > post_time):
                content = m.get("content", "")
                if content.startswith("ACK") or content.startswith("[Portal2]"):
                    print(f"⚠️  Got response but not expected content: {content[:60]}...")
        
        elapsed = time.time() - start
        print(f"   Waiting... ({elapsed:.0f}s)")
        time.sleep(POLL_INTERVAL)
    
    print(f"❌ FAIL: No response from Portal2 after {TIMEOUT_SECONDS}s")
    print("   This indicates the plugin is not processing messages properly.")
    print("   Check: /tmp/openclaw/openclaw-*.log for [AC-V2] errors")
    return False

def test_portal1_responds():
    """E2E: Post message as portal2, verify portal1 responds within timeout"""
    print()
    print("=" * 60)
    print("E2E Test: Portal1 responds to Portal2")
    print("=" * 60)
    
    marker = f"E2E-{int(time.time())}"
    test_content = f"@portal1 E2E test {marker} - reply with just: 42"
    
    print(f"1. Posting test message to #builds: {test_content[:50]}...")
    code, msg = post("/api/v2/channels/builds/messages", {
        "sender_id": "portal2",
        "content": test_content
    })
    
    if code != 200 or not msg.get("id"):
        print(f"❌ FAIL: Could not post test message: {msg}")
        return False
    
    post_time = msg.get("created_at", int(time.time()))
    print(f"   Posted at {post_time}, id: {msg.get('id')}")
    
    print(f"2. Waiting up to {TIMEOUT_SECONDS}s for Portal1 response...")
    start = time.time()
    
    while time.time() - start < TIMEOUT_SECONDS:
        code, result = get(f"/api/v2/channels/builds/messages?limit=20")
        if code != 200:
            time.sleep(POLL_INTERVAL)
            continue
        
        messages = result.get("messages", result)
        
        for m in messages:
            if (m.get("sender_id") == "portal1" and 
                m.get("created_at", 0) > post_time and
                "42" in m.get("content", "")):
                
                elapsed = time.time() - start
                print(f"✅ PASS: Portal1 responded in {elapsed:.1f}s")
                print(f"   Response: {m.get('content', '')[:80]}...")
                return True
        
        elapsed = time.time() - start
        print(f"   Waiting... ({elapsed:.0f}s)")
        time.sleep(POLL_INTERVAL)
    
    print(f"❌ FAIL: No response from Portal1 after {TIMEOUT_SECONDS}s")
    return False

def test_plugin_health():
    """Verify both agents show recent heartbeat (plugin is running)"""
    print()
    print("=" * 60)
    print("Plugin Health Check")
    print("=" * 60)
    
    code, agents = get("/api/v2/agents")
    if code != 200:
        print(f"❌ FAIL: Could not fetch agents: {agents}")
        return False
    
    now = int(time.time())
    all_healthy = True
    
    for agent in agents:
        agent_id = agent.get("id")
        last_hb = agent.get("last_heartbeat", 0)
        age = now - last_hb if last_hb else float('inf')
        status = agent.get("status", "unknown")
        
        # Consider healthy if heartbeat within last 5 minutes
        healthy = age < 300
        icon = "✅" if healthy else "❌"
        
        print(f"{icon} {agent_id}: status={status}, heartbeat {age:.0f}s ago")
        
        if not healthy:
            all_healthy = False
            print(f"   ⚠️  Heartbeat stale - plugin may not be running")
    
    return all_healthy

def main():
    print("AgentChat V2 End-to-End Test Suite")
    print("=" * 60)
    
    # Check server is running
    code, health = get("/health")
    if code != 200:
        print(f"❌ Server not running at {BASE_URL}")
        return 1
    print(f"✅ Server healthy: {health}")
    
    results = []
    
    # Run tests
    results.append(("Plugin Health", test_plugin_health()))
    results.append(("Portal1 Responds", test_portal1_responds()))
    # Uncomment to also test Portal2 (requires Portal2 to be running)
    # results.append(("Portal2 Responds", test_portal2_responds()))
    
    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        icon = "✅" if result else "❌"
        print(f"{icon} {name}")
    
    print()
    if passed == total:
        print(f"✅ All {total} tests passed!")
        return 0
    else:
        print(f"❌ {total - passed}/{total} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
