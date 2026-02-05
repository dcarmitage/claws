#!/usr/bin/env bash
# Standardized End-of-Session script — implements H13.
# Reports git state, memory hygiene, build summary, and judge summary.

set -euo pipefail

CLAWD_HOME="/home/clawd"
BUILD_LOG="$CLAWD_HOME/systems/orchestrator/build_log.py"
LOGS_DIR="$CLAWD_HOME/systems/orchestrator/logs"
RESULTS_DIR="$CLAWD_HOME/evals/results"

echo "=== End-of-Session Report ==="
echo ""

# 1. Git status
echo "-- Git Status --"
if git -C "$CLAWD_HOME" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    UNTRACKED=$(git -C "$CLAWD_HOME" ls-files --others --exclude-standard 2>/dev/null | wc -l)
    MODIFIED=$(git -C "$CLAWD_HOME" diff --name-only 2>/dev/null | wc -l)
    STAGED=$(git -C "$CLAWD_HOME" diff --cached --name-only 2>/dev/null | wc -l)

    echo "  Untracked files: $UNTRACKED"
    echo "  Modified files:  $MODIFIED"
    echo "  Staged files:    $STAGED"

    if [[ $UNTRACKED -gt 0 || $MODIFIED -gt 0 ]]; then
        echo ""
        echo "  Uncommitted changes:"
        git -C "$CLAWD_HOME" status --short 2>/dev/null | head -20 | sed 's/^/    /'
        TOTAL=$(git -C "$CLAWD_HOME" status --porcelain 2>/dev/null | wc -l)
        if [[ $TOTAL -gt 20 ]]; then
            echo "    ... and $((TOTAL - 20)) more"
        fi
    else
        echo "  Working tree clean."
    fi
else
    echo "  Not a git repository."
fi

echo ""

# 2. Memory hygiene
echo "-- Memory Hygiene --"
TODAY=$(date +%Y-%m-%d)
TODAY_MEM="$CLAWD_HOME/memory/$TODAY.md"

if [[ -f "$TODAY_MEM" && -s "$TODAY_MEM" ]]; then
    LINES=$(wc -l < "$TODAY_MEM")
    echo "  [OK] Today's memory ($TODAY): $LINES lines"
else
    echo "  [WARN] Today's memory missing or empty: $TODAY_MEM"
fi

if [[ -f "$CLAWD_HOME/MEMORY.md" ]]; then
    MEM_MOD=$(stat -c %Y "$CLAWD_HOME/MEMORY.md" 2>/dev/null || stat -f %m "$CLAWD_HOME/MEMORY.md" 2>/dev/null || echo "0")
    NOW=$(date +%s)
    AGE_HOURS=$(( (NOW - MEM_MOD) / 3600 ))
    if [[ $AGE_HOURS -lt 24 ]]; then
        echo "  [OK] MEMORY.md updated $AGE_HOURS hours ago"
    else
        echo "  [WARN] MEMORY.md last updated $AGE_HOURS hours ago (stale?)"
    fi
else
    echo "  [FAIL] MEMORY.md not found"
fi

echo ""

# 3. Build summary
echo "-- Build Summary --"
if [[ -d "$LOGS_DIR" ]]; then
    LATEST_LOG=$(ls -t "$LOGS_DIR"/*.jsonl 2>/dev/null | head -1)
    if [[ -n "$LATEST_LOG" ]]; then
        BUILD_ID=$(basename "$LATEST_LOG" .jsonl)
        echo "  Latest build: $BUILD_ID"
        python3 "$BUILD_LOG" summary "$BUILD_ID" 2>/dev/null | sed 's/^/  /' || echo "  (could not generate summary)"
    else
        echo "  No builds logged this session."
    fi
else
    echo "  No build logs directory."
fi

echo ""

# 4. Judge summary
echo "-- Judge Evaluation Summary --"
if [[ -d "$RESULTS_DIR" ]]; then
    RESULT_FILES=("$RESULTS_DIR"/*.json)
    if [[ -e "${RESULT_FILES[0]}" ]]; then
        TOTAL_EVALS=${#RESULT_FILES[@]}
        PASSED=0
        LOGIC_SUM=0
        CONSISTENCY_SUM=0

        for f in "${RESULT_FILES[@]}"; do
            if [[ -f "$f" ]]; then
                OP=$(jq -r '.overall_passed // false' "$f" 2>/dev/null)
                if [[ "$OP" == "true" ]]; then
                    PASSED=$((PASSED + 1))
                fi
                LS=$(jq -r '.logic_judge.score // 0' "$f" 2>/dev/null)
                CS=$(jq -r '.consistency_judge.score // 0' "$f" 2>/dev/null)
                LOGIC_SUM=$(echo "$LOGIC_SUM + $LS" | bc -l)
                CONSISTENCY_SUM=$(echo "$CONSISTENCY_SUM + $CS" | bc -l)
            fi
        done

        if [[ $TOTAL_EVALS -gt 0 ]]; then
            AVG_LOGIC=$(echo "scale=1; $LOGIC_SUM / $TOTAL_EVALS" | bc -l)
            AVG_CONSISTENCY=$(echo "scale=1; $CONSISTENCY_SUM / $TOTAL_EVALS" | bc -l)
            echo "  Total evaluations: $TOTAL_EVALS"
            echo "  Passed: $PASSED / $TOTAL_EVALS"
            echo "  Avg logic score:       $AVG_LOGIC"
            echo "  Avg consistency score: $AVG_CONSISTENCY"
        fi
    else
        echo "  No judge evaluations this session."
    fi
else
    echo "  No eval results directory."
fi

echo ""
echo "=== Session Close Complete ==="
