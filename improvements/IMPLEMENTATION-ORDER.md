# Implementation Order

Fix in this sequence. Each step is self-contained and testable.

## Phase 1 — Critical: Audio Correctness (B1, B2, B3, B4)

**These make the app produce wrong audio or crash.**

| Step | Issue | Files | Lines | Time |
|------|-------|-------|-------|------|
| 1 | B1 — FM stereo blend inverted | `fm.py` | 1 | 2 min |
| 2 | B2 — Double degradation: remove extra processor | `main.py` | -3 | 5 min |
| 3 | B3 — RSSI intensity inverted (5 locations) | `propagation.py`, `am.py` | 5 | 5 min |
| 4 | B4 — Player thread race on _process | `player.py` | 4 | 5 min |

**Verify:** Strong FM signal = stereo (not mono). AM weak signal = crackly (not clean).
Audio matches expected RSSI behavior. No race crashes on Ctrl+C.

---

## Phase 2 — High: Broken UX & Artifacts (B5, B6, B7, B8)

**Fix things that users see and hear.**

| Step | Issue | Files | Lines | Time |
|------|-------|-------|-------|------|
| 5 | B5 — Wire N key, remove dead Space/S keys | `tui.py`, `main.py` | ~15 | 15 min |
| 6 | B6 — Pink noise persistent state (no clicks) | `noise.py`, `propagation.py` | ~24 | 15 min |
| 7 | B7 — Pre-flight checks ffmpeg/ffplay | `main.py`, `player.py` | ~15 | 10 min |
| 8 | B8 — Arrow key robustness across terminals | `tui.py` | ~20 | 15 min |

**Verify:** N key skips track. No 23ms click artifacts. Missing ffmpeg → clean error.
Arrows work in tmux.

---

## Phase 3 — Polish: TUI & Headless UX (B9–B11, U2–U5)

| Step | Issue | Files | Lines | Time |
|------|-------|-------|-------|------|
| 9 | B9 — Remove double-buffering | `pipeline.py`, `player.py` | ~25 | 15 min |
| 10 | B10 — Flicker reduction (dirty flag) | `tui.py` | +5 | 5 min |
| 11 | B11 — Headless now-playing display | `main.py` | +15 | 10 min |
| 12 | U2 — RSSI/Volume flash feedback | `tui.py` | +10 | 10 min |
| 13 | U3 — Frequency clamp on mode switch | `main.py` | +1 | 1 min |
| 14 | U4 — RSSI dead zone -20 to -10 | `propagation.py` | 1 | 1 min |
| 15 | U5 — Skip warnings for bad files | `mp3.py` | +3 | 2 min |

---

## Phase 4 — Cleanup (B12–B15)

| Step | Issue | Files | Lines | Time |
|------|-------|-------|-------|------|
| 16 | B12 — Dead code removal | `main.py`, `tui.py` | -12 | 5 min |
| 17 | B13 — FMHD subchannel filter cache | `fmhd.py` | +5 | 5 min |
| 18 | B14 — AMMode pink noise normalization fix | `am.py` | 3 | 5 min |
| 19 | B15 — MP3Source metadata lock | `mp3.py` | +5 | 5 min |

---

## Total

| Metric | Before | After |
|--------|--------|-------|
| Bugs fixed | 0 | **15** |
| Critical | 0 | **4** (stereo inverted, double noise, RSSI inverted, thread race) |
| High | 0 | **4** (dead keys, pink noise clicks, no ffmpeg check, arrow fragility) |
| Medium/Low | 0 | **7** |
| UX improvements | 0 | **5** |
| Lines delta | 0 | **~+100/-20 net +80** |
| Estimated time | — | **~2.5 hours** |

