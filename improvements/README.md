# RadioSim — Quality Improvement Plan

Bug fixes, UX hardening, and TUI polish. No new features. No line-count bloat.

## Issue Summary

| # | Severity | Area | What |
|---|----------|------|------|
| B1 | **Critical** | Modes | FM stereo blend formula inverted — strong=mono, weak=stereo |
| B2 | **Critical** | Engine | Double degradation — mode + signal_sim both add noise |
| B3 | **Critical** | Signal | RSSI effect intensity inverted — strong signal gets MORE noise/fading |
| B4 | **Critical** | Engine | Player thread race on `self._process` — crash on stop |
| B5 | **High** | TUI | N/Space/S keys advertised but dead — no callbacks wired |
| B6 | **High** | Signal | `pink_noise()` fresh state per chunk — audible clicks @ 23ms |
| B7 | **High** | Engine | No ffplay/ffmpeg pre-flight check — silent failures |
| B8 | **High** | TUI | Arrow key escape sequences fragile across terminals |
| B9 | **Medium** | Engine | Player double-buffering — push+pop in same thread, buffer wasted |
| B10 | **Medium** | TUI | Flickering — re-render every frame even when idle |
| B11 | **Medium** | CLI | Headless mode silent — no now-playing feedback |
| B12 | **Medium** | Engine | Dead code: _wrapped_processor, unused imports |
| B13 | **Medium** | Modes | FMHD subchannel filter not cached — recomputed every chunk |
| B14 | **Low** | Signal | AMMode pink noise per-chunk normalization causes level jumps |
| B15 | **Low** | Sources | MP3Source metadata race between refill & metadata threads |
| U1 | **UX** | All | No graceful error when ffmpeg/ffplay/yt-dlp missing |
| U2 | **UX** | TUI | Volume/RSSI changes have no transient visual feedback |
| U3 | **UX** | TUI | Frequency drifts out of band on mode switch, no clamp |
| U4 | **UX** | TUI | RSSI dead zone from -20 to -10 dBm |
| U5 | **UX** | Sources | MP3 source silently skips unplayable files |
