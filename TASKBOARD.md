# TASKBOARD.md — Stream UI Final Polish

## Orchestration Method

**Orchestrator:** Main session (me). Maintains this file, spawns builders, verifies results.
**Builders:** Sub-agents. Each gets ONE task, fresh context, clear input/output contract.
**Flow:** Orchestrator updates TASKBOARD → spawns builder → builder completes + commits → orchestrator verifies → updates TASKBOARD → next task.

## Dependency Graph

```
Task 1: Server endpoints (Python only)
  ↓
Task 2: Time display (JS — depends on elapsed_seconds from Task 1)
  ↓
Task 3: Mic icon slash (JS/SVG — independent, but builds on Task 2's HTML)
  ↓
Task 4: Audio init UX (JS/CSS — independent, but builds on Task 3's HTML)
  ↓
Task 5: Scrubber + rec dot polish (CSS/JS — builds on Task 4's HTML)
  ↓
Task 6: Visual QA (orchestrator reviews, no sub-agent)
```

## Baseline
- **Commit:** `af94b7f` — redesigned control bar UI (known good)
- **File:** `/home/clawd/tools/camservice.py`

## Tasks

### Task 1: Server endpoint additions ✅ (4387988)
**Scope:** Python only. Do NOT touch WATCH_HTML.
**Changes:**
- In `storage_info()`: add `"free_bytes": int(stat.f_bfree * stat.f_frsize)` to response dict
- In `stream_status()`: when streaming, add `"elapsed_seconds": int(elapsed.total_seconds())` to response dict (elapsed is already computed as `datetime.now() - stream_started_at`)
**Validate:**
```bash
python3 -c "import ast; ast.parse(open('/home/clawd/tools/camservice.py').read()); print('valid')"
sudo systemctl restart camservice
curl -s http://localhost:5080/storage | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'free_bytes' in d and isinstance(d['free_bytes'], int), f'FAIL: {d}'; print('PASS:', d)"
curl -s http://localhost:5080/stream/start > /dev/null; sleep 2
curl -s http://localhost:5080/stream/status | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'elapsed_seconds' in d and isinstance(d['elapsed_seconds'], int), f'FAIL: {d}'; print('PASS:', d)"
curl -s http://localhost:5080/stream/stop > /dev/null
```
**Commit:** `task 1: add free_bytes and elapsed_seconds to server endpoints`

### Task 2: Time display rewrite ✅ (7b7dde8)
**Scope:** WATCH_HTML JavaScript only.
**Depends on:** Task 1 (elapsed_seconds in status endpoint)
**Changes:**
- Add server elapsed tracking: poll `/stream/status` every 2s, store `elapsed_seconds` in a JS variable
- Replace the time display format. Currently: `fmtTime(v.currentTime - start) + ' / ' + fmtTime(avail)`. New behavior:
  - When LIVE: show `● 5:51` — a pulsing red dot + total elapsed recording time
  - When behind (scrubbed back): show `● 5:51 · -12s` — elapsed + how far behind live edge
  - The red dot pulses using CSS animation when streaming
- Remove dependency on buffer length for "duration" — use server elapsed_seconds instead
**Validate:**
```bash
python3 -c "import ast; ast.parse(open('/home/clawd/tools/camservice.py').read()); print('valid')"
sudo systemctl restart camservice
```
Then manually: start stream, open watch page, verify time shows elapsed, scrub back, verify offset appears.
**Commit:** `task 2: time display shows elapsed + behind offset`

### Task 3: Mic muted icon swap ✅ (1f9ee97)
**Scope:** WATCH_HTML only (SVG + JS).
**Depends on:** Task 2 (HTML structure)
**Changes:**
- When mic is muted: swap the mic SVG path to Material Icons mic-off (diagonal slash through mic)
- When mic is unmuted: show normal mic icon
- Additionally: dim the entire mic-wrap to opacity 0.3 when muted
- The VU bar fill should go to 0% height when muted (already implemented)
**Mic-off SVG path (Material Icons):** `M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zm-4.02.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3L3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l1.66 1.66c-.71.33-1.5.52-2.31.52-2.76 0-5.3-2.1-5.3-5.1H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c.91-.13 1.77-.45 2.54-.9L19.73 21 21 19.73 4.27 3z`
**Normal mic SVG path (already in code):** `M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z`
**Validate:**
```bash
python3 -c "import ast; ast.parse(open('/home/clawd/tools/camservice.py').read()); print('valid')"
sudo systemctl restart camservice
```
Then: start stream, open watch page, click mic to mute, verify icon changes to slashed version + dims.
**Commit:** `task 3: mic icon swaps to slashed SVG when muted`

### Task 4: Audio initialization UX ✅ (55413f3)
**Scope:** WATCH_HTML only (CSS + JS).
**Depends on:** Task 3 (HTML structure)
**Changes:**
- Add a small, subtle overlay hint that appears on load: a semi-transparent pill at bottom-center saying "tap to enable audio" with a gentle pulse animation
- The hint sits ABOVE the dock, doesn't interfere with controls
- On first user interaction (click/touch/pointer), the hint fades out and `ensureAudio()` fires
- After audio inits, the hint is permanently removed (display:none)
- If AudioContext fails, hint changes to "audio unavailable" briefly then fades
**Validate:**
```bash
python3 -c "import ast; ast.parse(open('/home/clawd/tools/camservice.py').read()); print('valid')"
sudo systemctl restart camservice
```
Then: open watch page fresh (incognito), verify hint appears, tap anywhere, verify hint disappears and audio activates.
**Commit:** `task 4: audio init hint appears until first tap`

### Task 5: Scrubber + recording dot polish ✅ (18e5f45)
**Scope:** WATCH_HTML only (CSS + JS).
**Depends on:** Task 4 (HTML structure)
**Changes:**
- Increase scrubber track height from 3px to 4px
- When at live edge (mode === 'live'), add a subtle red pulse animation to the scrubber head (same keyframe as rec-dot: opacity 1 → 0.3 → 1, 1.2s ease-in-out)
- When NOT at live edge, scrubber head is static white (no pulse)
- Add a small recording dot (6px red circle) to the left of the time display that pulses when streaming (already in the CSS from earlier versions — re-add it)
- Triple-tap video = toggle rule-of-thirds grid overlay (reuse the SVG grid from earlier versions)
**Validate:**
```bash
python3 -c "import ast; ast.parse(open('/home/clawd/tools/camservice.py').read()); print('valid')"
sudo systemctl restart camservice
```
Then: start stream, verify rec dot pulses, verify scrubber head pulses at live edge, scrub back and verify pulse stops, triple-tap for grid.
**Commit:** `task 5: scrubber polish + recording dot + grid gesture`

### Task 6: Final QA ✅ (orchestrator)
**Scope:** Orchestrator (me) reviews the complete result.
**No sub-agent needed.**
- Read final HTML
- Start stream, verify all features
- Screenshot for documentation
- Update LEARN.md with results
- Final git commit + tag

## Status Log
- `af94b7f` — baseline (known good UI)
- `4387988` — task 1: server endpoints (free_bytes + elapsed_seconds)
- `7b7dde8` — task 2: time display (elapsed + behind offset)
- `1f9ee97` — task 3: mic icon slash SVG swap
- `55413f3` — task 4: audio init hint
- `18e5f45` — task 5: scrubber polish + grid gesture
- QA pass: 13/13 feature checks, endpoints verified, audio+video confirmed
