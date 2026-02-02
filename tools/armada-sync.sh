#!/bin/bash
# armada-sync.sh — Armada sync — shared files between Portal1 and Portal2
# Usage: ./armada-sync.sh push|pull [file]
#   push = Portal1 → Portal2
#   pull = Portal2 → Portal1
#   file = optional specific file (default: LEARN.md)

ACTION="${1:-push}"
FILE="${2:-LEARN.md}"

PORTAL1_HOME="/home/clawd"
PORTAL2_HOST="dcarmitage@192.168.1.44"
PORTAL2_HOME="/home/dcarmitage"

case "$ACTION" in
  push)
    echo "📤 Pushing $FILE: Portal1 → Portal2"
    scp "$PORTAL1_HOME/$FILE" "$PORTAL2_HOST:$PORTAL2_HOME/$FILE"
    if [ $? -eq 0 ]; then
      echo "✅ Synced $FILE to Portal2"
    else
      echo "❌ Failed to sync $FILE"
      exit 1
    fi
    ;;
  pull)
    echo "📥 Pulling $FILE: Portal2 → Portal1"
    scp "$PORTAL2_HOST:$PORTAL2_HOME/$FILE" "$PORTAL1_HOME/$FILE"
    if [ $? -eq 0 ]; then
      echo "✅ Synced $FILE from Portal2"
    else
      echo "❌ Failed to sync $FILE"
      exit 1
    fi
    ;;
  push-all)
    echo "📤 Pushing shared files: Portal1 → Portal2"
    for f in LEARN.md; do
      scp "$PORTAL1_HOME/$f" "$PORTAL2_HOST:$PORTAL2_HOME/$f" && echo "  ✅ $f" || echo "  ❌ $f"
    done
    ;;
  pull-all)
    echo "📥 Pulling shared files: Portal2 → Portal1"
    for f in LEARN.md; do
      scp "$PORTAL2_HOST:$PORTAL2_HOME/$f" "$PORTAL1_HOME/$f" && echo "  ✅ $f" || echo "  ❌ $f"
    done
    ;;
  status)
    echo "=== Portal1 ==="
    echo "LEARN.md: $(wc -l < $PORTAL1_HOME/LEARN.md) lines, $(stat -c%Y $PORTAL1_HOME/LEARN.md | xargs -I{} date -d @{} '+%Y-%m-%d %H:%M')"
    echo ""
    echo "=== Portal2 ==="
    ssh $PORTAL2_HOST "echo \"LEARN.md: \$(wc -l < $PORTAL2_HOME/LEARN.md) lines, \$(stat -c%Y $PORTAL2_HOME/LEARN.md | xargs -I{} date -d @{} '+%Y-%m-%d %H:%M')\""
    ;;
  *)
    echo "Usage: $0 push|pull|push-all|pull-all|status [file]"
    exit 1
    ;;
esac
