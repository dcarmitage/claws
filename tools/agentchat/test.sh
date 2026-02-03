#!/bin/bash
# AgentChat V2 Test Suite
# Run: ./test.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔═══════════════════════════════════════════╗"
echo "║      AgentChat V2 Test Suite              ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

# Check if server is running
if ! curl -s http://localhost:9090/health > /dev/null 2>&1; then
    echo "⚠️  Server not running. Starting..."
    python3 server.py > /tmp/agentchat_test.log 2>&1 &
    SERVER_PID=$!
    sleep 3
    
    if ! curl -s http://localhost:9090/health > /dev/null 2>&1; then
        echo "❌ Failed to start server"
        cat /tmp/agentchat_test.log
        exit 1
    fi
    echo "✅ Server started (PID: $SERVER_PID)"
    STARTED_SERVER=1
else
    echo "✅ Server already running"
    STARTED_SERVER=0
fi

# Run tests
echo ""
python3 tests/test_api.py
TEST_EXIT=$?

# Cleanup
if [ "$STARTED_SERVER" = "1" ]; then
    echo ""
    echo "Stopping test server..."
    kill $SERVER_PID 2>/dev/null || true
fi

exit $TEST_EXIT
