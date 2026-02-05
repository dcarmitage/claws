#!/usr/bin/env bash
# Dual Judge Evaluation Orchestrator.
# Runs both logic and consistency judges, applies thresholds, logs results.
#
# Usage:
#   ./run_dual_judge_eval.sh --build-id B001 --task-id T1 --spec path/to/spec.md \
#     --taskboard path/to/taskboard.md --commit abc123 [--working-dir /path]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGIC_JUDGE="$SCRIPT_DIR/logic_judge.sh"
CONSISTENCY_JUDGE="$SCRIPT_DIR/consistency_judge.sh"
VALIDATOR="$SCRIPT_DIR/validate_output.sh"
RESULTS_DIR="$SCRIPT_DIR/results"
BUILD_LOG="/home/clawd/systems/orchestrator/build_log.py"

PASS_THRESHOLD="8.0"

usage() {
    echo "Usage: $0 --build-id <id> --task-id <id> --spec <path> --taskboard <path> --commit <sha> [--working-dir <path>]"
    echo ""
    echo "Options:"
    echo "  --build-id     Build identifier"
    echo "  --task-id      Task identifier"
    echo "  --spec         Path to task specification"
    echo "  --taskboard    Path to taskboard file"
    echo "  --commit       Git commit SHA to evaluate"
    echo "  --working-dir  Git working directory (default: /home/clawd)"
    exit 1
}

BUILD_ID=""
TASK_ID=""
SPEC=""
TASKBOARD=""
COMMIT=""
WORKING_DIR="/home/clawd"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --build-id) BUILD_ID="$2"; shift 2 ;;
        --task-id) TASK_ID="$2"; shift 2 ;;
        --spec) SPEC="$2"; shift 2 ;;
        --taskboard) TASKBOARD="$2"; shift 2 ;;
        --commit) COMMIT="$2"; shift 2 ;;
        --working-dir) WORKING_DIR="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; usage ;;
    esac
done

if [[ -z "$BUILD_ID" || -z "$TASK_ID" || -z "$SPEC" || -z "$TASKBOARD" || -z "$COMMIT" ]]; then
    echo "ERROR: All of --build-id, --task-id, --spec, --taskboard, --commit are required." >&2
    usage
fi

# Validate input files exist
for f in "$SPEC" "$TASKBOARD"; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: File not found: $f" >&2
        exit 1
    fi
done

# Gather artifacts from git
echo "=== Gathering artifacts for commit $COMMIT ===" >&2

DIFF_FILE=$(mktemp)
CHANGED_FILES_FILE=$(mktemp)
trap 'rm -f "$DIFF_FILE" "$CHANGED_FILES_FILE"' EXIT

git -C "$WORKING_DIR" show "$COMMIT" --format="" > "$DIFF_FILE" 2>/dev/null || {
    echo "ERROR: Could not get diff for commit $COMMIT" >&2
    exit 1
}

CHANGED_FILES=$(git -C "$WORKING_DIR" show "$COMMIT" --name-only --format="" 2>/dev/null | tr '\n' ',' | sed 's/,$//')

if [[ -z "$CHANGED_FILES" ]]; then
    echo "WARNING: No changed files found for commit $COMMIT" >&2
    CHANGED_FILES="(none)"
fi

# Create a test output placeholder (test output from the build log if available)
TEST_OUTPUT="Commit $COMMIT verified. Changed files: $CHANGED_FILES"

echo "=== Running Logic Judge ===" >&2
LOGIC_JSON=""
LOGIC_EXIT=0
LOGIC_JSON=$(bash "$LOGIC_JUDGE" --spec "$SPEC" --diff "$DIFF_FILE" --test-output "$TEST_OUTPUT") || LOGIC_EXIT=$?

if [[ $LOGIC_EXIT -ne 0 ]]; then
    echo "WARNING: Logic judge returned non-zero exit ($LOGIC_EXIT)" >&2
fi

echo "=== Running Consistency Judge ===" >&2
CONSISTENCY_JSON=""
CONSISTENCY_EXIT=0
CONSISTENCY_JSON=$(bash "$CONSISTENCY_JUDGE" --spec "$SPEC" --taskboard "$TASKBOARD" --diff "$DIFF_FILE" --changed-files "$CHANGED_FILES") || CONSISTENCY_EXIT=$?

if [[ $CONSISTENCY_EXIT -ne 0 ]]; then
    echo "WARNING: Consistency judge returned non-zero exit ($CONSISTENCY_EXIT)" >&2
fi

# Extract scores
LOGIC_SCORE=$(echo "$LOGIC_JSON" | jq -r '.score // 0')
LOGIC_TIER=$(echo "$LOGIC_JSON" | jq -r '.tier // "INVALID"')
CONSISTENCY_SCORE=$(echo "$CONSISTENCY_JSON" | jq -r '.score // 0')
CONSISTENCY_TIER=$(echo "$CONSISTENCY_JSON" | jq -r '.tier // "INVALID"')

# Apply threshold: both must be >= 8.0
LOGIC_PASSED=$(echo "$LOGIC_SCORE >= $PASS_THRESHOLD" | bc -l)
CONSISTENCY_PASSED=$(echo "$CONSISTENCY_SCORE >= $PASS_THRESHOLD" | bc -l)

if [[ "$LOGIC_PASSED" == "1" && "$CONSISTENCY_PASSED" == "1" ]]; then
    OVERALL_PASSED=true
    OVERALL_RESULT="PASS"
else
    OVERALL_PASSED=false
    OVERALL_RESULT="FAIL"
fi

# Save full results
mkdir -p "$RESULTS_DIR"
OUTPUT_FILE="$RESULTS_DIR/${BUILD_ID}_${TASK_ID}.json"
jq -n \
    --arg build_id "$BUILD_ID" \
    --arg task_id "$TASK_ID" \
    --arg commit "$COMMIT" \
    --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --argjson logic "$LOGIC_JSON" \
    --argjson consistency "$CONSISTENCY_JSON" \
    --argjson overall_passed "$OVERALL_PASSED" \
    '{
        build_id: $build_id,
        task_id: $task_id,
        commit: $commit,
        timestamp: $timestamp,
        logic_judge: $logic,
        consistency_judge: $consistency,
        overall_passed: $overall_passed
    }' > "$OUTPUT_FILE"

echo "Results saved to: $OUTPUT_FILE" >&2

# Log to build_log.py
if [[ -f "$BUILD_LOG" ]]; then
    python3 "$BUILD_LOG" judge-eval "$BUILD_ID" "$TASK_ID" "$COMMIT" \
        --logic-score "$LOGIC_SCORE" --logic-tier "$LOGIC_TIER" \
        --consistency-score "$CONSISTENCY_SCORE" --consistency-tier "$CONSISTENCY_TIER" \
        --output-path "$OUTPUT_FILE" 2>/dev/null || {
        echo "WARNING: Could not log to build_log.py" >&2
    }
fi

# Print summary
echo ""
echo "=== Dual Judge Evaluation Summary ==="
echo "Build: $BUILD_ID | Task: $TASK_ID | Commit: ${COMMIT:0:8}"
echo "---"
echo "Logic Judge:       $LOGIC_SCORE ($LOGIC_TIER) $([ "$LOGIC_PASSED" == "1" ] && echo "PASS" || echo "FAIL")"
echo "Consistency Judge: $CONSISTENCY_SCORE ($CONSISTENCY_TIER) $([ "$CONSISTENCY_PASSED" == "1" ] && echo "PASS" || echo "FAIL")"
echo "---"
echo "Overall: $OVERALL_RESULT (threshold: >= $PASS_THRESHOLD both judges)"
echo "Output: $OUTPUT_FILE"

# On failure, surface the reasons so the agent knows what to fix
if [[ "$OVERALL_RESULT" == "FAIL" ]]; then
    echo ""
    echo "=== Failure Details (E6: root cause required) ==="
    if [[ "$LOGIC_PASSED" != "1" ]]; then
        echo ""
        echo "LOGIC JUDGE FAILURES:"
        # Show refuted/unverifiable claims
        echo "$LOGIC_JSON" | jq -r '
            .claims // [] | .[] |
            select(.verdict != "CONFIRMED") |
            "  [\(.verdict)] [\(.severity)] \(.text)\n    Evidence: \(.evidence)"
        ' 2>/dev/null || echo "  (could not parse claims)"
        echo "$LOGIC_JSON" | jq -r '
            .execution_issues // [] | .[] |
            "  [ISSUE] \(.)"
        ' 2>/dev/null || true
    fi
    if [[ "$CONSISTENCY_PASSED" != "1" ]]; then
        echo ""
        echo "CONSISTENCY JUDGE FAILURES:"
        echo "$CONSISTENCY_JSON" | jq -r '
            .checks // {} | to_entries[] |
            select(.value.score < 8.0) |
            "  [\(.value.verdict)] \(.key): \(.value.score)/10" +
            (.value.issues // [] | map("\n    - \(.)") | join(""))
        ' 2>/dev/null || echo "  (could not parse checks)"
    fi
    echo ""
    echo "Fix the issues above, then re-run the judge. Do not advance this task."
fi

# Exit code reflects pass/fail
if [[ "$OVERALL_PASSED" == "true" ]]; then
    exit 0
else
    exit 1
fi
