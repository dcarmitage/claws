#!/usr/bin/env python3
"""
Portal1 Camera Service — persistent camera with instant capture + streaming.

Keeps the camera sensor initialized via Picamera2. Snaps are ~60ms.

Endpoints:
  GET /snap                          → returns file path (text/plain)
  GET /snap.jpg                      → returns JPEG binary directly
  GET /clip?duration=3               → returns file path to MP4
  GET /stream/start                  → start HLS stream (local)
  GET /stream/start?rtmp=<url>       → start RTMP push (YouTube/Twitch/X)
  GET /stream/stop                   → stop streaming
  GET /stream/status                 → streaming status JSON
  GET /stream/live.m3u8              → HLS playlist (when streaming locally)
  GET /stream/<segment>.ts           → HLS segments
  GET /health                        → status JSON
"""
from picamera2 import Picamera2
import subprocess
import signal
import time
import os
import json
import threading
import glob
import shutil as _shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from datetime import datetime

PORT = 5080
# Use USB drive if mounted, fallback to SD card
MEDIA_DIR = "/mnt/media" if os.path.ismount("/mnt/media") else "/home/clawd/media"
STREAM_DIR = os.path.join(MEDIA_DIR, "stream")
LOCK = threading.Lock()

# Import catalog for auto-indexing
import sys
sys.path.insert(0, "/home/clawd/tools/catalog")
try:
    import catalog
    catalog.init_db()
    HAS_CATALOG = True
except:
    HAS_CATALOG = False

# Streaming state
stream_proc = None
stream_mode = None  # "hls" or "rtmp"
stream_rtmp_url = None
stream_started_at = None
stream_rec_path = None
stream_hud = False
stream_hud_proc = None
HUD_TEXTFILE = "/tmp/stream_hud.txt"
HUD_SCRIPT = "/home/clawd/tools/stream_hud.sh"
mic_muted = False

def mic_set_mute(mute):
    """Set microphone mute state via ALSA mixer."""
    global mic_muted
    mic_muted = mute
    try:
        val = "nocap" if mute else "cap"
        subprocess.run(["amixer", "-c", "0", "sset", "Mic", val],
                       capture_output=True, timeout=5)
    except:
        pass
    return {"muted": mic_muted}

WATCH_HTML = r"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>portal1</title>
<style>
  :root {
    --hud: rgba(255,255,255,0.85);
    --hud-dim: rgba(255,255,255,0.4);
    --hud-bg: rgba(0,0,0,0.45);
    --rec: #ff3b30;
    --amber: #ff9500;
    --mono: 'SF Mono','Menlo','Cascadia Code','Consolas',monospace;
    --sans: -apple-system,system-ui,'Helvetica Neue',sans-serif;
  }
  *{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  body{background:#000;color:var(--hud);overflow:hidden;user-select:none;-webkit-user-select:none}

  #vf{position:fixed;inset:0;display:flex;align-items:center;justify-content:center}
  video{width:100%;height:100%;object-fit:contain;cursor:pointer}

  /* Grid */
  #grid{position:absolute;inset:0;pointer-events:none;opacity:0;transition:opacity .3s}
  #grid.show{opacity:1}
  #grid line{stroke:rgba(255,255,255,.15);stroke-width:.5}

  /* ── Command Station ── */
  #dock{position:absolute;bottom:0;left:0;right:0;z-index:10;
    padding:0 16px env(safe-area-inset-bottom,10px);
    background:linear-gradient(transparent,rgba(0,0,0,.6) 30%);
    transition:opacity .4s}
  #dock.dim{opacity:.15}

  /* Scrubber */
  .track{height:28px;display:flex;align-items:center;position:relative;cursor:pointer;touch-action:none}
  .track *{pointer-events:none}
  .track-bg{position:absolute;left:0;right:0;height:3px;background:rgba(255,255,255,.12);border-radius:2px}
  .track-buf{position:absolute;height:3px;background:rgba(255,255,255,.18);border-radius:2px}
  .track-prog{position:absolute;left:0;height:3px;background:var(--rec);border-radius:2px}
  .track-head{position:absolute;top:50%;width:11px;height:11px;border-radius:50%;background:#fff;
    transform:translate(-50%,-50%);box-shadow:0 0 6px rgba(0,0,0,.5);transition:transform .1s}
  .track:active .track-head{transform:translate(-50%,-50%) scale(1.3)}

  /* VU meter — same style as storage bar */
  .vu-bar{width:100%;height:3px;border-radius:2px;background:rgba(255,255,255,.1);overflow:hidden;margin:4px 0 6px}
  .vu-fill{height:100%;border-radius:2px;width:0%;transition:width 80ms linear;background:var(--hud)}

  /* Controls row */
  .controls{display:flex;align-items:center;justify-content:space-between;height:24px;
    font:10px/1 var(--mono);letter-spacing:.04em}
  .ctrl-group{display:flex;align-items:center;gap:8px}

  .rec-dot{width:6px;height:6px;border-radius:50%;background:var(--rec);flex-shrink:0}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
  .rec-dot.on{animation:pulse 1.2s ease-in-out infinite}
  .v{font-variant-numeric:tabular-nums;color:var(--hud)}

  .pill{padding:2px 8px;border-radius:8px;font:10px/1 var(--mono);font-weight:600;
    letter-spacing:.08em;cursor:pointer;transition:all .15s}
  .pill-live{background:rgba(255,60,48,.7);color:#fff}
  .pill-behind{background:var(--hud-bg);color:var(--hud-dim)}
  .pill-behind:hover{background:rgba(255,60,48,.4);color:#fff}

  .dbtn{background:none;border:none;color:var(--hud-dim);cursor:pointer;
    font:10px/1 var(--mono);letter-spacing:.05em;padding:2px 6px;border-radius:6px;
    transition:color .2s,background .2s;white-space:nowrap}
  .dbtn:hover{color:var(--hud);background:rgba(255,255,255,.08)}
  .dbtn.active{color:var(--hud)}
  .dbtn.off{color:var(--rec)}
  .dbtn .dot{display:inline-block;width:5px;height:5px;border-radius:50%;
    background:currentColor;margin-right:3px;vertical-align:middle}

  .storage-bar{width:36px;height:3px;border-radius:2px;background:rgba(255,255,255,.1);overflow:hidden}
  .storage-fill{height:100%;border-radius:2px;background:var(--hud-dim);transition:width .5s}
  .storage-fill.warn{background:var(--amber)}
  .storage-fill.crit{background:var(--rec)}

  #pause-flash{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
    font-size:56px;opacity:0;transition:opacity .25s;pointer-events:none;
    text-shadow:0 2px 12px rgba(0,0,0,.5)}

  #offline{position:absolute;inset:0;display:flex;flex-direction:column;
    align-items:center;justify-content:center;gap:16px;z-index:5}
  #offline.hidden{display:none}
  .off-icon{font-size:48px;opacity:.15}
  .off-label{font:13px/1.4 var(--sans);color:var(--hud-dim);text-align:center;max-width:280px}
  .off-label strong{color:var(--hud);font-weight:500}
  #offline .dbtn{font-size:12px;padding:8px 20px;background:var(--hud-bg);border-radius:10px}
  #dbg{margin-top:16px;font:10px/1.4 monospace;color:rgba(255,255,255,0.25);
    max-height:100px;overflow:auto;text-align:left;width:80%;max-width:500px}
</style>
</head><body>
<div id="vf">
  <video id="v" autoplay muted playsinline></video>

  <svg id="grid" viewBox="0 0 300 200" preserveAspectRatio="none">
    <line x1="100" y1="0" x2="100" y2="200"/><line x1="200" y1="0" x2="200" y2="200"/>
    <line x1="0" y1="66.7" x2="300" y2="66.7"/><line x1="0" y1="133.3" x2="300" y2="133.3"/>
  </svg>

  <div id="dock">
    <div class="track" id="track">
      <div class="track-bg"></div>
      <div class="track-buf" id="tbuf"></div>
      <div class="track-prog" id="tprog"></div>
      <div class="track-head" id="thead"></div>
    </div>
    <div class="vu-bar"><div class="vu-fill" id="vu-fill"></div></div>
    <div class="controls">
      <div class="ctrl-group">
        <div class="rec-dot" id="rdot"></div>
        <span class="v" id="rtime">00:00:00</span>
        <span class="pill pill-live" id="lpill" onclick="goLive()">LIVE</span>
      </div>
      <div class="ctrl-group">
        <button class="dbtn" id="mic-btn" onclick="toggleMic()" title="Microphone"><span class="dot"></span>MIC</button>
        <button class="dbtn" id="vol-btn" onclick="toggleVol()" title="Audio">VOL</button>
        <button class="dbtn" id="grid-btn" onclick="toggleGrid()" title="Grid">GRID</button>
        <button class="dbtn" onclick="toggleFS()" title="Fullscreen">FS</button>
        <span class="v" id="sfree" style="color:var(--hud-dim);font-size:9px">--</span>
        <div class="storage-bar"><div class="storage-fill" id="sfill"></div></div>
      </div>
    </div>
  </div>

  <div id="pause-flash">&#10074;&#10074;</div>

  <div id="offline">
    <div class="off-icon">&#127744;</div>
    <div class="off-label"><strong>portal1</strong> is idle<br>
      <span id="off-sub">Send <code>/stream start</code> to go live</span></div>
    <button class="dbtn" onclick="location.reload()">&#x21bb; refresh</button>
    <pre id="dbg"></pre>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
<script>
const $ = id => document.getElementById(id);
const v = $('v'), HOST = '__HOST__';
const streamUrl = `http://${HOST}/stream/live.m3u8`;
function dbg(s) { console.log(s); const el=$('dbg'); if(el) el.textContent += s + '\n'; }

let hls, active = false, gridOn = false, dimTimer;
let dragging = false, mode = 'live';
let micMuted = false;

// ── Audio analyser ──
// Route: video → MediaElementSource → analyser → gainNode → speakers
// Video is unmuted after first click so analyser always gets data.
// Volume controlled by gainNode (not v.muted).
let audioCtx, analyser, audioSrc, gainNode, audioReady = false;
let speakerOn = false;
const vuFill = $('vu-fill');

function initAudio() {
  if (audioReady) return;
  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.5;
    gainNode = audioCtx.createGain();
    gainNode.gain.value = 0; // start silent — VOL button turns on
    audioSrc = audioCtx.createMediaElementSource(v);
    audioSrc.connect(analyser);
    analyser.connect(gainNode);
    gainNode.connect(audioCtx.destination);
    // Unmute the element so audio data flows through the graph
    v.muted = false;
    audioReady = true;
    dbg('audio ok — analyser live');
  } catch(e) { dbg('audio: ' + e.message); }
}

function ensureAudio() {
  initAudio();
  if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
}

// VU meter — update fill width based on RMS level
let vuLevel = 0;
function updateVU() {
  requestAnimationFrame(updateVU);
  if (!active || !analyser) { vuFill.style.width = '0%'; return; }
  const data = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(data);
  let sum = 0;
  for (let i = 0; i < data.length; i++) sum += data[i];
  const avg = sum / data.length / 255;
  vuLevel += (avg - vuLevel) * 0.35;
  const pct = Math.min(100, Math.round(vuLevel * 250));
  vuFill.style.width = pct + '%';
  // Color shift: white → amber → red at high levels
  if (pct > 85) vuFill.style.background = 'var(--rec)';
  else if (pct > 60) vuFill.style.background = 'var(--amber)';
  else vuFill.style.background = 'var(--hud)';
}
requestAnimationFrame(updateVU);

// ── HLS Player ──
function init() {
  if (hls) { hls.destroy(); hls = null; }
  mode = 'live';
  if (!Hls.isSupported()) { v.src = streamUrl; v.play(); return; }
  hls = new Hls({
    backBufferLength: 60,
    maxBufferLength: 10,
    maxMaxBufferLength: 20,
    manifestLoadingMaxRetry: 30,
    manifestLoadingRetryDelay: 800,
    levelLoadingRetryDelay: 800,
    fragLoadingRetryDelay: 800,
  });
  hls.loadSource(streamUrl);
  hls.attachMedia(v);
  hls.on(Hls.Events.MANIFEST_PARSED, () => {
    dbg('manifest ok');
    v.play().catch(e => dbg('play: ' + e.message));
    setActive(true);
    setTimeout(() => {
      if (v.buffered.length) v.currentTime = v.buffered.end(v.buffered.length - 1) - 0.5;
      setMode('live');
    }, 600);
  });
  hls.on(Hls.Events.FRAG_LOADED, () => { if (!active) setActive(true); });
  hls.on(Hls.Events.ERROR, (_, d) => {
    dbg('hls ' + (d.fatal?'FATAL':'') + ' ' + d.details);
    if (d.fatal) { hls.destroy(); hls = null; }
  });
  dbg('hls init');
}

function setActive(on, msg) {
  active = on;
  $('offline').classList.toggle('hidden', on);
  $('dock').style.display = on ? '' : 'none';
  if (on) { $('rdot').classList.add('on'); resetDim(); }
  else {
    $('rdot').classList.remove('on'); $('rtime').textContent = '--:--:--';
    if (msg) $('off-sub').textContent = msg;
    v.pause(); if (hls) { hls.destroy(); hls = null; }
    v.removeAttribute('src'); v.load();
  }
}

function setMode(m) {
  mode = m;
  const p = $('lpill');
  if (m === 'live') { p.className = 'pill pill-live'; p.textContent = 'LIVE'; }
  else { p.className = 'pill pill-behind'; }
}

function getBehind() {
  if (!v.buffered.length) return 0;
  return Math.max(0, v.buffered.end(v.buffered.length - 1) - v.currentTime);
}
function fmtBehind(s) {
  if (s < 1) return 'LIVE';
  if (s < 60) return '-' + Math.round(s) + 's';
  return '-' + Math.floor(s/60) + ':' + String(Math.floor(s%60)).padStart(2,'0');
}

// ── Tap play/pause ──
v.addEventListener('click', e => {
  if (e.target !== v) return;
  ensureAudio();
  if (v.paused) {
    v.play();
    if (mode === 'paused') { if (hls) hls.config.liveSyncDuration = 999999; setMode('rewind'); }
  } else {
    v.pause();
    if (hls) hls.config.liveSyncDuration = 999999;
    setMode('paused');
    $('pause-flash').style.opacity = '1';
    setTimeout(() => $('pause-flash').style.opacity = '0', 700);
  }
});
v.addEventListener('play', () => $('pause-flash').style.opacity = '0');
v.addEventListener('playing', () => { if (!active) setActive(true); });

function goLive() {
  if (hls) delete hls.config.liveSyncDuration;
  if (v.paused) v.play();
  if (v.buffered.length) v.currentTime = v.buffered.end(v.buffered.length - 1) - 0.5;
  setMode('live');
}

// ── Scrubber ──
const track = $('track');
track.addEventListener('pointerdown', e => {
  dragging = true;
  if (mode === 'live') setMode('rewind');
  if (hls) hls.config.liveSyncDuration = 999999;
  scrub(e);
});
document.addEventListener('pointermove', e => { if (dragging) scrub(e); });
document.addEventListener('pointerup', () => {
  if (dragging) { dragging = false; if (getBehind() < 2) goLive(); }
});
function scrub(e) {
  if (!v.buffered.length) return;
  const rect = track.getBoundingClientRect();
  const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  const start = v.buffered.start(0);
  const end = v.buffered.end(v.buffered.length - 1);
  v.currentTime = start + pct * (end - start);
}

// ── Render loop ──
let lastRender = 0;
function render(ts) {
  requestAnimationFrame(render);
  if (ts - lastRender < 200) return;
  lastRender = ts;
  if (!active || !v.buffered.length) return;
  const end = v.buffered.end(v.buffered.length - 1);
  const start = v.buffered.start(0);
  const avail = end - start;
  const behind = Math.max(0, end - v.currentTime);
  $('tbuf').style.left = '0%'; $('tbuf').style.width = '100%';
  if (mode === 'live' && !dragging) {
    $('tprog').style.width = '100%'; $('thead').style.left = '100%';
  } else {
    const pos = avail > 0.5 ? Math.max(0, Math.min(1, (v.currentTime - start) / avail)) : 1;
    $('tprog').style.width = (pos*100)+'%'; $('thead').style.left = (pos*100)+'%';
    $('lpill').textContent = (mode==='paused'?'\u23F8 ':'')+fmtBehind(behind)+' \u00b7 LIVE';
  }
}
requestAnimationFrame(render);

// ── Controls ──
function toggleGrid() { gridOn=!gridOn; $('grid').classList.toggle('show',gridOn); $('grid-btn').classList.toggle('active',gridOn); }
function toggleVol() {
  ensureAudio();
  speakerOn = !speakerOn;
  if (gainNode) gainNode.gain.value = speakerOn ? 1 : 0;
  $('vol-btn').classList.toggle('active', speakerOn);
}
async function toggleMic() {
  try {
    const r = await fetch(`http://${HOST}/stream/mic?mute=${micMuted?'0':'1'}`);
    const d = await r.json();
    micMuted = d.muted;
    updateMicUI();
  } catch(e) { dbg('mic: '+e.message); }
}
function updateMicUI() {
  $('mic-btn').classList.toggle('off', micMuted);
  $('mic-btn').innerHTML = micMuted ? 'MIC' : '<span class="dot"></span>MIC';
}
function toggleFS() { document.fullscreenElement ? document.exitFullscreen() : $('vf').requestFullscreen(); }

// ── Auto-dim ──
function resetDim() {
  $('dock').classList.remove('dim');
  clearTimeout(dimTimer);
  dimTimer = setTimeout(() => { if (active) $('dock').classList.add('dim'); }, 5000);
}
document.addEventListener('mousemove', resetDim);
document.addEventListener('touchstart', resetDim);

// ── Polls ──
async function pollStatus() {
  try {
    const r = await fetch(`http://${HOST}/stream/status`);
    const d = await r.json();
    if (d.streaming) {
      if (!hls) { dbg('stream detected'); init(); }
      $('rtime').textContent = d.elapsed || '00:00:00';
      if (d.mic_muted !== undefined && d.mic_muted !== micMuted) { micMuted = d.mic_muted; updateMicUI(); }
      if (!active) $('off-sub').textContent = 'Connecting...';
    } else {
      if (active) setActive(false, 'Stream ended');
    }
  } catch(e) { if (active) setActive(false, 'Connection lost'); }
}
async function pollStorage() {
  try {
    const r = await fetch(`http://${HOST}/storage`);
    const d = await r.json();
    $('sfree').textContent = d.free_gb+'G';
    const f=$('sfill'); f.style.width=d.used_pct+'%';
    f.className='storage-fill'+(d.used_pct>95?' crit':d.used_pct>85?' warn':'');
  } catch(e) {}
}
setInterval(pollStatus, 2000);
setInterval(pollStorage, 5000);

// ── Init ──
pollStatus(); pollStorage(); init();
setTimeout(() => { if (!active) setActive(false); }, 3000);
document.addEventListener('click', ensureAudio);
document.addEventListener('touchstart', ensureAudio);
document.addEventListener('pointerdown', ensureAudio);
</script>
</body></html>"""

# Initialize persistent camera
cam = None

def init_camera():
    global cam
    if cam is not None:
        try:
            cam.stop()
            cam.close()
        except:
            pass
    cam = Picamera2()
    cam.configure(cam.create_still_configuration(main={"size": (1920, 1080)}))
    cam.start()
    time.sleep(1)

init_camera()

def snap():
    """Capture a photo. ~60ms. Returns file path."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"{MEDIA_DIR}/snap_{ts}.jpg"
    with LOCK:
        cam.capture_file(path)
    if path and os.path.exists(path) and HAS_CATALOG:
        try:
            catalog.ingest(path, media_type="snap", move=False)
        except:
            pass
    return path if os.path.exists(path) else None

def clip(duration_s=3, width=1920, height=1080):
    """Capture a video clip. Returns file path to MP4."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = f"{MEDIA_DIR}/clip_{ts}_raw.mp4"
    mp4_path = f"{MEDIA_DIR}/clip_{ts}.mp4"
    with LOCK:
        try:
            cam.stop()
            cam.close()
        except:
            pass
        try:
            subprocess.run([
                "rpicam-vid", "-o", raw_path,
                "--width", str(width), "--height", str(height),
                "-t", str(int(duration_s * 1000)), "--nopreview",
                "--framerate", "30", "--codec", "libav",
                "--libav-format", "mp4"
            ], capture_output=True, timeout=duration_s + 10)
            if os.path.exists(raw_path):
                size = os.path.getsize(raw_path)
                if size > 15_000_000:
                    subprocess.run([
                        "ffmpeg", "-y", "-i", raw_path,
                        "-c:v", "libx264", "-preset", "fast", "-crf", "28",
                        "-movflags", "+faststart", mp4_path
                    ], capture_output=True, timeout=duration_s * 3)
                    os.remove(raw_path)
                else:
                    os.rename(raw_path, mp4_path)
        finally:
            init_camera()
    if mp4_path and os.path.exists(mp4_path) and HAS_CATALOG:
        try:
            catalog.ingest(mp4_path, media_type="clip", move=False)
        except:
            pass
    return mp4_path if os.path.exists(mp4_path) else None

def stream_start(rtmp_url=None, width=1280, height=720, fps=30, bitrate="2500k", hud=False):
    """Start streaming. HLS locally, or RTMP push if url provided."""
    global stream_proc, stream_mode, stream_rtmp_url, stream_started_at, stream_rec_path
    global stream_hud, stream_hud_proc

    if stream_proc is not None:
        return {"error": "Stream already running. Stop it first."}

    # Release Picamera2 so rpicam-vid can use the camera
    with LOCK:
        try:
            cam.stop()
            cam.close()
        except:
            pass

    os.makedirs(STREAM_DIR, exist_ok=True)
    # Clean old segments
    for f in glob.glob(f"{STREAM_DIR}/*.ts") + glob.glob(f"{STREAM_DIR}/*.m3u8"):
        os.remove(f)

    # HUD overlay filter (re-encodes video with text overlay)
    stream_hud = hud
    if hud:
        # Use 720p for HUD mode (re-encoding needs headroom)
        width = min(width, 1280)
        height = min(height, 720)
        hud_filter = (
            f"drawtext=textfile={HUD_TEXTFILE}:reload=1:"
            f"fontsize=14:fontcolor=white@0.35:borderw=1:bordercolor=black@0.15:"
            f"x=w-tw-14:y=12:font=monospace"
        )
        video_encode = f"-vf '{hud_filter}' -c:v libx264 -preset ultrafast -tune zerolatency -g {fps} -keyint_min {fps} -crf 23"
    else:
        video_encode = f"-c:v copy"

    if rtmp_url:
        # RTMP push mode with audio
        stream_mode = "rtmp"
        stream_rtmp_url = rtmp_url
        cmd = (
            f"rpicam-vid -t 0 --width {width} --height {height} "
            f"--framerate {fps} --codec libav --libav-format mpegts "
            f"-o - 2>/dev/null | "
            f"ffmpeg -re -f mpegts -thread_queue_size 512 -i pipe:0 "
            f"-f alsa -thread_queue_size 512 -ac 1 -ar 44100 -i plughw:0,0 "
            f"-map 0:v -map 1:a {video_encode} -c:a aac -b:a 128k "
            f"-f flv '{rtmp_url}'"
        )
    else:
        # HLS local mode — segments kept on disk for recording on stop
        stream_mode = "hls"
        stream_rtmp_url = None
        cmd = (
            f"rpicam-vid -t 0 --width {width} --height {height} "
            f"--framerate {fps} --codec libav --libav-format mpegts "
            f"-o - 2>/dev/null | "
            f"ffmpeg -f mpegts -thread_queue_size 512 -i pipe:0 "
            f"-f alsa -thread_queue_size 512 -ac 1 -ar 44100 -i plughw:0,0 "
            f"-map 0:v -map 1:a {video_encode} -c:a aac -b:a 96k "
            f"-f hls -hls_time 2 -hls_list_size 20 -hls_flags append_list "
            f"-hls_segment_filename '{STREAM_DIR}/seg_%05d.ts' "
            f"'{STREAM_DIR}/live.m3u8'"
        )

    stream_rec_path = None  # recording built from HLS segments on stop

    # Start HUD text updater if enabled
    if hud:
        # Write initial text so ffmpeg doesn't error on missing file
        with open(HUD_TEXTFILE, "w") as f:
            f.write("● REC 00\\:00\\:00  |  starting...  |  portal1")
        start_epoch = str(int(time.time()))
        stream_hud_proc = subprocess.Popen(
            [HUD_SCRIPT, HUD_TEXTFILE, MEDIA_DIR, start_epoch],
            preexec_fn=os.setsid
        )

    stream_proc = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
    stream_started_at = datetime.now().isoformat()

    return {
        "status": "started",
        "mode": stream_mode,
        "rtmp_url": stream_rtmp_url,
        "pid": stream_proc.pid,
        "hls_url": f"http://portal1.local:{PORT}/stream/live.m3u8" if stream_mode == "hls" else None,
    }

def stream_stop():
    """Stop streaming, build recording from segments, reinitialize camera."""
    global stream_proc, stream_mode, stream_rtmp_url, stream_started_at, stream_rec_path
    global stream_hud, stream_hud_proc

    if stream_proc is None:
        return {"status": "not_running"}

    try:
        os.killpg(os.getpgid(stream_proc.pid), signal.SIGTERM)
        stream_proc.wait(timeout=5)
    except:
        try:
            os.killpg(os.getpgid(stream_proc.pid), signal.SIGKILL)
        except:
            pass

    # Kill HUD updater
    if stream_hud_proc:
        try:
            os.killpg(os.getpgid(stream_hud_proc.pid), signal.SIGTERM)
        except:
            pass
        stream_hud_proc = None

    stopped_mode = stream_mode
    stream_proc = None
    stream_mode = None
    stream_rtmp_url = None
    stream_started_at = None
    stream_rec_path = None
    stream_hud = False

    # Reinitialize camera for snaps
    init_camera()

    result = {"status": "stopped", "was_mode": stopped_mode}

    # Build recording from HLS segments (audio + video)
    segments = sorted(glob.glob(f"{STREAM_DIR}/seg_*.ts"))
    if segments:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        mp4_path = f"{MEDIA_DIR}/stream_{ts}.mp4"
        concat_list = f"{STREAM_DIR}/concat.txt"
        try:
            with open(concat_list, "w") as f:
                for seg in segments:
                    f.write(f"file '{seg}'\n")
            subprocess.run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c", "copy", "-movflags", "+faststart", mp4_path
            ], capture_output=True, timeout=300)
            if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                result["recording"] = mp4_path
                result["size_mb"] = round(os.path.getsize(mp4_path) / 1_000_000, 1)
                if HAS_CATALOG:
                    try:
                        catalog.ingest(mp4_path, media_type="stream", move=False)
                    except:
                        pass
        except Exception as e:
            result["recording_error"] = str(e)
        finally:
            if os.path.exists(concat_list):
                os.remove(concat_list)

    # Clean up HLS segments and playlist
    for f in glob.glob(f"{STREAM_DIR}/seg_*.ts") + glob.glob(f"{STREAM_DIR}/live.m3u8"):
        try:
            os.remove(f)
        except:
            pass

    return result

def stream_status():
    """Get streaming status."""
    if stream_proc is None or stream_proc.poll() is not None:
        if stream_proc is not None:
            # Process died
            stream_stop()
        return {"streaming": False}

    elapsed = None
    if stream_started_at:
        start = datetime.fromisoformat(stream_started_at)
        elapsed = str(datetime.now() - start).split(".")[0]

    return {
        "streaming": True,
        "mode": stream_mode,
        "rtmp_url": stream_rtmp_url,
        "pid": stream_proc.pid,
        "started_at": stream_started_at,
        "elapsed": elapsed,
        "mic_muted": mic_muted,
        "hls_url": f"http://portal1.local:{PORT}/stream/live.m3u8" if stream_mode == "hls" else None,
    }

class Handler(BaseHTTPRequestHandler):
    timeout = 120

    def log_message(self, format, *args):
        pass

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/snap":
            start = time.time()
            path = snap()
            ms = int((time.time() - start) * 1000)
            if path:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("X-Capture-Ms", str(ms))
                self.end_headers()
                self.wfile.write(path.encode())
            else:
                self.send_error(500, "capture failed")

        elif parsed.path == "/snap.jpg":
            start = time.time()
            path = snap()
            ms = int((time.time() - start) * 1000)
            if path:
                with open(path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Capture-Ms", str(ms))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(500, "capture failed")

        elif parsed.path == "/clip":
            duration = min(int(params.get("duration", ["3"])[0]), 60)
            start = time.time()
            try:
                path = clip(duration_s=duration)
                ms = int((time.time() - start) * 1000)
                if path:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("X-Capture-Ms", str(ms))
                    self.end_headers()
                    self.wfile.write(path.encode())
                else:
                    self.send_response(500)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"clip failed")
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(str(e).encode())

        elif parsed.path == "/stream/start":
            rtmp_url = params.get("rtmp", [None])[0]
            hud = params.get("hud", ["0"])[0] in ("1", "true", "on")
            result = stream_start(rtmp_url=rtmp_url, hud=hud)
            status = 200 if "error" not in result else 409
            self._json_response(result, status)

        elif parsed.path == "/stream/stop":
            result = stream_stop()
            self._json_response(result)

        elif parsed.path == "/stream/status":
            self._json_response(stream_status())

        elif parsed.path == "/stream/live.m3u8":
            m3u8_path = f"{STREAM_DIR}/live.m3u8"
            if os.path.exists(m3u8_path):
                with open(m3u8_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"not ready")

        elif parsed.path.startswith("/stream/") and parsed.path.endswith(".ts"):
            seg_name = os.path.basename(parsed.path)
            seg_path = f"{STREAM_DIR}/{seg_name}"
            if os.path.exists(seg_path):
                with open(seg_path, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "video/mp2t")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

        elif parsed.path == "/stream/mic":
            mute_param = params.get("mute", ["toggle"])[0]
            if mute_param == "toggle":
                result = mic_set_mute(not mic_muted)
            else:
                result = mic_set_mute(mute_param in ("1", "true", "on"))
            self._json_response(result)

        elif parsed.path == "/storage":
            try:
                media_root = MEDIA_DIR
                usage = _shutil.disk_usage(media_root)
                free_gb = round(usage.free / (1024**3), 1)
                total_gb = round(usage.total / (1024**3), 1)
                used_pct = round((usage.used / usage.total) * 100, 1)
                self._json_response({
                    "free_gb": free_gb, "total_gb": total_gb,
                    "used_pct": used_pct, "path": media_root
                })
            except Exception as e:
                self._json_response({"error": str(e)}, 500)

        elif parsed.path == "/stream/test":
            host = self.headers.get("Host", f"192.168.1.64:{PORT}")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"""<!DOCTYPE html>
<html><body style="background:#000;color:#fff;font-family:monospace">
<div id="log" style="padding:20px;font-size:14px"></div>
<video id="v" autoplay muted playsinline style="width:100%;max-height:80vh" controls></video>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
<script>
var log = s => {{ document.getElementById('log').innerHTML += s + '<br>'; console.log(s); }};
var v = document.getElementById('v');
var url = 'http://{host}/stream/live.m3u8';
log('hls.js supported: ' + Hls.isSupported());
log('url: ' + url);
var hls = new Hls({{ manifestLoadingMaxRetry: 20, manifestLoadingRetryDelay: 1000 }});
hls.loadSource(url);
hls.attachMedia(v);
hls.on(Hls.Events.MANIFEST_PARSED, () => {{ log('MANIFEST OK - playing'); v.play(); }});
hls.on(Hls.Events.FRAG_LOADED, () => {{ log('fragment loaded'); }});
hls.on(Hls.Events.ERROR, (e,d) => {{ log('ERROR: ' + d.type + ' ' + d.details + ' fatal=' + d.fatal); }});
log('waiting for stream...');
</script></body></html>""".encode())

        elif parsed.path == "/stream/watch":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = WATCH_HTML.replace("__HOST__", self.headers.get("Host", f"192.168.1.64:{PORT}"))
            self.wfile.write(html.encode())

        elif parsed.path == "/health":
            info = {
                "status": "ok",
                "backend": "picamera2",
                "snap_ms": "~60",
                "port": PORT,
            }
            info.update(stream_status())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(info).encode())
        else:
            self.send_error(404)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

if __name__ == "__main__":
    os.makedirs(MEDIA_DIR, exist_ok=True)
    os.makedirs(STREAM_DIR, exist_ok=True)
    print(f"Camera service on port {PORT} (Picamera2 — ~60ms snaps + streaming)")
    print(f"  GET /snap           → file path")
    print(f"  GET /snap.jpg       → JPEG binary")
    print(f"  GET /clip           → MP4 file path")
    print(f"  GET /stream/start   → start HLS stream")
    print(f"  GET /stream/stop    → stop stream")
    print(f"  GET /stream/status  → stream info")
    print(f"  GET /health         → status")
    ThreadedHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
