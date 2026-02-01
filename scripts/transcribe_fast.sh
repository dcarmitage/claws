#!/bin/bash
# Fast transcription via persistent Parakeet service
# Usage: ./transcribe_fast.sh /path/to/audio.ogg
#
# Returns JSON with: text, duration, transcription_time, total_time

AUDIO_FILE="$1"
SERVICE_URL="http://localhost:5111"

if [ -z "$AUDIO_FILE" ]; then
    echo "Usage: transcribe_fast.sh <audio_file>" >&2
    exit 1
fi

if [ ! -f "$AUDIO_FILE" ]; then
    echo "Error: File not found: $AUDIO_FILE" >&2
    exit 1
fi

# Resolve to absolute path
AUDIO_FILE="$(realpath "$AUDIO_FILE")"

exec curl -s -X POST "$SERVICE_URL/transcribe" \
    -H "Content-Type: application/json" \
    -d "{\"audio\": \"$AUDIO_FILE\"}"
