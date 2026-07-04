# B5–B10 + UX — Medium/Low Severity Fixes

## B5 — TUI Flickering (MEDIUM)

**Problem:** `tui.py:80` — `live.update(self._render())` on every loop iteration (25 fps)
regardless of whether state changed. Rich's `Live` re-renders the full tree each time.
On slower terminals this causes visible flicker.

**Fix:** Only call `live.update()` when state actually changed. Add a dirty flag:

```python
# tui.py
def __init__(self, ...):
    ...
    self._dirty = True

def _handle_key(self, key):
    ...
    self._dirty = True  # set on any state mutation

# In run():
while self._running:
    key = self._poll_key()
    if key:
        self._handle_key(key)
    if self._dirty:
        live.update(self._render())
        self._dirty = False
    time.sleep(0.04)
```

The metadata loop (main.py:264-268) should also set `tui._dirty = True` on update.

**Lines changed: ~5**

---

## B6 — Headless Mode Has No Now-Playing Feedback (MEDIUM)

**Problem:** `main.py:279-300` — `_run_headless` blocks on `input()`. The user sees
nothing while audio plays. No track info, no progress, no volume indicator.

**Fix:** Print metadata changes on a background thread:

```python
def _run_headless(audio_source, pipeline, player):
    import threading, sys

    player.start()
    stop_event = threading.Event()
    last_title = ""

    def status_loop():
        nonlocal last_title
        while not stop_event.is_set():
            meta = audio_source.metadata()
            title = meta.get("title", "")
            if title != last_title:
                last_title = title
                print(f"\rNow Playing: {title} — {meta.get('artist', '')}  ", end="", file=sys.stderr)
            time.sleep(1)

    status_thread = threading.Thread(target=status_loop, daemon=True)
    status_thread.start()

    try:
        input("\nPress Enter to stop...\n")
    except (EOFError, KeyboardInterrupt):
        pass

    stop_event.set()
    player.stop()
    audio_source.close()
    print("\nRadioSim stopped.")
```

**Lines changed: ~15**

---

## B7 — Frequency Not Clamped on Mode Switch (MEDIUM)

**Problem:** When switching FM→AM in TUI, frequency stays at 101.1 MHz but AM
band is 530–1710 kHz. The frequency dial shows 101.1 kHz (valid but nonsensical
after switching from MHz).

**Fix:** In `on_mode_change`, jump to center of new band (the CLI default):

```python
def on_mode_change(new_mode):
    nonlocal radio_mode, mode
    mode = new_mode
    _mode_cell[0] = MODE_MAP[new_mode]()
    _mode_str_cell[0] = new_mode
    pipeline.flush()
    # Jump frequency to center of new band
    tui.state.frequency = MODE_DEFAULTS[new_mode]
```

**Lines changed: +1**

---

## B8 — Dead Code Removal (MEDIUM)

**Remove:**
- `main.py:40-50` — `_wrapped_processor` function, never called
- `main.py:141` — `sim_ref = [signal_sim]`, never used
- `main.py:4` — `import sys`, unused
- `tui.py:11` — `from rich.progress import BarColumn, Progress, TextColumn`, unused
- `tui.py:16` — `from src.modes.base import RadioMode`, unused
- `tui.py:17` — `from src.signal.propagation import SignalSimulator`, unused
- `tui.py:139` — `dial_width = 35`, assigned but never used

**Lines changed: -12**

---

## B9 — Duplicated Mode Info Dicts (LOW)

**Problem:** `tui.py:165-186` — `bands`, `bw`, `stereo_map`, `noise_map` are
hardcoded dicts that duplicate information already in `ModeParameters` on each
mode class.

**Fix:** Add `display_info()` method to `RadioMode` ABC:

```python
# base.py
def display_info(self) -> dict:
    unit = self.params.frequency_unit
    lo = self.params.frequency_min
    hi = self.params.frequency_max
    return {
        "band": f"{lo:.0f} – {hi:.0f} {unit}",
        "bandwidth": f"{self.params.audio_bandwidth_low:.0f} Hz – {self.params.audio_bandwidth_high:.0f} Hz",
        "stereo": "● Yes" if self.params.stereo else "○ No",
    }
```

TUI reads from `radio_mode.display_info()` instead of hardcoded dicts.

**Lines changed: +8 in base.py, -12 in tui.py**

---

## B10 — list_devices() Lies (LOW)

**Problem:** `player.py:123-130` — `list_devices()` always returns a dummy
entry `"ffplay (default output)"`. This isn't a real device list. It's
misleading to anyone calling the API.

**Fix:** Either remove the method (it's not used anywhere except the initial
import check) or make it actually check ffplay availability and return only
that boolean information:

```python
@staticmethod
def check_available() -> bool:
    """Check if ffplay is available on PATH."""
    import shutil
    return shutil.which("ffplay") is not None
```

**Lines changed: -10, +4**

---

## U1 — Graceful Missing-Dependency Errors (UX)

**Fix:** Implemented in B4 (pre-flight checks). Additional: catch `yt-dlp`
not-found in `YouTubeSource.open()` and give a clear error message instead
of a cryptic `FileNotFoundError`.

---

## U2 — Volume/RSSI Change Feedback (UX)

**Problem:** When user presses `[` or `]` to change RSSI, the value updates
in the TUI but there's no transient "pop" indicating the change registered.
Users might press the key multiple times thinking it didn't work.

**Fix:** Flash the changed value briefly with reverse-video style for 300ms:

```python
# tui.py — add flash tracking
self._flash_rssi: float | None = None  # timestamp of last rssi flash
self._flash_vol: float | None = None

# In _handle_key for RSSI/volume changes:
self._flash_rssi = time.time()

# In _render_header, check flash state:
if self._flash_rssi and time.time() - self._flash_rssi < 0.3:
    rssi_style = "reverse white on green"
else:
    rssi_style = "green"
```

**Lines changed: ~10**

---

## U5 — MP3 Source Silent Skip (UX)

**Problem:** `mp3.py` — if a file can't be decoded by ffmpeg, `_launch_current`
recursively skips to the next file. The user never knows a track was skipped.

**Fix:** Print a warning to stderr:

```python
except Exception:
    import sys
    print(f"Warning: skipping unplayable file: {path.name}", file=sys.stderr)
    return self._launch_current()
```
