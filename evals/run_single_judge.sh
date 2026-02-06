#!/usr/bin/env bash
# Single Judge Runner — run one judge (logic or consistency) standalone.
# Useful for re-running only the judge that failed, prompt tuning, and debugging.
#
# Usage:
#   ./run_single_judge.sh --judge logic --build-id B001 --task-id T1 --spec path/to/spec.md \
#     --taskboard path/to/taskboard.md --commit abc123 [--working-dir /path]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGIC_JUDGE="$SCRIPT_DIR/logic_judge.sh"
CONSISTENCY_JUDGE="$SCRIPT_DIR/consistency_judge.sh"
VALIDATOR="$SCRIPT_DIR/validate_output.sh"

PASS_THRESHOLD="8.0"

usage() {
    echo "Usage: $0 --judge <logic|consistency> --build-id <id> --task-id <id> --spec <path> --taskboard <path> --commit <sha> [--working-dir <path>]"
    echo ""
    echo "Options:"
    echo "  --judge        Which judge to run: logic or consistency"
    echo "  --build-id     Build identifier"
    echo "  --task-id      Task identifier"
    echo "  --spec         Path to task specification"
    echo "  --taskboard    Path to taskboard file"
    echo "  --commit       Git commit SHA to evaluate"
    echo "  --working-dir  Git working directory (default: /home/clawd)"
    exit 1
}

JUDGE=""
BUILD_ID=""
TASK_ID=""
SPEC=""
TASKBOARD=""
COMMIT=""
WORKING_DIR="/home/clawd"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --judge) JUDGE="$2"; shift 2 ;;
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

# Validate judge type
case "${JUDGE}" in
    logic|consistency) ;;
    "")
        echo "ERROR: --judge is required. Must be 'logic' or 'consistency'." >&2
        usage
        ;;
    *)
        echo "ERROR: Invalid --judge value: '$JUDGE'. Must be 'logic' or 'consistency'." >&2
        exit 1
        ;;
esac

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
trap 'rm -f "$DIFF_FILE"' EXIT

git -C "$WORKING_DIR" show "$COMMIT" --format="" > "$DIFF_FILE" 2>/dev/null || {
    echo "ERROR: Could not get diff for commit $COMMIT" >&2
    exit 1
}

CHANGED_FILES=$(git -C "$WORKING_DIR" show "$COMMIT" --name-only --format="" 2>/dev/null | tr '\n' ',' | sed 's/,$//')
if [[ -z "$CHANGED_FILES" ]]; then
    CHANGED_FILES="(none)"
fi

TEST_OUTPUT="Commit $COMMIT verified. Changed files: $CHANGED_FILES"

# Run the selected judge
echo "=== Running ${JUDGE^} Judge ===" >&2

JUDGE_JSON=""
JUDGE_EXIT=0

if [[ "$JUDGE" == "logic" ]]; then
    JUDGE_JSON=$(bash "$LOGIC_JUDGE" --spec "$SPEC" --diff "$DIFF_FILE" --test-output "$TEST_OUTPUT") || JUDGE_EXIT=$?
else
    JUDGE_JSON=$(bash "$CONSISTENCY_JUDGE" --spec "$SPEC" --taskboard "$TASKBOARD" --diff "$DIFF_FILE" --changed-files "$CHANGED_FILES") || JUDGE_EXIT=$?
fi

if [[ $JUDGE_EXIT -ne 0 ]]; then
    echo "WARNING: ${JUDGE^} judge returned non-zero exit ($JUDGE_EXIT)" >&2
fi

# Validate judge output through validate_output.sh
if echo "$JUDGE_JSON" | bash "$VALIDATOR" - >/dev/null 2>&1; then
    echo "Judge output validation: VALID" >&2
else
    echo "WARNING: Judge output failed validation" >&2
    echo "$JUDGE_JSON" >&2
fi

# Extract score and tier
SCORE=$(echo "$JUDGE_JSON" | jq -r '.score // 0')
TIER=$(echo "$JUDGE_JSON" | jq -r '.tier // "INVALID"')

# Apply threshold
PASSED=$(echo "$SCORE >= $PASS_THRESHOLD" | bc -l)

if [[ "$PASSED" == "1" ]]; then
    RESULT="PASS"
else
    RESULT="FAIL"
fi

# Print summary
echo ""
echo "=== Single Judge Evaluation Summary ==="
echo "Build: $BUILD_ID | Task: $TASK_ID | Commit: ${COMMIT:0:8}"
echo "Judge: ${JUDGE^}"
echo "---"
echo "Score: $SCORE ($TIER) $RESULT"
echo "Threshold: >= $PASS_THRESHOLD"

# On failure, surface details
if [[ "$RESULT" == "FAIL" ]]; then
    echo ""
    echo "=== Failure Details ==="
    if [[ "$JUDGE" == "logic" ]]; then
        echo "$JUDGE_JSON" | jq -r '
            .claims // [] | .[] |
            select(.verdict != "CONFIRMED") |
            "  [\(.verdict)] [\(.severity)] \(.text)\n    Evidence: \(.evidence)"
        ' 2>/dev/null || echo "  (could not parse claims)"
        echo "$JUDGE_JSON" | jq -r '
            .execution_issues // [] | .[] |
            "  [ISSUE] \(.)"
        ' 2>/dev/null || true
    else
        echo "$JUDGE_JSON" | jq -r '
            .checks // {} | to_entries[] |
            select(.value.score < 8.0) |
            "  [\(.value.verdict)] \(.key): \(.value.score)/10" +
            (.value.issues // [] | map("\n    - \(.)") | join(""))
        ' 2>/dev/null || echo "  (could not parse checks)"
    fi
fi

# Output the full JSON to stdout for piping
echo ""
echo "=== Raw JSON ==="
echo "$JUDGE_JSON" | jq .

# Exit code reflects pass/fail
if [[ "$PASSED" == "1" ]]; then
    exit 0
else
    exit 1
fi
