#!/bin/bash
# Fast transcription using faster-whisper (int8, CPU)
# Usage: transcribe.sh <audio_file> [model]
# Models: tiny, base, small, medium, large-v3
# Default: base (best speed/quality tradeoff for Pi 5)

AUDIO_FILE="$1"
MODEL="${2:-base}"

if [ -z "$AUDIO_FILE" ]; then
    echo "Usage: transcribe.sh <audio_file> [model]"
    exit 1
fi

source /home/clawd/tools/whisper-env/bin/activate

python3 -c "
import sys, json, time
from faster_whisper import WhisperModel

model = WhisperModel('${MODEL}', device='cpu', compute_type='int8')
t0 = time.time()
segments, info = model.transcribe('${AUDIO_FILE}', language='en')
results = []
for s in segments:
    results.append({'start': s.start, 'end': s.end, 'text': s.text.strip()})

elapsed = time.time() - t0
text = ' '.join([r['text'] for r in results])

output = {
    'text': text,
    'segments': results,
    'duration': info.duration,
    'transcription_time': round(elapsed, 2),
    'rtfx': round(info.duration / elapsed, 1),
    'model': '${MODEL}'
}
print(json.dumps(output, indent=2))
"
