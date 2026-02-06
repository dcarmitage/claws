#!/usr/bin/env bash
# Consistency Judge — cross-file alignment evaluation.
# Calls OpenClaw gateway with the consistency judge prompt + all artifacts.
# Outputs JSON to stdout.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="$SCRIPT_DIR/prompts/consistency_judge.txt"
VALIDATOR="$SCRIPT_DIR/validate_output.sh"

OPENCLAW_URL="${OPENCLAW_URL:-http://localhost:18789/v1/chat/completions}"
if [[ -z "${OPENCLAW_TOKEN:-}" ]]; then
    OPENCLAW_CONFIG="$OPENCLAW_CONFIG"
    if [[ -f "$OPENCLAW_CONFIG" ]]; then
        OPENCLAW_TOKEN=$(python3 -c "import json; print(json.load(open('$OPENCLAW_CONFIG'))['gateway']['auth']['token'])" 2>/dev/null || true)
    fi
fi
OPENCLAW_TOKEN="${OPENCLAW_TOKEN:-}"

usage() {
    echo "Usage: $0 --spec <path> --taskboard <path> --diff <path_or_text> --changed-files <list>"
    echo ""
    echo "Options:"
    echo "  --spec           Path to task specification file"
    echo "  --taskboard      Path to taskboard file"
    echo "  --diff           Git diff (file path or inline text)"
    echo "  --changed-files  Comma-separated list of changed files"
    exit 1
}

read_content() {
    if [[ -f "$1" ]]; then
        cat "$1"
    else
        echo "$1"
    fi
}

SPEC=""
TASKBOARD=""
DIFF=""
CHANGED_FILES=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --spec) SPEC="$2"; shift 2 ;;
        --taskboard) TASKBOARD="$2"; shift 2 ;;
        --diff) DIFF="$2"; shift 2 ;;
        --changed-files) CHANGED_FILES="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; usage ;;
    esac
done

if [[ -z "$SPEC" || -z "$TASKBOARD" || -z "$DIFF" || -z "$CHANGED_FILES" ]]; then
    echo "ERROR: --spec, --taskboard, --diff, and --changed-files are all required." >&2
    usage
fi

# Load prompt template
if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "ERROR: Prompt template not found: $PROMPT_FILE" >&2
    exit 1
fi
SYSTEM_PROMPT=$(cat "$PROMPT_FILE")

# Gather evidence
SPEC_CONTENT=$(read_content "$SPEC")
TASKBOARD_CONTENT=$(read_content "$TASKBOARD")
DIFF_CONTENT=$(read_content "$DIFF")

# Assemble user message
USER_MSG="## SPEC
$SPEC_CONTENT

## TASKBOARD
$TASKBOARD_CONTENT

## DIFF
\`\`\`diff
$DIFF_CONTENT
\`\`\`

## CHANGED FILES
$CHANGED_FILES

Evaluate cross-file consistency now. Respond with JSON only."

# Build request payload
PAYLOAD=$(jq -n \
    --arg system "$SYSTEM_PROMPT" \
    --arg user "$USER_MSG" \
    '{
        "messages": [
            {"role": "system", "content": $system},
            {"role": "user", "content": $user}
        ],
        "temperature": 0
    }')

# Call OpenClaw gateway
AUTH_HEADER=""
if [[ -n "$OPENCLAW_TOKEN" ]]; then
    AUTH_HEADER="Authorization: Bearer $OPENCLAW_TOKEN"
fi

RESPONSE=$(curl -s -X POST "$OPENCLAW_URL" \
    -H "Content-Type: application/json" \
    ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
    -d "$PAYLOAD")

# Extract judge output
JUDGE_OUTPUT=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')

if [[ -z "$JUDGE_OUTPUT" ]]; then
    echo "ERROR: No content in LLM response." >&2
    echo "Response: $RESPONSE" >&2
    exit 1
fi

# Extract JSON object — strip any preamble text or markdown fences the model added
JUDGE_OUTPUT=$(echo "$JUDGE_OUTPUT" | sed 's/^```json//; s/^```//; s/```$//' | sed '/^$/d')
JUDGE_OUTPUT=$(echo "$JUDGE_OUTPUT" | python3 -c "
import sys
text = sys.stdin.read()
start = text.find('{')
end = text.rfind('}')
if start >= 0 and end > start:
    print(text[start:end+1])
else:
    print(text)
")

# Validate the output
if echo "$JUDGE_OUTPUT" | bash "$VALIDATOR" - >/dev/null 2>&1; then
    echo "$JUDGE_OUTPUT"
else
    echo "WARNING: Judge output failed validation. Raw output:" >&2
    echo "$JUDGE_OUTPUT" >&2
    echo "$JUDGE_OUTPUT"
    exit 1
fi
