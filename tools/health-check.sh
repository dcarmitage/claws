#!/bin/bash
# agent-alpha Boot Health Check
# Run at session start to verify all systems are operational
# Usage: bash tools/health-check.sh

echo "🌀 agent-alpha Health Check"
echo "======================"
PASS=0; FAIL=0; WARN=0

check() {
  if eval "$2" > /dev/null 2>&1; then
    echo "  ✅ $1"
    ((PASS++))
  else
    echo "  ❌ $1"
    ((FAIL++))
  fi
}

warn() {
  if eval "$2" > /dev/null 2>&1; then
    echo "  ✅ $1"
    ((PASS++))
  else
    echo "  ⚠️  $1 (non-critical)"
    ((WARN++))
  fi
}

echo ""
echo "Services:"
check "camservice (port 5080)" "curl -sf http://localhost:5080/health"
check "parakeet STT (port 5092)" "curl -sf http://localhost:5092/health"
check "hailo NPU" "test -e /dev/hailo0"
check "clawdbot gateway" "pgrep -f clawdbot-gateway"

echo ""
echo "Storage:"
check "USB drive mounted (/mnt/media)" "mountpoint -q /mnt/media"
check "SD card space >5GB free" "[ $(df $CLAWS_HOME --output=avail | tail -1) -gt 5000000 ]"
warn "USB drive space >5GB free" "[ $(df /mnt/media --output=avail 2>/dev/null | tail -1) -gt 5000000 ]"

echo ""
echo "Tools:"
check "git repo clean" "cd $CLAWS_HOME && git diff --quiet HEAD 2>/dev/null"
check "QMD installed" "test -f $CLAWS_HOME/tools/qmd/src/qmd.ts"
warn "QMD index exists" "test -f $HOME/.cache/qmd/index.sqlite"
warn "bun available" "which bun || test -f $HOME/.bun/bin/bun"

echo ""
echo "Knowledge:"
check "MEMORY.md exists" "test -f $CLAWS_HOME/MEMORY.md"
check "LEARN.md exists" "test -f $CLAWS_HOME/LEARN.md"
check "Today's memory exists" "test -f $CLAWS_HOME/memory/$(date +%Y-%m-%d).md"

echo ""
echo "======================"
echo "✅ $PASS passed | ❌ $FAIL failed | ⚠️  $WARN warnings"

if [ $FAIL -gt 0 ]; then
  echo "⛔ FIX FAILURES before proceeding"
  exit 1
elif [ $WARN -gt 0 ]; then
  echo "🟡 Ready with warnings"
  exit 0
else
  echo "🟢 All systems go"
  exit 0
fi
