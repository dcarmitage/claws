#!/usr/bin/env python3
"""Overnight tasks for Portal1 — run while Mudpaw sleeps."""
import subprocess, json, time, os, glob
from datetime import datetime

RESULTS = "/home/clawd/media/overnight_report.md"
report = []
report.append(f"# 🌙 Overnight Report — {datetime.now().strftime('%Y-%m-%d')}\n")
report.append("Portal1 worked on these while you slept:\n")

# === 1. TIMELAPSE: Take a photo every 5 minutes for ~7 hours ===
report.append("## 📷 Sunrise Timelapse")
report.append("Capturing a photo every 5 minutes through the night into morning.\n")

os.makedirs("/home/clawd/media/timelapse", exist_ok=True)
TIMELAPSE_DURATION = 7 * 60 * 60  # 7 hours
INTERVAL = 5 * 60  # 5 minutes
start = time.time()
frame = 0

while time.time() - start < TIMELAPSE_DURATION:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outpath = f"/home/clawd/media/timelapse/frame_{frame:04d}_{ts}.jpg"
    subprocess.run([
        "rpicam-still", "-o", outpath,
        "--width", "1920", "--height", "1080",
        "--zsl", "-t", "2000"
    ], capture_output=True, timeout=15)
    frame += 1
    time.sleep(INTERVAL)

report.append(f"- Captured **{frame} frames** over {TIMELAPSE_DURATION//3600}h")
report.append(f"- Saved to `/home/clawd/media/timelapse/`")

# Stitch into video
if frame > 10:
    subprocess.run([
        "ffmpeg", "-y", "-framerate", "24",
        "-pattern_type", "glob", "-i", "/home/clawd/media/timelapse/frame_*.jpg",
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-movflags", "+faststart",
        "/home/clawd/media/timelapse_overnight.mp4"
    ], capture_output=True, timeout=300)
    report.append(f"- Stitched into timelapse video: `/home/clawd/media/timelapse_overnight.mp4`\n")

# Write report
with open(RESULTS, "w") as f:
    f.write("\n".join(report))

print(f"Done! {frame} frames captured.")
