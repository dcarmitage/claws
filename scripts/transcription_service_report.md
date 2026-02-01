# Parakeet Transcription Service Report

## Overview
Persistent Flask service keeping the `nemo-parakeet-tdt-0.6b-v3` model loaded in memory 24/7 on the Raspberry Pi 5.

## Components
| File | Purpose |
|------|---------|
| `transcription_service.py` | Flask server on `localhost:5111` |
| `transcription.service` | systemd user service (auto-starts on boot) |
| `transcribe_fast.sh` | Client script (`./transcribe_fast.sh /path/to/audio.ogg`) |

## API
- **POST /transcribe** — `{"audio": "/path/to/file.ogg"}` → JSON result
- **GET /health** — Service status and uptime

## Benchmarks (2026-01-30)

### Test Audio
- File: `1ca688bb-c8ae-48a9-9700-289b0ea73bb5.ogg` (Opus, 48kHz mono)
- Duration: **18.52 seconds**

### Results (model warm, service running)
| Metric | Run 1 | Run 2 | Run 3 |
|--------|-------|-------|-------|
| ffmpeg convert | 0.18s | 0.17s | 0.15s |
| Transcription | 7.94s | 7.89s | 7.85s |
| **Total** | **8.13s** | **8.06s** | **8.00s** |
| Realtime factor | 2.3x | 2.3x | 2.3x |

### Cold Start (model load time)
- Model load: ~7-9 seconds (one-time at service start)
- After that, model stays in memory

### Estimated Performance by Audio Length
| Audio Duration | Expected Transcription Time |
|---------------|---------------------------|
| 3s (short voice msg) | ~1.5s |
| 5s | ~2.2s |
| 10s | ~4.3s |
| 18.5s | ~8.0s |

### Transcript Output
> "I wanted to test the reboot first before attaching the AI hat. It looks like it worked. I'm gonna shut off the pie again. Actually, can you do it? And then I will install the AI hat and then check back in with you."

## Service Management
```bash
# Status
systemctl --user status transcription.service

# Restart
systemctl --user restart transcription.service

# Stop
systemctl --user stop transcription.service

# Logs
journalctl --user -u transcription.service -f
```

## Memory Usage
- Model resident memory: ~600-800MB
- Service overhead: ~50MB

## Notes
- Service uses `threaded=False` (single-threaded) since transcription is CPU-bound and concurrent requests would just slow everything down
- ffmpeg conversion adds only ~0.15-0.18s overhead
- Linger is enabled so the user service starts on boot without login
- The onnxruntime GPU warning is harmless (Pi 5 has no supported GPU)
