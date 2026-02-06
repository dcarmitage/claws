#!/usr/bin/env bash
# Logic Judge — falsification-oriented evaluation of task output.
# Calls OpenClaw gateway with the logic judge prompt + evidence.
# Outputs JSON to stdout.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMPT_FILE="$SCRIPT_DIR/prompts/logic_judge.txt"
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
    echo "Usage: $0 --spec <path> --diff <path_or_text> --test-output <path_or_text>"
    echo ""
    echo "Options:"
    echo "  --spec          Path to task specification file"
    echo "  --diff          Git diff (file path or inline text)"
    echo "  --test-output   Test output (file path or inline text)"
    exit 1
}

read_content() {
    # If argument is a file path that exists, read it; otherwise treat as inline text
    if [[ -f "$1" ]]; then
        cat "$1"
    else
        echo "$1"
    fi
}

SPEC=""
DIFF=""
TEST_OUTPUT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --spec) SPEC="$2"; shift 2 ;;
        --diff) DIFF="$2"; shift 2 ;;
        --test-output) TEST_OUTPUT="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1" >&2; usage ;;
    esac
done

if [[ -z "$SPEC" || -z "$DIFF" || -z "$TEST_OUTPUT" ]]; then
    echo "ERROR: --spec, --diff, and --test-output are all required." >&2
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
DIFF_CONTENT=$(read_content "$DIFF")
TEST_CONTENT=$(read_content "$TEST_OUTPUT")

# Assemble user message with evidence
USER_MSG="## SPEC
$SPEC_CONTENT

## DIFF
\`\`\`diff
$DIFF_CONTENT
\`\`\`

## TEST_OUTPUT
\`\`\`
$TEST_CONTENT
\`\`\`

Evaluate this task output now. Respond with JSON only."

# Build request payload — escape for JSON
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

# Extract judge output from response
JUDGE_OUTPUT=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')

if [[ -z "$JUDGE_OUTPUT" ]]; then
    echo "ERROR: No content in LLM response." >&2
    echo "Response: $RESPONSE" >&2
    exit 1
fi

# Extract JSON object — strip any preamble text or markdown fences the model added
JUDGE_OUTPUT=$(echo "$JUDGE_OUTPUT" | sed 's/^```json//; s/^```//; s/```$//' | sed '/^$/d')
# Find the first { to last } to isolate the JSON object
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
    # Still output it so the caller can decide what to do
    echo "$JUDGE_OUTPUT"
    exit 1
fi
