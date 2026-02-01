# TASKBOARD v2 — Live Sync Fix

## Problem
Stream viewer has: scrubber bouncing, weird pausing, not synced with real time.

## Root Causes
1. HLS config missing live-sync tuning — player doesn't know how to stay at live edge
2. Manual `v.currentTime = buffered.end - 0.5` forces player too close to edge, causing stalls
3. Scrubber position calculated from shifting buffer boundaries = jitter

## Baseline
- **Commit:** `1abf0c7` (v1.0-stream-ui tag)
- **File:** `/home/clawd/tools/camservice.py` (WATCH_HTML only)

## Tasks

### Task 1: HLS config tuning ⬜
**Scope:** WATCH_HTML JS only — the `new Hls({...})` config object.
**Changes:** Replace the HLS config with properly tuned live settings:
```javascript
hls = new Hls({
  // Live edge: stay 2 segments behind (4s with 2s segments)
  liveSyncDurationCount: 2,
  // Max drift: if >5 segments behind, force catch-up
  liveMaxLatencyDurationCount: 5,
  // Keep 30s of back-buffer for scrubbing
  backBufferLength: 30,
  // Buffer limits
  maxBufferLength: 8,
  maxMaxBufferLength: 15,
  // Retry settings
  manifestLoadingMaxRetry: 30,
  manifestLoadingRetryDelay: 500,
  levelLoadingRetryDelay: 500,
  fragLoadingRetryDelay: 500,
});
```

Also remove the aggressive initial seek. In the `MANIFEST_PARSED` handler, replace:
```javascript
setTimeout(() => {
  if (v.buffered.length) v.currentTime = v.buffered.end(v.buffered.length - 1) - 0.5;
  setMode('live');
}, 600);
```
With just:
```javascript
setTimeout(() => setMode('live'), 600);
```
Let hls.js handle the live edge position via liveSyncDurationCount.

Also fix `goLive()` — replace the manual seek with hls.js live sync:
```javascript
function goLive() {
  if (hls) {
    // Reset live sync so hls.js manages the edge
    delete hls.config.liveSyncDuration;
    hls.liveSyncPosition && (v.currentTime = hls.liveSyncPosition);
  }
  if (v.paused) v.play();
  setMode('live');
}
```

**Validate:** python ast parse + restart camservice
**Commit:** `fix 1: HLS live sync tuning`

### Task 2: Scrubber stability ⬜
**Scope:** WATCH_HTML JS only — the `render()` function.
**Changes:**

The render function needs to handle live mode differently from scrub-back mode:

Replace the scrubber positioning logic in render() with:
```javascript
// Scrubber positioning
if (mode === 'live' && !dragging) {
  // Pin to right edge — don't calculate from buffer
  $('tprog').style.width = '100%';
  $('thead').style.left = '100%';
  $('thead').classList.add('live');
} else {
  $('thead').classList.remove('live');
  // Calculate position relative to buffer, with smoothing
  if (avail > 1) {
    const pos = Math.max(0, Math.min(1, (v.currentTime - start) / avail));
    $('tprog').style.width = (pos * 100) + '%';
    $('thead').style.left = (pos * 100) + '%';
  }
}
```

Also: when mode is 'live', auto-detect if we've fallen behind. Add this check in render():
```javascript
// Auto-detect if we've drifted from live edge
if (mode === 'live' && !dragging && behind > 4) {
  // We've drifted — let hls.js resync rather than showing stale position
  setMode('rewind');
}
```

And when behind < 2, auto-return to live:
```javascript
if (mode !== 'live' && !dragging && behind < 2) {
  setMode('live');
}
```

**Validate:** python ast parse + restart camservice
**Commit:** `fix 2: scrubber stability for live streams`

### Task 3: Smooth playback recovery ⬜
**Scope:** WATCH_HTML JS only.
**Changes:**

Add an hls.js event handler for buffer stalls. After the existing ERROR handler, add:
```javascript
hls.on(Hls.Events.BUFFER_STALLED_EVENT, () => {
  dbg('buffer stall — seeking to sync position');
  if (mode === 'live' && hls.liveSyncPosition) {
    v.currentTime = hls.liveSyncPosition;
  }
});
```

Also, handle the `FRAG_BUFFERED` event to auto-play if paused due to stall:
```javascript
hls.on(Hls.Events.FRAG_BUFFERED, () => {
  if (active && v.paused && mode === 'live') {
    v.play().catch(() => {});
  }
});
```

**Validate:** python ast parse + restart camservice
**Commit:** `fix 3: smooth playback recovery on stalls`

### Task 4: QA ⬜
**Scope:** Orchestrator verifies everything.

## Methodology Note
Each task modifies only WATCH_HTML JavaScript. No Python changes.
One sub-agent per task. Verify between each.
