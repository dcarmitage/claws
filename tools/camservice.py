#!/usr/bin/env python3
"""
agent-alpha Camera Service — persistent camera with instant capture + streaming.

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
MEDIA_DIR = "/mnt/media" if os.path.ismount("/mnt/media") else "$CLAWS_HOME/media"
STREAM_DIR = os.path.join(MEDIA_DIR, "stream")
LOCK = threading.Lock()

# Import catalog for auto-indexing
import sys
sys.path.insert(0, "$CLAWS_HOME/tools/catalog")
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
HUD_SCRIPT = "$CLAWS_HOME/tools/stream_hud.sh"
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
<title>agent-alpha</title>
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

  /* ── Dock ── */
  #dock{position:absolute;bottom:0;left:0;right:0;z-index:10;
    padding:0 14px env(safe-area-inset-bottom,10px);
    background:linear-gradient(transparent,rgba(0,0,0,.55) 40%);
    transition:opacity .4s}
  #dock.dim{opacity:.12}

  /* Scrubber */
  .track{height:32px;display:flex;align-items:center;position:relative;cursor:pointer;touch-action:none}
  .track *{pointer-events:none}
  .track-bg{position:absolute;left:0;right:0;height:4px;background:rgba(255,255,255,.12);border-radius:2px}
  .track-buf{position:absolute;height:4px;background:rgba(255,255,255,.18);border-radius:2px}
  .track-prog{position:absolute;left:0;height:4px;background:var(--rec);border-radius:2px}
  .track-head{position:absolute;top:50%;width:13px;height:13px;border-radius:50%;background:#fff;
    transform:translate(-50%,-50%);box-shadow:0 0 6px rgba(0,0,0,.5);transition:transform .1s}
  .track:active .track-head{transform:translate(-50%,-50%) scale(1.35)}
  .track-head.live{animation:pulse 1.2s ease-in-out infinite;background:var(--rec)}

  /* Controls row */
  .controls{display:flex;align-items:center;height:44px;gap:0;
    font:11px/1 var(--mono);letter-spacing:.03em}
  .ctrl-left{display:flex;align-items:center;gap:10px;flex:1;min-width:0}
  .ctrl-right{display:flex;align-items:center;gap:14px;flex-shrink:0}

  /* Play button */
  .icon-btn{background:none;border:none;cursor:pointer;padding:0;
    display:flex;align-items:center;justify-content:center;
    width:44px;height:44px;-webkit-tap-highlight-color:transparent}
  .icon-btn svg{fill:var(--hud);transition:fill .15s,opacity .15s}
  .icon-btn.muted svg{fill:var(--hud-dim);opacity:.3}

  /* Time display */
  .time{font:11px/1 var(--mono);font-variant-numeric:tabular-nums;color:var(--hud-dim);
    white-space:nowrap;letter-spacing:.02em}

  /* LIVE pill */
  .pill{padding:3px 8px;border-radius:8px;font:10px/1 var(--mono);font-weight:700;
    letter-spacing:.08em;cursor:pointer;transition:all .15s;flex-shrink:0}
  .pill-live{background:rgba(255,60,48,.75);color:#fff}
  .pill-behind{background:var(--hud-bg);color:var(--hud-dim)}

  /* Mic button with integrated VU */
  .mic-wrap{position:relative;display:flex;align-items:center}
  .mic-vu{position:absolute;right:-1px;bottom:10px;width:3px;height:20px;
    border-radius:1.5px;overflow:hidden;pointer-events:none}
  .mic-vu-bg{position:absolute;inset:0;background:rgba(255,255,255,.08);border-radius:1.5px}
  .mic-vu-fill{position:absolute;bottom:0;left:0;right:0;height:0%;
    background:var(--hud);border-radius:1.5px;transition:height 80ms linear}

  /* Storage */
  .storage{font:10px/1 var(--mono);color:var(--hud-dim);cursor:pointer;
    font-variant-numeric:tabular-nums;white-space:nowrap;min-width:28px;text-align:right;
    padding:4px 0;-webkit-tap-highlight-color:transparent}

  /* Pause flash */
  #pause-flash{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
    font-size:56px;opacity:0;transition:opacity .25s;pointer-events:none;
    text-shadow:0 2px 12px rgba(0,0,0,.5)}

  /* Audio hint */
  #audio-hint{position:absolute;bottom:80px;left:50%;transform:translateX(-50%);
    padding:6px 16px;border-radius:12px;background:rgba(0,0,0,.5);
    backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
    font:11px/1 var(--sans);color:var(--hud-dim);letter-spacing:.03em;
    pointer-events:none;z-index:8;opacity:0;transition:opacity .4s}
  #audio-hint.show{opacity:1}
  @keyframes hint-pulse{0%,100%{opacity:.5}50%{opacity:1}}
  #audio-hint.show{animation:hint-pulse 2s ease-in-out infinite}

  /* Offline */
  #offline{position:absolute;inset:0;display:flex;flex-direction:column;
    align-items:center;justify-content:center;gap:16px;z-index:5}
  #offline.hidden{display:none}
  .off-icon{font-size:48px;opacity:.15}
  .off-label{font:13px/1.4 var(--sans);color:var(--hud-dim);text-align:center;max-width:280px}
  .off-label strong{color:var(--hud);font-weight:500}
  .rec-dot{width:6px;height:6px;border-radius:50%;background:var(--rec);flex-shrink:0}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
  .rec-dot.on{animation:pulse 1.2s ease-in-out infinite}

  .off-refresh{background:none;border:none;color:var(--hud-dim);cursor:pointer;
    font:12px/1 var(--mono);padding:10px 22px;background:var(--hud-bg);border-radius:10px}
  #dbg{margin-top:16px;font:10px/1.4 monospace;color:rgba(255,255,255,0.2);
    max-height:100px;overflow:auto;text-align:left;width:80%;max-width:500px}
</style>
</head><body>
<div id="vf">
  <video id="v" autoplay muted playsinline></video>
  <svg id="grid" viewBox="0 0 300 200" preserveAspectRatio="none" style="position:absolute;inset:0;width:100%;height:100%;pointer-events:none;opacity:0;transition:opacity .3s">
    <line x1="100" y1="0" x2="100" y2="200" stroke="rgba(255,255,255,.15)" stroke-width=".5"/>
    <line x1="200" y1="0" x2="200" y2="200" stroke="rgba(255,255,255,.15)" stroke-width=".5"/>
    <line x1="0" y1="66.7" x2="300" y2="66.7" stroke="rgba(255,255,255,.15)" stroke-width=".5"/>
    <line x1="0" y1="133.3" x2="300" y2="133.3" stroke="rgba(255,255,255,.15)" stroke-width=".5"/>
  </svg>

  <div id="dock">
    <div class="track" id="track">
      <div class="track-bg"></div>
      <div class="track-buf" id="tbuf"></div>
      <div class="track-prog" id="tprog"></div>
      <div class="track-head" id="thead"></div>
    </div>
    <div class="controls">
      <div class="ctrl-left">
        <!-- Play/Pause -->
        <button class="icon-btn" id="play-btn" onclick="togglePlay()">
          <svg id="play-icon" width="10" height="12" viewBox="0 0 10 12"><polygon points="0,0 10,6 0,12"/></svg>
          <svg id="pause-icon" width="10" height="12" viewBox="0 0 10 12" style="display:none"><rect x="0" y="0" width="3" height="12"/><rect x="7" y="0" width="3" height="12"/></svg>
        </button>
        <div class="rec-dot" id="rdot"></div>
        <!-- Position / Duration -->
        <span class="time" id="rtime">0:00</span>
        <!-- LIVE pill -->
        <span class="pill pill-live" id="lpill" onclick="goLive()">LIVE</span>
      </div>
      <div class="ctrl-right">
        <!-- Speaker -->
        <button class="icon-btn" id="vol-btn" onclick="toggleVol()">
          <svg width="18" height="18" viewBox="0 0 24 24"><path id="vol-path" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>
        </button>
        <!-- Mic with VU -->
        <div class="mic-wrap">
          <button class="icon-btn" id="mic-btn" onclick="toggleMic()">
            <svg width="16" height="18" viewBox="0 0 24 24"><path id="mic-path" d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg>
          </button>
          <div class="mic-vu">
            <div class="mic-vu-bg"></div>
            <div class="mic-vu-fill" id="mic-vu-fill"></div>
          </div>
        </div>
        <!-- Storage -->
        <div class="storage" id="storage" onclick="toggleStorage()">--</div>
      </div>
    </div>
  </div>

  <div id="pause-flash">&#10074;&#10074;</div>

  <div id="audio-hint">tap to enable audio</div>
  <div id="offline">
    <div class="off-icon">&#127744;</div>
    <div class="off-label"><strong>agent-alpha</strong> is idle<br>
      <span id="off-sub">Send <code>/stream start</code> to go live</span></div>
    <button class="off-refresh" onclick="location.reload()">&#x21bb; refresh</button>
    <pre id="dbg"></pre>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
<script>
const $ = id => document.getElementById(id);
const v = $('v'), HOST = '__HOST__';
const streamUrl = `http://${HOST}/stream/live.m3u8`;
function dbg(s) { console.log(s); const el=$('dbg'); if(el) el.textContent += s + '\n'; }

let hls, active = false, dimTimer;
let dragging = false, mode = 'live';
let serverElapsed = 0;
let micMuted = false;
let storageMode = 'time'; // 'time' or 'gb'
let storageFreeBytes = 0, storageFreeGb = '--', storageUsedPct = 0;
const BITRATE_ESTIMATE = 2600 * 1024 / 8; // ~2600kbps stream → bytes/sec

// ── Audio ──
let audioCtx, analyser, audioSrc, gainNode, audioReady = false;
let speakerOn = true; // default ON per spec

function initAudio() {
  if (audioReady) return;
  try {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.5;
    gainNode = audioCtx.createGain();
    gainNode.gain.value = 1; // default ON
    audioSrc = audioCtx.createMediaElementSource(v);
    audioSrc.connect(analyser);
    analyser.connect(gainNode);
    gainNode.connect(audioCtx.destination);
    v.muted = false;
    audioReady = true;
    $('audio-hint').classList.remove('show');
    updateVolUI();
    dbg('audio ok');
  } catch(e) { dbg('audio: ' + e.message); }
}

function ensureAudio() {
  initAudio();
  if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
  $('audio-hint').classList.remove('show');
}

// ── VU meter (mic icon vertical bar) ──
let vuLevel = 0;
const vuFill = $('mic-vu-fill');
function updateVU() {
  requestAnimationFrame(updateVU);
  if (!active || !analyser || micMuted) { vuFill.style.height = '0%'; return; }
  const data = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(data);
  let sum = 0;
  for (let i = 0; i < data.length; i++) sum += data[i];
  const avg = sum / data.length / 255;
  vuLevel += (avg - vuLevel) * 0.35;
  const pct = Math.min(100, Math.round(vuLevel * 250));
  vuFill.style.height = pct + '%';
  if (pct > 85) vuFill.style.background = 'var(--rec)';
  else if (pct > 60) vuFill.style.background = 'var(--amber)';
  else vuFill.style.background = 'var(--hud)';
}
requestAnimationFrame(updateVU);

// ── HLS ──
function init() {
  if (hls) { hls.destroy(); hls = null; }
  mode = 'live';
  if (!Hls.isSupported()) { v.src = streamUrl; v.play(); return; }
  hls = new Hls({
    liveSyncDurationCount: 2,
    liveMaxLatencyDurationCount: 5,
    backBufferLength: 30,
    maxBufferLength: 8,
    maxMaxBufferLength: 15,
    manifestLoadingMaxRetry: 30,
    manifestLoadingRetryDelay: 500,
    levelLoadingRetryDelay: 500,
    fragLoadingRetryDelay: 500,
  });
  hls.loadSource(streamUrl);
  hls.attachMedia(v);
  hls.on(Hls.Events.MANIFEST_PARSED, () => {
    dbg('manifest ok');
    v.play().catch(e => dbg('play: ' + e.message));
    setActive(true);
    setTimeout(() => setMode('live'), 600);
  });
  hls.on(Hls.Events.FRAG_LOADED, () => { if (!active) setActive(true); });
  hls.on(Hls.Events.ERROR, (_, d) => {
    dbg('hls ' + (d.fatal?'FATAL ':'') + d.details);
    if (d.fatal) { hls.destroy(); hls = null; }
  });
  hls.on(Hls.Events.BUFFER_STALLED_EVENT, () => {
    dbg('buffer stall');
    if (mode === 'live' && hls.liveSyncPosition) {
      v.currentTime = hls.liveSyncPosition;
    }
  });
  hls.on(Hls.Events.FRAG_BUFFERED, () => {
    if (active && v.paused && mode === 'live') {
      v.play().catch(() => {});
    }
  });
  dbg('hls init');
}

function setActive(on, msg) {
  active = on;
  $('offline').classList.toggle('hidden', on);
  $('dock').style.display = on ? '' : 'none';
  if (on) { $('rdot').classList.add('on'); resetDim();
    if (!audioReady) $('audio-hint').classList.add('show');
  } else { $('rdot').classList.remove('on');
    if (msg) $('off-sub').textContent = msg;
    v.pause(); if (hls) { hls.destroy(); hls = null; }
    v.removeAttribute('src'); v.load();
  }
  updatePlayUI();
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
function fmtTime(s) {
  s = Math.max(0, Math.floor(s));
  const m = Math.floor(s / 60), sec = s % 60;
  return m + ':' + String(sec).padStart(2, '0');
}
function fmtElapsed(s) {
  if (s < 0) s = 0;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return h + ':' + String(m).padStart(2,'0') + ':' + String(sec).padStart(2,'0');
  return m + ':' + String(sec).padStart(2,'0');
}

// ── Play/Pause ──
function updatePlayUI() {
  const playing = active && !v.paused;
  $('play-icon').style.display = playing ? 'none' : '';
  $('pause-icon').style.display = playing ? '' : 'none';
}
function togglePlay() {
  ensureAudio();
  if (v.paused) {
    v.play();
    if (mode === 'paused') { if (hls) hls.config.liveSyncDuration = 999999; setMode('rewind'); }
  } else {
    v.pause();
    if (hls) hls.config.liveSyncDuration = 999999;
    setMode('paused');
    flash();
  }
  updatePlayUI();
}

function flash() {
  $('pause-flash').style.opacity = '1';
  setTimeout(() => $('pause-flash').style.opacity = '0', 600);
}

// Tap video = play/pause, double-tap = fullscreen, triple-tap = grid
let tapCount = 0, tapTimer = null;
v.addEventListener('click', e => {
  if (e.target !== v) return;
  tapCount++;
  clearTimeout(tapTimer);
  tapTimer = setTimeout(() => {
    if (tapCount === 1) { ensureAudio(); togglePlay(); }
    else if (tapCount === 2) {
      if (document.fullscreenElement) document.exitFullscreen();
      else $('vf').requestFullscreen().catch(() => {});
    }
    else if (tapCount >= 3) {
      const g = $('grid');
      g.style.opacity = g.style.opacity === '1' ? '0' : '1';
    }
    tapCount = 0;
  }, 350);
});
v.addEventListener('play', () => { $('pause-flash').style.opacity = '0'; updatePlayUI(); });
v.addEventListener('pause', updatePlayUI);
v.addEventListener('playing', () => { if (!active) setActive(true); updatePlayUI(); });

function goLive() {
  if (hls) {
    delete hls.config.liveSyncDuration;
    if (hls.liveSyncPosition) v.currentTime = hls.liveSyncPosition;
  }
  if (v.paused) v.play();
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
  const pos = avail > 0.5 ? Math.max(0, Math.min(1, (v.currentTime - start) / avail)) : 1;

  // Time display: elapsed from server + behind offset
  if (mode === 'live') {
    $('rtime').textContent = fmtElapsed(serverElapsed);
  } else {
    const behindStr = behind < 1 ? '' : behind < 60 ? ' \u00b7 -' + Math.round(behind) + 's' : ' \u00b7 -' + Math.floor(behind/60) + ':' + String(Math.floor(behind%60)).padStart(2,'0');
    $('rtime').textContent = fmtElapsed(serverElapsed) + behindStr;
  }

  // Buffer bar
  $('tbuf').style.left = '0%'; $('tbuf').style.width = '100%';

  // Scrubber position
  if (mode === 'live' && !dragging) {
    $('tprog').style.width = '100%';
    $('thead').style.left = '100%';
    $('thead').classList.add('live');
  } else {
    $('thead').classList.remove('live');
    if (avail > 1) {
      const pos = Math.max(0, Math.min(1, (v.currentTime - start) / avail));
      $('tprog').style.width = (pos * 100) + '%';
      $('thead').style.left = (pos * 100) + '%';
    }
    // Show behind offset on LIVE pill
    $('lpill').textContent = (mode==='paused'?'\u23F8 ':'') + fmtBehind(behind) + ' \u00b7 LIVE';
  }

  // Auto-detect drift from live edge
  if (mode === 'live' && !dragging && behind > 4) {
    setMode('rewind');
  }
  // Auto-return to live when caught up
  if (mode !== 'live' && mode !== 'paused' && !dragging && behind < 2) {
    setMode('live');
  }
}
requestAnimationFrame(render);

// ── Volume ──
function updateVolUI() {
  const path = $('vol-path');
  if (speakerOn) {
    path.setAttribute('d', 'M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z');
    $('vol-btn').querySelector('svg').style.fill = 'var(--hud)';
  } else {
    path.setAttribute('d', 'M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z');
    $('vol-btn').querySelector('svg').style.fill = 'var(--hud-dim)';
  }
}
function toggleVol() {
  ensureAudio();
  speakerOn = !speakerOn;
  if (gainNode) gainNode.gain.value = speakerOn ? 1 : 0;
  updateVolUI();
}

// ── Mic ──
async function toggleMic() {
  try {
    const r = await fetch(`http://${HOST}/stream/mic?mute=${micMuted?'0':'1'}`);
    const d = await r.json();
    micMuted = d.muted;
    updateMicUI();
  } catch(e) { dbg('mic: '+e.message); }
}
function updateMicUI() {
  const btn = $('mic-btn');
  btn.classList.toggle('muted', micMuted);
  const path = $('mic-path');
  if (micMuted) {
    path.setAttribute('d', 'M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zm-4.02.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3L3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l1.66 1.66c-.71.33-1.5.52-2.31.52-2.76 0-5.3-2.1-5.3-5.1H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c.91-.13 1.77-.45 2.54-.9L19.73 21 21 19.73 4.27 3z');
  } else {
    path.setAttribute('d', 'M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z');
  }
}

// ── Storage ──
function fmtStorageTime(freeBytes) {
  if (!freeBytes || freeBytes <= 0) return '--';
  const secs = freeBytes / BITRATE_ESTIMATE;
  if (secs < 3600) return '~' + Math.round(secs / 60) + 'm';
  if (secs < 86400) return '~' + Math.round(secs / 3600) + 'h';
  return '~' + Math.round(secs / 86400) + 'd';
}
function renderStorage() {
  const el = $('storage');
  if (storageMode === 'time') {
    el.textContent = fmtStorageTime(storageFreeBytes);
  } else {
    el.textContent = storageFreeGb + 'G';
  }
}
function toggleStorage() { storageMode = storageMode === 'time' ? 'gb' : 'time'; renderStorage(); }

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
      if (d.elapsed_seconds !== undefined) serverElapsed = d.elapsed_seconds;
      if (!hls) { dbg('stream detected'); init(); }
      if (d.mic_muted !== undefined && d.mic_muted !== micMuted) { micMuted = d.mic_muted; updateMicUI(); }
      if (!active) $('off-sub').textContent = 'Connecting\u2026';
    } else {
      if (active) setActive(false, 'Stream ended');
    }
  } catch(e) { if (active) setActive(false, 'Connection lost'); }
}
async function pollStorage() {
  try {
    const r = await fetch(`http://${HOST}/storage`);
    const d = await r.json();
    storageFreeGb = d.free_gb;
    storageFreeBytes = d.free_bytes || d.free_gb * 1073741824;
    storageUsedPct = d.used_pct;
    renderStorage();
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
            f.write("● REC 00\\:00\\:00  |  starting...  |  agent-alpha")
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
        "hls_url": f"http://agent-alpha.local:{PORT}/stream/live.m3u8" if stream_mode == "hls" else None,
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
    elapsed_seconds = None
    if stream_started_at:
        start = datetime.fromisoformat(stream_started_at)
        delta = datetime.now() - start
        elapsed = str(delta).split(".")[0]
        elapsed_seconds = int(delta.total_seconds())

    return {
        "streaming": True,
        "mode": stream_mode,
        "rtmp_url": stream_rtmp_url,
        "pid": stream_proc.pid,
        "started_at": stream_started_at,
        "elapsed": elapsed,
        "elapsed_seconds": elapsed_seconds,
        "mic_muted": mic_muted,
        "hls_url": f"http://agent-alpha.local:{PORT}/stream/live.m3u8" if stream_mode == "hls" else None,
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
                stat = os.statvfs(media_root)
                self._json_response({
                    "free_gb": free_gb, "total_gb": total_gb,
                    "used_pct": used_pct, "path": media_root,
                    "free_bytes": int(stat.f_bfree * stat.f_frsize)
                })
            except Exception as e:
                self._json_response({"error": str(e)}, 500)

        elif parsed.path == "/stream/test":
            host = self.headers.get("Host", f"<your-agent-ip>:{PORT}")
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
            html = WATCH_HTML.replace("__HOST__", self.headers.get("Host", f"<your-agent-ip>:{PORT}"))
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
