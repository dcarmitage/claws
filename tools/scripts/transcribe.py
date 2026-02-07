#!/usr/bin/env python3
"""Fast transcription service using faster-whisper.
Usage: python3 transcribe.py <audio_file> [model]
"""
import sys, json, time
from faster_whisper import WhisperModel

# Cache model in memory if run as persistent service
_model_cache = {}

def transcribe(audio_path, model_name="base"):
    if model_name not in _model_cache:
        _model_cache[model_name] = WhisperModel(model_name, device="cpu", compute_type="int8")
    
    model = _model_cache[model_name]
    t0 = time.time()
    segments, info = model.transcribe(audio_path, language="en")
    
    results = []
    for s in segments:
        results.append({"start": s.start, "end": s.end, "text": s.text.strip()})
    
    elapsed = time.time() - t0
    text = " ".join([r["text"] for r in results])
    
    return {
        "text": text,
        "segments": results,
        "duration": round(info.duration, 2),
        "transcription_time": round(elapsed, 2),
        "rtfx": round(info.duration / elapsed, 1),
        "model": model_name
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: transcribe.py <audio_file> [model]")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "base"
    
    result = transcribe(audio_file, model_name)
    print(json.dumps(result, indent=2))
