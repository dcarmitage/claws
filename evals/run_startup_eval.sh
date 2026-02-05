#!/usr/bin/env bash
# Startup Fitness Eval — retrieval-based checks for session readiness.
# Verifies key memory files are accessible and contain expected content.
# Exit 0 = fit, exit 1 = not fit.

set -euo pipefail

CLAWD_HOME="/home/clawd"
ERRORS=()
WARNINGS=()

check_file_exists() {
    local path="$1"
    local label="$2"
    if [[ -f "$path" ]]; then
        echo "  [OK] $label exists"
    else
        echo "  [FAIL] $label missing: $path"
        ERRORS+=("$label missing")
    fi
}

check_file_has_content() {
    local path="$1"
    local label="$2"
    if [[ -f "$path" && -s "$path" ]]; then
        echo "  [OK] $label has content"
    elif [[ -f "$path" ]]; then
        echo "  [WARN] $label exists but is empty"
        WARNINGS+=("$label empty")
    else
        echo "  [FAIL] $label missing"
        ERRORS+=("$label missing")
    fi
}

check_grep_pattern() {
    local path="$1"
    local pattern="$2"
    local label="$3"
    if [[ -f "$path" ]] && grep -q "$pattern" "$path" 2>/dev/null; then
        echo "  [OK] $label: pattern found"
    else
        echo "  [WARN] $label: pattern '$pattern' not found in $path"
        WARNINGS+=("$label pattern missing")
    fi
}

echo "=== Startup Fitness Evaluation ==="
echo ""

# Memory file checks
echo "-- Memory Files --"
check_file_has_content "$CLAWD_HOME/MEMORY.md" "MEMORY.md"
check_file_has_content "$CLAWD_HOME/LEARN.md" "LEARN.md"

TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d 2>/dev/null || echo "")
check_file_exists "$CLAWD_HOME/memory/$TODAY.md" "Today's memory ($TODAY)"
if [[ -n "$YESTERDAY" ]]; then
    if [[ -f "$CLAWD_HOME/memory/$YESTERDAY.md" ]]; then
        echo "  [OK] Yesterday's memory ($YESTERDAY) exists"
    else
        echo "  [INFO] Yesterday's memory ($YESTERDAY) not found (may be expected)"
    fi
fi

echo ""

# Key pattern retrieval checks
echo "-- Retrieval Checks --"
check_grep_pattern "$CLAWD_HOME/MEMORY.md" "status\|state\|current\|active" "MEMORY.md system status"
check_grep_pattern "$CLAWD_HOME/LEARN.md" "lesson\|learned\|insight\|pattern" "LEARN.md lesson entries"

echo ""

# Orchestrator files
echo "-- Orchestrator Files --"
check_file_has_content "$CLAWD_HOME/systems/orchestrator/HEURISTICS.md" "HEURISTICS.md"
check_file_has_content "$CLAWD_HOME/systems/orchestrator/CHECKLISTS.md" "CHECKLISTS.md"

echo ""

# Git access check
echo "-- Git Access --"
if git -C "$CLAWD_HOME" log --oneline -1 >/dev/null 2>&1; then
    LATEST_COMMIT=$(git -C "$CLAWD_HOME" log --oneline -1)
    echo "  [OK] Git accessible. Latest: $LATEST_COMMIT"
else
    echo "  [WARN] Git not accessible or no commits"
    WARNINGS+=("Git not accessible")
fi

echo ""

# Service health checks (subset)
echo "-- Service Health --"
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:18789/v1/models" 2>/dev/null | grep -q "200"; then
    echo "  [OK] OpenClaw gateway responding"
else
    echo "  [WARN] OpenClaw gateway not responding (judges will not work)"
    WARNINGS+=("OpenClaw not responding")
fi

echo ""

# Summary
echo "=== Summary ==="
echo "Errors: ${#ERRORS[@]}"
echo "Warnings: ${#WARNINGS[@]}"

if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo ""
    echo "ERRORS (must fix):"
    for err in "${ERRORS[@]}"; do
        echo "  - $err"
    done
fi

if [[ ${#WARNINGS[@]} -gt 0 ]]; then
    echo ""
    echo "WARNINGS (should investigate):"
    for warn in "${WARNINGS[@]}"; do
        echo "  - $warn"
    done
fi

if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo ""
    echo "RESULT: NOT FIT (${#ERRORS[@]} errors)"
    exit 1
else
    echo ""
    echo "RESULT: FIT (${#WARNINGS[@]} warnings)"
    exit 0
fi
