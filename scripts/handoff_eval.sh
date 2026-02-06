#!/usr/bin/env bash
# Session Handoff Gate — checks structural readiness before a session can proceed.
# Verifies required files exist and git is accessible.
# Exit 0 = ready, exit 1 = not ready.

set -euo pipefail

CLAWD_HOME="$CLAWS_HOME"
ERRORS=()

check_exists() {
    local path="$1"
    local label="$2"
    if [[ -f "$path" ]]; then
        echo "  [OK] $label"
    else
        echo "  [MISSING] $label: $path"
        ERRORS+=("$label")
    fi
}

echo "=== Session Handoff Evaluation ==="
echo ""

# Structure checks
echo "-- Required Files --"
check_exists "$CLAWD_HOME/MEMORY.md" "MEMORY.md"
check_exists "$CLAWD_HOME/LEARN.md" "LEARN.md"
check_exists "$CLAWD_HOME/systems/orchestrator/HEURISTICS.md" "HEURISTICS.md"
check_exists "$CLAWD_HOME/systems/orchestrator/CHECKLISTS.md" "CHECKLISTS.md"

TODAY=$(date +%Y-%m-%d)
check_exists "$CLAWD_HOME/memory/$TODAY.md" "Today's memory ($TODAY)"

echo ""

# QMD check (optional — only fail if QMD is installed but index missing)
echo "-- QMD Index --"
if command -v qmd >/dev/null 2>&1; then
    if [[ -d "$CLAWD_HOME/.qmd" ]]; then
        echo "  [OK] QMD index present"
    else
        echo "  [WARN] QMD installed but no index found"
    fi
else
    echo "  [SKIP] QMD not installed"
fi

echo ""

# Git checks
echo "-- Git Access --"
if git -C "$CLAWD_HOME" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "  [OK] Inside git repo"

    # Check working tree state
    DIRTY=$(git -C "$CLAWD_HOME" status --porcelain 2>/dev/null | head -5)
    if [[ -n "$DIRTY" ]]; then
        COUNT=$(git -C "$CLAWD_HOME" status --porcelain 2>/dev/null | wc -l)
        echo "  [WARN] Working tree has $COUNT uncommitted changes"
    else
        echo "  [OK] Working tree clean"
    fi
else
    echo "  [FAIL] Not a git repository"
    ERRORS+=("Git not accessible")
fi

echo ""

# Summary
echo "=== Result ==="
if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo "NOT READY (${#ERRORS[@]} issues):"
    for err in "${ERRORS[@]}"; do
        echo "  - $err"
    done
    exit 1
else
    echo "READY"
    exit 0
fi
