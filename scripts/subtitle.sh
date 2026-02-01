#!/usr/bin/env bash
# subtitle.sh - Wrapper to run subtitle.py with the whisper venv
# Usage: subtitle.sh input.mp4 [--burn] [--embed] [--translate] [--model base] [-o output.srt]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="/home/clawd/tools/whisper-env"
PYTHON="${VENV}/bin/python3"

if [ ! -f "$PYTHON" ]; then
    echo "[subtitle] Error: whisper venv not found at $VENV" >&2
    exit 1
fi

exec "$PYTHON" "${SCRIPT_DIR}/subtitle.py" "$@"
