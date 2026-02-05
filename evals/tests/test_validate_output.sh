#!/usr/bin/env bash
# Tests for validate_output.sh
# Usage: bash evals/tests/test_validate_output.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALIDATOR="$SCRIPT_DIR/../validate_output.sh"

PASS=0
FAIL=0

run_test() {
    local desc="$1"
    local input="$2"
    local expect_exit="$3"  # 0 = expect success, 1 = expect failure

    local actual_exit=0
    echo "$input" | bash "$VALIDATOR" - >/dev/null 2>&1 || actual_exit=$?

    if [[ "$actual_exit" -eq 0 && "$expect_exit" -eq 0 ]] || [[ "$actual_exit" -ne 0 && "$expect_exit" -ne 0 ]]; then
        echo "  PASS: $desc"
        ((PASS++))
    else
        echo "  FAIL: $desc (expected exit=$expect_exit, got exit=$actual_exit)"
        ((FAIL++))
    fi
}

echo "=== validate_output.sh tests ==="
echo ""

# --- Valid inputs ---

run_test "Valid logic judge output (GOLD)" \
    '{"judge":"logic","score":9.5,"tier":"GOLD","timestamp":"2026-02-05T00:00:00Z","claims":[],"summary":"Perfect."}' \
    0

run_test "Valid consistency judge output (SILVER)" \
    '{"judge":"consistency","score":8.2,"tier":"SILVER","timestamp":"2026-02-05T00:00:00Z","checks":{},"summary":"Good."}' \
    0

run_test "Valid score at boundary 0.0" \
    '{"judge":"logic","score":0.0,"tier":"INVALID","timestamp":"2026-02-05T00:00:00Z","summary":"Failed."}' \
    0

run_test "Valid score at boundary 10.0" \
    '{"judge":"logic","score":10.0,"tier":"GOLD","timestamp":"2026-02-05T00:00:00Z","summary":"Perfect."}' \
    0

run_test "Valid BRONZE tier" \
    '{"judge":"logic","score":7.0,"tier":"BRONZE","timestamp":"2026-02-05T00:00:00Z","summary":"Ok."}' \
    0

# --- Missing fields ---

run_test "Missing judge field" \
    '{"score":9.0,"tier":"GOLD","timestamp":"2026-02-05T00:00:00Z"}' \
    1

run_test "Missing score field" \
    '{"judge":"logic","tier":"GOLD","timestamp":"2026-02-05T00:00:00Z"}' \
    1

run_test "Missing tier field" \
    '{"judge":"logic","score":9.0,"timestamp":"2026-02-05T00:00:00Z"}' \
    1

run_test "Missing timestamp field" \
    '{"judge":"logic","score":9.0,"tier":"GOLD"}' \
    1

# --- Invalid values ---

run_test "Invalid tier value (PLATINUM)" \
    '{"judge":"logic","score":9.0,"tier":"PLATINUM","timestamp":"2026-02-05T00:00:00Z"}' \
    1

run_test "Invalid judge value (semantic)" \
    '{"judge":"semantic","score":9.0,"tier":"GOLD","timestamp":"2026-02-05T00:00:00Z"}' \
    1

run_test "Score out of range (negative)" \
    '{"judge":"logic","score":-1.0,"tier":"INVALID","timestamp":"2026-02-05T00:00:00Z"}' \
    1

run_test "Score out of range (> 10)" \
    '{"judge":"logic","score":11.0,"tier":"GOLD","timestamp":"2026-02-05T00:00:00Z"}' \
    1

# --- Malformed input ---

run_test "Non-JSON input (plain text)" \
    'This is not JSON at all' \
    1

run_test "Empty input" \
    '' \
    1

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
exit 0
