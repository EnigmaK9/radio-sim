# B4 — No Pre-Flight Checks for ffplay/ffmpeg (HIGH)

## What's wrong

The app silently fails if `ffplay` or `ffmpeg` is not on PATH:

- `player.py:42-59` — `subprocess.Popen(["ffplay", ...])` raises `FileNotFoundError`
  which is never caught. The refill thread starts, `self._process` is None, the
  loop immediately breaks, and the user gets **silence with no error**.

- `mp3.py:_launch_current()` — Same: `FileNotFoundError` from ffmpeg subprocess
  caught and re-raised as RuntimeError, but only in `_launch_current`. If
  `open()` fails, the error propagates to main and crashes. If it fails
  mid-playback (track transition), the error crashes the refill thread silently
  (daemon thread, no stack trace visible).

- `youtube.py:_fetch_metadata()` — yt-dlp subprocess failure is caught and
  returns fallback metadata, which is good. But the actual streaming pipe
  in `open()` has no error handling at all.

## Fix

### 1. Pre-flight check at startup (main.py)

```python
# main.py — before any audio work
import shutil

def _check_dependencies():
    missing = []
    if shutil.which("ffmpeg") is None:
        missing.append("ffmpeg")
    if shutil.which("ffplay") is None:
        missing.append("ffplay")
    if missing:
        click.echo(
            f"Error: {', '.join(missing)} not found on PATH. "
            f"Install with: sudo apt install ffmpeg",
            err=True,
        )
        raise SystemExit(1)

# In main():
_check_dependencies()
```

### 2. Player subprocess error handling

```python
# player.py:start()
def start(self):
    self._running = True
    try:
        self._process = subprocess.Popen(cmd, ...)
    except FileNotFoundError:
        raise RuntimeError(
            "ffplay not found. Install ffmpeg: sudo apt install ffmpeg"
        )
    ...
```

### 3. MP3 source mid-playback resilience

```python
# mp3.py:_launch_current()
def _launch_current(self):
    ...
    try:
        self._process = subprocess.Popen(cmd, ...)
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg not found. Install ffmpeg: sudo apt install ffmpeg"
        )
    except Exception as e:
        # Skip unplayable file, try next
        import sys
        print(f"Warning: Cannot decode {path.name}: {e}", file=sys.stderr)
        return self._launch_current()  # tail-recursive skip
```

### Lines changed: ~15 across 3 files

## Verification

```bash
# Temporarily hide ffmpeg and verify clean error
PATH=/usr/bin python -m src.main --mode fm --source ~/Music/ --no-tui
# Should print: "Error: ffplay not found on PATH..."
```
