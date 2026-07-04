# B5–B8 — High Severity Fixes

## B5 — Dead Keys: N, Space, S (TUI)

**File:** `src/ui/tui.py:242-281`

Three keyboard shortcuts advertised in the footer but wired to no-ops:

| Key | Footer text | Code | What happens |
|-----|------------|------|-------------|
| N | `[N]ext` | `pass` (line 243) | Nothing |
| Space | `[Space]Play` | toggles `self.state.playing` (line 245) | Variable flipped, nobody reads it |
| S | `[S]ource` | cycles `self.state.source_type` string (line 281) | String toggled, source unchanged |

### Fix

**N key — wire to source.advance_track():**

Add `on_next_track` callback to TUI and wire it in main.py:

```python
# tui.py — add callback parameter
def __init__(self, ..., on_next_track=None):
    self._on_next_track = on_next_track or (lambda: None)

# tui.py — handle key
elif key in ("n", "N"):
    self._on_next_track()
    self._dirty = True

# main.py — wire callback
def on_next_track():
    audio_source.advance_track()

tui = RadioTUI(..., on_next_track=on_next_track)
```

**Space key — remove from footer or implement pause:**

There's no Player.pause() method. The cleanest minimal approach: remove
`[Space]Play` from the footer until pause is implemented. Replace with
accurate shortcuts only.

**S key — cycle actual sources (not just a string):**

Requires a source registry and switching mechanism. Scope creep for this
improvement round. Fix: remove `[S]ource` from footer and the dead handler.

```python
# footer — remove [S]ource, keep only working shortcuts
"[Q]uit  [M]ode  [←→]Tune  [↑↓]Vol  [N]ext  [R]SSI"
```

**Lines changed: ~15 in tui.py, ~3 in main.py**

---

## B6 — pink_noise() Per-Chunk State Reset

**File:** `src/signal/noise.py:21-39`

The standalone `pink_noise()` creates fresh state each call:

```python
def pink_noise(n_samples, n_channels=2, amplitude=0.01):
    n_octaves = 5
    state = np.zeros(n_octaves)  # FRESH every call — causes click @ chunk boundary
```

Each 1024-sample chunk starts with all Voss-McCartney generators at zero,
creating a discontinuity (click) every ~23 ms. Used by AMHDMode and
SignalSimulator._degrade_am.

### Fix

Convert to a class with persistent state, or pass state as parameter:

```python
class PinkNoiseGenerator:
    """Persistent pink noise generator — no chunk-boundary artifacts."""

    def __init__(self, n_octaves: int = 5):
        self.state = np.zeros(n_octaves, dtype=np.float32)

    def generate(self, n_samples: int, n_channels: int = 2, amplitude: float = 0.01) -> np.ndarray:
        out = np.zeros((n_samples, n_channels), dtype=np.float32)
        for ch in range(n_channels):
            for i in range(n_samples):
                k = np.random.randint(len(self.state))
                self.state[k] = np.random.randn()
                out[i, ch] = np.mean(self.state)
        std = np.std(out) + 1e-8
        return (out / std) * amplitude
```

Update call sites:

```python
# SignalSimulator.__init__
self._pink_gen = PinkNoiseGenerator()

# _degrade_am
pink = self._pink_gen.generate(n_samples, n_channels, amplitude=noise_amp * 1.2)
```

**Lines changed: ~20 in noise.py, ~4 in propagation.py, ~4 in amhd.py**

---

## B7 — No ffplay/ffmpeg Pre-Flight Check

Already documented in `B4-preflight-checks.md`. Included here for completeness
in the high-severity list.

**Lines changed: ~15 across main.py, player.py, mp3.py**

---

## B8 — Arrow Key Fragility

Already documented in `B3-arrow-keys.md`. Renumbered to B8.

**Lines changed: ~20 in tui.py**
