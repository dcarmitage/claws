#!/bin/bash
# Time the full transcription pipeline
AUDIO="$1"
echo "=== Pipeline Benchmark ==="
echo "Start: $(date +%s.%N)"

echo -n "Transcription service call... "
T0=$(date +%s.%N)
RESULT=$(curl -s -X POST http://localhost:5111/transcribe -H "Content-Type: application/json" -d "{\"audio\": \"$AUDIO\"}")
T1=$(date +%s.%N)
ELAPSED=$(echo "$T1 - $T0" | bc)
echo "${ELAPSED}s"

echo "Result: $RESULT"
echo "End: $(date +%s.%N)"
