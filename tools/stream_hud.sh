#!/bin/bash
# Dynamic HUD text generator for ffmpeg drawtext
# Writes current stats to a text file that ffmpeg reads each frame
# Usage: stream_hud.sh <textfile> <media_root> <start_epoch>

TEXTFILE="$1"
MEDIA_ROOT="${2:-/mnt/media}"
START_EPOCH="${3:-$(date +%s)}"

while true; do
    NOW=$(date +%s)
    ELAPSED=$((NOW - START_EPOCH))
    HH=$(printf "%02d" $((ELAPSED / 3600)))
    MM=$(printf "%02d" $(((ELAPSED % 3600) / 60)))
    SS=$(printf "%02d" $((ELAPSED % 60)))

    # Storage
    if mountpoint -q "$MEDIA_ROOT" 2>/dev/null; then
        FREE=$(df -h "$MEDIA_ROOT" | awk 'NR==2{print $4}')
        TOTAL=$(df -h "$MEDIA_ROOT" | awk 'NR==2{print $2}')
        PCT=$(df "$MEDIA_ROOT" | awk 'NR==2{print $5}')
    else
        FREE=$(df -h $CLAWS_HOME/media | awk 'NR==2{print $4}')
        TOTAL=$(df -h $CLAWS_HOME/media | awk 'NR==2{print $2}')
        PCT=$(df $CLAWS_HOME/media | awk 'NR==2{print $5}')
    fi

    # Recording file size
    REC_FILE=$(ls -t "$MEDIA_ROOT"/stream_*.ts 2>/dev/null | head -1)
    if [ -n "$REC_FILE" ] && [ -f "$REC_FILE" ]; then
        REC_SIZE=$(du -h "$REC_FILE" | awk '{print $1}')
    else
        REC_SIZE="0B"
    fi

    # Date
    DATESTAMP=$(date +"%d%b%y" | tr '[:lower:]' '[:upper:]')
    TIMESTAMP=$(date +"%H\:%M\:%S")

    # Write watermark text (subtle signature)
    echo "@your-user  ${DATESTAMP} ${TIMESTAMP}" > "$TEXTFILE"

    sleep 1
done
