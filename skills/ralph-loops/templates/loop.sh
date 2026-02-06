#!/bin/bash
# Ralph Wiggum Loop Script
# Based on Geoffrey Huntley's methodology
#
# Usage: ./loop.sh [plan|build] [max_iterations]
# Examples:
#   ./loop.sh              # Build mode, unlimited iterations
#   ./loop.sh 20           # Build mode, max 20 iterations
#   ./loop.sh plan         # Plan mode, unlimited iterations
#   ./loop.sh plan 5       # Plan mode, max 5 iterations

set -e

# Parse arguments
if [ "$1" = "plan" ]; then
    MODE="plan"
    PROMPT_FILE="PROMPT_plan.md"
    MAX_ITERATIONS=${2:-0}
elif [ "$1" = "build" ]; then
    MODE="build"
    PROMPT_FILE="PROMPT_build.md"
    MAX_ITERATIONS=${2:-0}
elif [[ "$1" =~ ^[0-9]+$ ]]; then
    MODE="build"
    PROMPT_FILE="PROMPT_build.md"
    MAX_ITERATIONS=$1
else
    MODE="build"
    PROMPT_FILE="PROMPT_build.md"
    MAX_ITERATIONS=0
fi

ITERATION=0
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "no-git")

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐛 Ralph Wiggum Loop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Mode: $MODE"
echo "Prompt: $PROMPT_FILE"
echo "Branch: $CURRENT_BRANCH"
[ $MAX_ITERATIONS -gt 0 ] && echo "Max: $MAX_ITERATIONS iterations"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Verify prompt file exists
if [ ! -f "$PROMPT_FILE" ]; then
    echo "❌ Error: $PROMPT_FILE not found"
    echo ""
    echo "Make sure you have:"
    echo "  - PROMPT_plan.md (for planning mode)"
    echo "  - PROMPT_build.md (for building mode)"
    exit 1
fi

# Check for specs
if [ ! -d "specs" ] || [ -z "$(ls -A specs 2>/dev/null)" ]; then
    echo "⚠️  Warning: No specs found in specs/"
    echo "Consider running Phase 1 (requirements) first."
    echo ""
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

while true; do
    if [ $MAX_ITERATIONS -gt 0 ] && [ $ITERATION -ge $MAX_ITERATIONS ]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ Reached max iterations: $MAX_ITERATIONS"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        break
    fi

    ITERATION=$((ITERATION + 1))
    echo ""
    echo "════════════════════ ITERATION $ITERATION ════════════════════"
    echo ""

    # Run Ralph iteration with selected prompt
    # -p: Headless mode (non-interactive, reads from stdin)
    # --dangerously-skip-permissions: Auto-approve all tool calls
    # --model opus: Use Opus for complex reasoning
    cat "$PROMPT_FILE" | claude -p \
        --dangerously-skip-permissions \
        --model opus \
        --verbose

    # Push changes after each iteration (if git is available and judges passed)
    if [ "$CURRENT_BRANCH" != "no-git" ]; then
        LAST_COMMIT=$(git rev-parse HEAD 2>/dev/null)
        JUDGE_RESULT_FILE="$CLAWS_HOME/evals/results/*_*.json"
        JUDGE_PASSED=true

        # Check if the most recent judge result for this commit passed
        LATEST_RESULT=$(ls -t $CLAWS_HOME/evals/results/*.json 2>/dev/null | head -1)
        if [ -n "$LATEST_RESULT" ]; then
            RESULT_COMMIT=$(jq -r '.commit // ""' "$LATEST_RESULT" 2>/dev/null)
            if [ "$RESULT_COMMIT" = "$LAST_COMMIT" ]; then
                RESULT_PASSED=$(jq -r '.overall_passed // false' "$LATEST_RESULT" 2>/dev/null)
                if [ "$RESULT_PASSED" != "true" ]; then
                    JUDGE_PASSED=false
                    echo "⚠️  Judge gate: last commit did not pass dual-judge evaluation. Skipping push."
                fi
            fi
        fi

        if [ "$JUDGE_PASSED" = true ]; then
            git push origin "$CURRENT_BRANCH" 2>/dev/null || {
                echo "Creating remote branch..."
                git push -u origin "$CURRENT_BRANCH" 2>/dev/null || true
            }
        fi
    fi

    # Brief pause between iterations
    sleep 2
done

echo ""
echo "🎉 Ralph loop complete!"
echo "Total iterations: $ITERATION"
