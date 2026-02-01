# Stream Watch Page — Control Bar Redesign

## Context
Live stream viewer for Raspberry Pi camera (portal1). Viewed on mobile (iPhone Safari).
Current service: `/home/clawd/tools/camservice.py` with WATCH_HTML embedded.

## Design Principles (Jobs/Ive/Ango review)
- Viewfinder-first: video dominates, chrome disappears
- No text labels — icons only
- Hierarchy through proportion and spacing, not labels
- Touch targets minimum 44px on mobile
- Progressive disclosure

## Layout
```
┌──────────────────────────────────────────────┐
│ ═══════════════════════════════════════════○  │  Scraper
│                                              │
│  ▶  0:42 / 0:42   LIVE     🔲  🎤▎  ~18h   │  Controls
└──────────────────────────────────────────────┐
```

## Elements (left to right)

### 1. Play/Pause (left)
- ▶ / ⏸ glyph, ~10px
- Tap to toggle
- Also: tap video = play/pause

### 2. Position / Duration (left-center)
- Format: `0:42 / 0:42`
- When LIVE: both numbers match, advance together (parity)
- When scrubbed back: position falls behind duration
- Tabular-numeric font

### 3. LIVE Pill (center-left)
- Red filled when at live edge
- Dims when behind, becomes clickable to snap back
- Shows offset when behind: `-5s · LIVE`

### 4. Speaker/Volume (right cluster)
- Icon only (🔊/🔇)
- **Default: ON** (GainNode starts at 1)
- Tap to toggle mute
- Uses Web Audio GainNode (not v.muted) so analyser always gets data

### 5. Mic + Integrated VU (right cluster)
- Mic icon with internal 2px vertical bar
- Bar rises/falls with audio input level (from Web Audio analyser)
- The mic IS the meter — bar lives inside/beside the icon
- Tap to mute Pi microphone (icon dims to 30%, bar goes flat)
- ALSA control: `amixer -c 0 sset Mic cap/nocap`

### 6. Storage (far right)
- Default shows time estimate: `~18h` (free_bytes / current_bitrate)
- Tap to toggle: `~18h` → `54G` → `~18h`
- Smallest element, dim color
- No icon, just a number

## Removed
- GRID button (drop or double-tap gesture)
- FS button (double-tap video = fullscreen, standard gesture)
- All text labels ("VOL", "MIC", "GRID", "FS")
- Separate VU bar between scrubber and controls

## Gestures
- Single-tap video = play/pause
- Double-tap video = fullscreen
- Scrub bar = timeline navigation

## Technical Notes
- Audio routing: video → MediaElementSource → analyser → gainNode → speakers
- Video element is unmuted after first click (so analyser gets data)
- GainNode controls volume (not v.muted)
- HLS at 720p, 2-second segments
- ALSA capture via `plumber:0,0` (not hw:0,0)
- Mic volume set to 100%: `amixer -c 0 sset Mic 100%`
- Service: camservice.service on port 5080
