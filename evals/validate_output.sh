#!/usr/bin/env bash
# Lightweight JSON schema validator for judge output.
# Checks required fields, score range, and tier enum.
# Exit 0 if valid, exit 1 if not.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    echo "Usage: $0 <json_file_or_stdin>"
    echo "  Validates judge output JSON against the expected schema."
    echo "  Pass a file path as argument, or pipe JSON to stdin."
    exit 1
}

# Read JSON from file argument or stdin
if [[ $# -ge 1 && "$1" != "-" ]]; then
    if [[ ! -f "$1" ]]; then
        echo "ERROR: File not found: $1" >&2
        exit 1
    fi
    JSON=$(cat "$1")
else
    JSON=$(cat)
fi

if [[ -z "$JSON" ]]; then
    echo "ERROR: Empty input" >&2
    exit 1
fi

# Validate it's parseable JSON
if ! echo "$JSON" | jq empty 2>/dev/null; then
    echo "ERROR: Invalid JSON" >&2
    exit 1
fi

ERRORS=()

# Check required fields exist
for field in judge score tier timestamp; do
    val=$(echo "$JSON" | jq -r ".$field // empty")
    if [[ -z "$val" ]]; then
        ERRORS+=("Missing required field: $field")
    fi
done

# Check score is a number in range 0-10
SCORE=$(echo "$JSON" | jq -r '.score // empty')
if [[ -n "$SCORE" ]]; then
    # Check it's a valid number
    if ! echo "$SCORE" | grep -qE '^[0-9]+(\.[0-9]+)?$'; then
        ERRORS+=("Score is not a valid number: $SCORE")
    else
        IN_RANGE=$(echo "$SCORE >= 0 && $SCORE <= 10" | bc -l)
        if [[ "$IN_RANGE" != "1" ]]; then
            ERRORS+=("Score out of range (0-10): $SCORE")
        fi
    fi
fi

# Check tier enum
TIER=$(echo "$JSON" | jq -r '.tier // empty')
if [[ -n "$TIER" ]]; then
    case "$TIER" in
        GOLD|SILVER|BRONZE|INVALID) ;;
        *) ERRORS+=("Invalid tier value: $TIER (must be GOLD/SILVER/BRONZE/INVALID)") ;;
    esac
fi

# Check judge field
JUDGE=$(echo "$JSON" | jq -r '.judge // empty')
if [[ -n "$JUDGE" ]]; then
    case "$JUDGE" in
        logic|consistency) ;;
        *) ERRORS+=("Invalid judge value: $JUDGE (must be logic/consistency)") ;;
    esac
fi

# Report results
if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo "VALIDATION FAILED:" >&2
    for err in "${ERRORS[@]}"; do
        echo "  - $err" >&2
    done
    exit 1
fi

echo "VALID"
exit 0
