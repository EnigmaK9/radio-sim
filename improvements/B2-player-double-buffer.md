# B2 — Player Double-Buffering Waste (HIGH)

## What's wrong

`player.py:102-108` — The refill loop calls `push_chunk()` (which runs source→processors→buffer)
and then immediately calls `pop_chunk()` to read it back. The ring buffer is never consumed
by a separate thread — the producer is also the consumer.

```python
# player.py:102-108
ok = self.pipeline.push_chunk()  # source → processors → buffer
if not ok:
    time.sleep(0.1)
    continue
chunk = self.pipeline.pop_chunk()  # immediately read back
```

This means:
1. The ring buffer's `buffer_fill` is always 0 or 1 — the "32 chunks" capacity is never used
2. The TUI's buffer fill indicator is misleading (always shows 0/32 or 1/32)
3. Memory for 32 chunks (~128 KB) is allocated but wasted
4. If the source blocks briefly, playback glitches — no buffering to absorb it

## Root cause

The original design was for PyAudio callback mode: the audio callback thread
would `pop_chunk()` independently. When we switched to ffplay subprocess,
the separate consumer thread disappeared, but the ring buffer stayed.

## Fix

**Option A (recommended):** Have `push_chunk` return the processed chunk directly
instead of storing it in the buffer. Remove the buffer entirely.

```python
# pipeline.py — add direct processing method
def process_chunk(self) -> tuple[bool, np.ndarray]:
    """Read from source, run processors, return processed chunk.
    Returns (ok, chunk)."""
    if self.source is None:
        return True, np.zeros((self.chunk_size, self.channels), dtype=np.float32)
    raw = self.source.read_chunk(self.chunk_size)
    if raw is None:
        return False, np.zeros((self.chunk_size, self.channels), dtype=np.float32)
    processed = raw.astype(np.float32)
    for proc in self._processors:
        processed = proc(processed)
    processed = np.clip(processed, -1.0, 1.0)
    return True, self._resize_chunk(processed)
```

```python
# player.py — simplified refill loop
def _refill_loop(self):
    while self._running:
        if self._process is None or self._process.poll() is not None:
            break
        ok, chunk = self.pipeline.process_chunk()
        if not ok:
            time.sleep(0.1)
            continue
        chunk = chunk * self.volume
        int_data = (np.clip(chunk, -1, 1) * 32767).astype(np.int16).tobytes()
        try:
            self._process.stdin.write(int_data)
        except (BrokenPipeError, OSError):
            break
```

### Lines changed: ~15 in pipeline.py, ~10 in player.py

## Alternative

Keep the ring buffer for its original purpose (jitter absorption) but only
if we later add a separate consumer. For now, Option A is the right call.

## Verification

```bash
python -m src.main --mode fm --freq 101.1 --source ~/Music/ --no-tui
# Should play without stutter. Check CPU usage is not higher than before.
```
