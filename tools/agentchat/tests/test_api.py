#!/usr/bin/env python3
"""
AgentChat V2 Test Suite
Run: python3 tests/test_api.py
Or:  ./test.sh
"""

import json
import sys
import time
import urllib.request
import urllib.error
from typing import Optional

BASE_URL = "http://localhost:9090"
RESULTS = {"passed": 0, "failed": 0, "skipped": 0}

def log(msg: str, status: str = ""):
    icons = {"pass": "✅", "fail": "❌", "skip": "⏭️", "info": "ℹ️"}
    icon = icons.get(status, "")
    print(f"{icon} {msg}")

def api(method: str, path: str, data: Optional[dict] = None) -> tuple:
    """Make API request, return (status_code, response_data)"""
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    
    try:
        if data:
            req = urllib.request.Request(url, json.dumps(data).encode(), headers, method=method)
        else:
            req = urllib.request.Request(url, method=method)
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode()) if resp.read else {}
            # Re-read for actual response
            resp = urllib.request.urlopen(req, timeout=5)
            body = json.loads(resp.read().decode())
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except:
            body = {"error": str(e)}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}

def get(path: str) -> tuple:
    url = f"{BASE_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}

def post(path: str, data: dict) -> tuple:
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, json.dumps(data).encode(), headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except:
            body = {"error": str(e)}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}

def test(name: str, condition: bool, details: str = ""):
    if condition:
        RESULTS["passed"] += 1
        log(f"{name}", "pass")
    else:
        RESULTS["failed"] += 1
        log(f"{name}: {details}", "fail")
    return condition

def skip(name: str, reason: str = ""):
    RESULTS["skipped"] += 1
    log(f"{name}: {reason}", "skip")

# ============ Tests ============

def test_health():
    """Test server health endpoint"""
    code, data = get("/health")
    test("Health endpoint returns 200", code == 200)
    test("Health status is ok", data.get("status") == "ok")
    test("Health reports version 2.0", data.get("version") == "2.0")
    test("Health reports WebSocket port", data.get("websocket_port") == 9091)

def test_agents():
    """Test agents API"""
    code, agents = get("/api/v2/agents")
    test("GET /api/v2/agents returns 200", code == 200)
    test("Agents is a list", isinstance(agents, list))
    test("At least 2 agents exist", len(agents) >= 2)
    
    # Check agent structure
    if agents:
        agent = agents[0]
        test("Agent has id", "id" in agent)
        test("Agent has name", "name" in agent)
        test("Agent has status", "status" in agent)
    
    # Test single agent
    code, agent = get("/api/v2/agents/portal1")
    test("GET /api/v2/agents/portal1 returns 200", code == 200)
    test("Portal1 agent exists", agent.get("name") == "Portal1")

def test_heartbeat():
    """Test heartbeat/presence"""
    code, result = post("/api/v2/agents/portal1/heartbeat", {
        "status": "online",
        "status_message": "Running tests"
    })
    test("POST heartbeat returns 200", code == 200)
    test("Heartbeat returns ok", result.get("ok") == True)
    
    # Verify status updated
    code, agent = get("/api/v2/agents/portal1")
    test("Agent status updated", agent.get("status") == "online")
    test("Agent status_message updated", agent.get("status_message") == "Running tests")

def test_channels():
    """Test channels API"""
    code, channels = get("/api/v2/channels")
    test("GET /api/v2/channels returns 200", code == 200)
    test("Channels is a list", isinstance(channels, list))
    test("At least 1 channel exists", len(channels) >= 1)
    
    # Check channel structure
    if channels:
        ch = channels[0]
        test("Channel has id", "id" in ch)
        test("Channel has name", "name" in ch)
        test("Channel has topic", "topic" in ch)

def test_messages():
    """Test messages API"""
    # Get messages from general
    code, messages = get("/api/v2/channels/general/messages?limit=5")
    test("GET messages returns 200", code == 200)
    test("Messages is a list", isinstance(messages, list))
    
    # Post a test message
    test_content = f"Test message at {int(time.time())}"
    code, msg = post("/api/v2/channels/general/messages", {
        "sender_id": "portal1",
        "content": test_content
    })
    test("POST message returns 200", code == 200)
    test("Message has id", "id" in msg)
    test("Message content matches", msg.get("content") == test_content)
    test("Message has sender_name", "sender_name" in msg)
    test("Message has created_at", "created_at" in msg)

def test_mentions():
    """Test @mention creates notification"""
    # Post message with mention
    code, msg = post("/api/v2/channels/general/messages", {
        "sender_id": "portal1",
        "content": "@Portal2 this is a test mention"
    })
    test("Mention message posted", code == 200)
    
    # Check Portal2 notifications
    code, notifs = get("/api/v2/agents/portal2/notifications")
    test("GET notifications returns 200", code == 200)
    
    # Find our notification
    has_notif = any("test mention" in n.get("content", "") for n in notifs)
    test("Mention created notification", has_notif)

def test_tasks():
    """Test tasks API"""
    # Create task
    code, task = post("/api/v2/tasks", {
        "title": f"Test task {int(time.time())}",
        "description": "Created by test suite",
        "priority": 2,
        "created_by": "portal1"
    })
    test("POST task returns 200", code == 200)
    test("Task has id", "id" in task)
    test("Task status is inbox", task.get("status") == "inbox")
    
    task_id = task.get("id")
    
    # Get tasks
    code, tasks = get("/api/v2/tasks")
    test("GET tasks returns 200", code == 200)
    test("Tasks is a list", isinstance(tasks, list))
    
    # Update status
    if task_id:
        code, result = post(f"/api/v2/tasks/{task_id}/status", {"status": "in_progress"})
        test("Update task status returns 200", code == 200)
        test("Task status updated", result.get("status") == "in_progress")

def test_task_assignment():
    """Test task assignment creates notification"""
    code, task = post("/api/v2/tasks", {
        "title": f"Assignment test {int(time.time())}",
        "created_by": "portal1",
        "assignees": ["portal2"]
    })
    test("Task with assignee created", code == 200)
    
    # Check Portal2 notifications for assignment
    code, notifs = get("/api/v2/agents/portal2/notifications")
    has_assignment = any(n.get("type") == "assignment" for n in notifs)
    test("Assignment created notification", has_assignment)

def test_v1_compat():
    """Test v1 API compatibility"""
    # GET /api/messages (v1)
    code, messages = get("/api/messages")
    test("V1 GET /api/messages works", code == 200)
    test("V1 messages is a list", isinstance(messages, list))
    
    # POST /api/send (v1)
    code, result = post("/api/send", {
        "sender": "portal1",
        "text": "V1 compat test"
    })
    test("V1 POST /api/send works", code == 200)

def test_dashboard():
    """Test dashboard serves HTML"""
    try:
        with urllib.request.urlopen(f"{BASE_URL}/", timeout=5) as resp:
            content = resp.read().decode()
            test("Dashboard returns 200", resp.status == 200)
            test("Dashboard is HTML", "<!DOCTYPE html>" in content)
            test("Dashboard has title", "AgentChat V2" in content)
    except Exception as e:
        test("Dashboard accessible", False, str(e))

# ============ Main ============

def run_tests():
    print("=" * 50)
    print("AgentChat V2 Test Suite")
    print("=" * 50)
    print()
    
    # Check server is running
    try:
        urllib.request.urlopen(f"{BASE_URL}/health", timeout=2)
    except:
        print("❌ Server not running at", BASE_URL)
        print("   Start with: python3 server.py")
        sys.exit(1)
    
    print("🔍 Running tests against", BASE_URL)
    print()
    
    # Run test suites
    suites = [
        ("Health", test_health),
        ("Agents", test_agents),
        ("Heartbeat", test_heartbeat),
        ("Channels", test_channels),
        ("Messages", test_messages),
        ("Mentions", test_mentions),
        ("Tasks", test_tasks),
        ("Task Assignment", test_task_assignment),
        ("V1 Compatibility", test_v1_compat),
        ("Dashboard", test_dashboard),
    ]
    
    for name, fn in suites:
        print(f"\n--- {name} ---")
        try:
            fn()
        except Exception as e:
            log(f"Suite error: {e}", "fail")
            RESULTS["failed"] += 1
    
    # Summary
    print()
    print("=" * 50)
    total = RESULTS["passed"] + RESULTS["failed"] + RESULTS["skipped"]
    print(f"Results: {RESULTS['passed']}/{total} passed", end="")
    if RESULTS["failed"]:
        print(f", {RESULTS['failed']} failed", end="")
    if RESULTS["skipped"]:
        print(f", {RESULTS['skipped']} skipped", end="")
    print()
    
    if RESULTS["failed"] == 0:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
