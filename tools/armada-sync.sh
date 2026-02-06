#!/bin/bash
# armada-sync.sh — Armada sync — shared files between agent-alpha and agent-beta
# Usage: ./armada-sync.sh push|pull [file]
#   push = agent-alpha → agent-beta
#   pull = agent-beta → agent-alpha
#   file = optional specific file (default: LEARN.md)

ACTION="${1:-push}"
FILE="${2:-LEARN.md}"

PORTAL1_HOME="$CLAWS_HOME"
PORTAL2_HOST="your-user@<your-agent-ip>"
PORTAL2_HOME="$HOME"

case "$ACTION" in
  push)
    echo "📤 Pushing $FILE: agent-alpha → agent-beta"
    scp "$PORTAL1_HOME/$FILE" "$PORTAL2_HOST:$PORTAL2_HOME/$FILE"
    if [ $? -eq 0 ]; then
      echo "✅ Synced $FILE to agent-beta"
    else
      echo "❌ Failed to sync $FILE"
      exit 1
    fi
    ;;
  pull)
    echo "📥 Pulling $FILE: agent-beta → agent-alpha"
    scp "$PORTAL2_HOST:$PORTAL2_HOME/$FILE" "$PORTAL1_HOME/$FILE"
    if [ $? -eq 0 ]; then
      echo "✅ Synced $FILE from agent-beta"
    else
      echo "❌ Failed to sync $FILE"
      exit 1
    fi
    ;;
  push-all)
    echo "📤 Pushing shared files: agent-alpha → agent-beta"
    for f in LEARN.md; do
      scp "$PORTAL1_HOME/$f" "$PORTAL2_HOST:$PORTAL2_HOME/$f" && echo "  ✅ $f" || echo "  ❌ $f"
    done
    ;;
  pull-all)
    echo "📥 Pulling shared files: agent-beta → agent-alpha"
    for f in LEARN.md; do
      scp "$PORTAL2_HOST:$PORTAL2_HOME/$f" "$PORTAL1_HOME/$f" && echo "  ✅ $f" || echo "  ❌ $f"
    done
    ;;
  status)
    echo "=== agent-alpha ==="
    echo "LEARN.md: $(wc -l < $PORTAL1_HOME/LEARN.md) lines, $(stat -c%Y $PORTAL1_HOME/LEARN.md | xargs -I{} date -d @{} '+%Y-%m-%d %H:%M')"
    echo ""
    echo "=== agent-beta ==="
    ssh $PORTAL2_HOST "echo \"LEARN.md: \$(wc -l < $PORTAL2_HOME/LEARN.md) lines, \$(stat -c%Y $PORTAL2_HOME/LEARN.md | xargs -I{} date -d @{} '+%Y-%m-%d %H:%M')\""
    ;;
  *)
    echo "Usage: $0 push|pull|push-all|pull-all|status [file]"
    exit 1
    ;;
esac
