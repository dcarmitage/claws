#!/usr/bin/env python3
"""Persistent Parakeet transcription service.

Keeps the nemo-parakeet-tdt-0.6b-v3 model loaded in memory.
Listens on localhost:5111 for transcription requests.

POST /transcribe  {"audio": "/path/to/file.ogg"}
GET  /health      → {"status": "ok", "model": "...", "uptime": ...}
"""

import json
import logging
import os
import subprocess
import tempfile
import time

from flask import Flask, request, jsonify

# --- Config ---
MODEL_NAME = "nemo-parakeet-tdt-0.6b-v3"
HOST = "127.0.0.1"
PORT = 5111

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("transcription_service")

# --- App ---
app = Flask(__name__)

# --- Global model ---
model = None
start_time = None


def load_model():
    global model, start_time
    log.info("Loading model %s ...", MODEL_NAME)
    t0 = time.time()
    import onnx_asr
    model = onnx_asr.load_model(MODEL_NAME)
    elapsed = time.time() - t0
    start_time = time.time()
    log.info("Model loaded in %.1fs", elapsed)


def convert_to_wav(input_path: str) -> str:
    """Convert audio to 16kHz mono WAV. Returns path to temp wav file."""
    # If already a wav, check sample rate
    if input_path.lower().endswith(".wav"):
        # Still convert to ensure 16kHz mono
        pass

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ar", "16000", "-ac", "1",
        "-f", "wav", tmp.name,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    if result.returncode != 0:
        os.unlink(tmp.name)
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:500]}")
    return tmp.name


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model": MODEL_NAME,
        "uptime": round(time.time() - start_time, 1) if start_time else 0,
    })


@app.route("/transcribe", methods=["POST"])
def transcribe():
    data = request.get_json(force=True, silent=True) or {}
    audio_path = data.get("audio")

    if not audio_path:
        return jsonify({"error": "missing 'audio' field"}), 400

    if not os.path.isfile(audio_path):
        return jsonify({"error": f"file not found: {audio_path}"}), 404

    wav_path = None
    try:
        # Convert to wav
        t_convert = time.time()
        wav_path = convert_to_wav(audio_path)
        convert_time = time.time() - t_convert

        # Get audio duration via ffprobe
        duration = 0.0
        try:
            probe = subprocess.run(
                ["ffprobe", "-i", audio_path, "-show_entries", "format=duration",
                 "-v", "quiet", "-of", "csv=p=0"],
                capture_output=True, text=True, timeout=10,
            )
            duration = float(probe.stdout.strip())
        except Exception:
            pass

        # Transcribe
        t_transcribe = time.time()
        text = model.recognize(wav_path)
        transcription_time = time.time() - t_transcribe

        total_time = convert_time + transcription_time

        log.info(
            "Transcribed %.1fs audio in %.2fs (convert=%.2fs, infer=%.2fs) → %d chars",
            duration, total_time, convert_time, transcription_time, len(text),
        )

        return jsonify({
            "text": text,
            "duration": round(duration, 2),
            "transcription_time": round(transcription_time, 2),
            "total_time": round(total_time, 2),
            "convert_time": round(convert_time, 2),
            "model": MODEL_NAME,
        })

    except Exception as e:
        log.exception("Transcription failed")
        return jsonify({"error": str(e)}), 500

    finally:
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)


if __name__ == "__main__":
    load_model()
    log.info("Starting transcription service on %s:%d", HOST, PORT)
    app.run(host=HOST, port=PORT, threaded=False)
