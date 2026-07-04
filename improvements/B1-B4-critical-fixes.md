# B1–B4 — Critical Bug Fixes

## B1 — FM Stereo Blend Formula Inverted

**File:** `src/modes/fm.py:52`

```python
# CURRENT (WRONG):
blend = float(np.clip((signal_db + 90) / (-70 + 90), 0.0, 1.0))
```

**What happens:** At signal_db = -30 (strong): blend = (-30+90)/20 = 3.0 → clipped to 1.0 = **full mono**.
At signal_db = -100 (weak): blend = (-100+90)/20 = -0.5 → clipped to 0.0 = **full stereo**.

This is backwards. The comment says "0 = full stereo (strong), 1 = full mono (weak)" but the
formula has the signs inverted.

**Fix:**
```python
# CORRECT:
blend = float(np.clip((-70 - signal_db) / 20.0, 0.0, 1.0))
```

**Verification:** -30 dBm → blend=2.0→clipped to 0 (full stereo). -100 dBm → blend=1.5→clipped to 1 (full mono).

---

## B2 — Double Degradation (Noise Applied Twice)

**File:** `src/main.py:146-154`

**What happens:** The pipeline has TWO processors in sequence:

1. `mode_processor` (line 147): calls `radio_mode.process()` — each mode adds its own noise:
   - FMMode adds white noise (`_mix_noise`)
   - AMMode adds pink+white static + crackle + fading
   - AMHDMode adds quantization noise + frame drops
   - FMHDMode adds white noise + glitches
   - DABMode adds white noise + burst errors

2. `degradation_processor` (line 152): calls `signal_sim.apply_degradation()` — adds ANOTHER layer:
   - `_degrade_fm` adds white noise + multipath + fading
   - `_degrade_am` adds pink+white static + crackle + fading
   - etc.

The cumulative noise is 2× what it should be. For AM mode, this means pink+white static
is generated in AMMode and then ANOTHER pink+white layer in SignalSimulator.

**Fix:** Choose ONE place for degradation. The cleanest split:

```python
# main.py — mode handles EQ/bandwidth/stereo; signal_sim handles ALL noise
def mode_processor(chunk):
    # Only EQ + stereo + bandwidth shaping — NO noise
    return radio_mode.process(chunk, signal_sim.rssi)

# Remove from mode.process():
# - FMMode._mix_noise
# - AMMode._mix_static, _inject_crackle, _apply_fading
# - AMHDMode digital/analog path noise injection
# - FMHDMode noise injection
# - DABMode noise injection + burst errors

# signal_sim.apply_degradation handles ALL noise + fading + errors
```

**Alternative (less refactoring):** Remove `degradation_processor` from the pipeline
and let each mode handle its own degradation. But then RSSI changes need to flow
through mode objects, not signal_sim.

**Recommendation:** The alternative is simpler. Keep noise in modes, remove
`degradation_processor` from pipeline. SignalSimulator becomes just an RSSI
holder that modes read from:

```python
# main.py — single processor
def mode_processor(chunk):
    return radio_mode.process(chunk, signal_sim.rssi)

pipeline.add_processor(mode_processor)
# Remove: pipeline.add_processor(degradation_processor)
```

**Lines changed: -3 in main.py, SignalSimulator remains as RSSI state holder**

---

## B3 — RSSI Effect Intensity Inverted

**Files:**
- `src/signal/propagation.py:131` — crackle rate
- `src/signal/propagation.py:140` — fade depth
- `src/modes/am.py:81` — crackle rate
- `src/modes/am.py:108` — fade rate
- `src/modes/am.py:109` — fade depth

**What happens:** The formula `min + (1.0 - normalized) * range` means:
- Strong signal (noise_amp ≈ 0.015): `1.0 - 0.015/0.12 ≈ 0.875` → high crackle, deep fades
- Weak signal (noise_amp ≈ 0.105): `1.0 - 0.105/0.12 ≈ 0.125` → low crackle, shallow fades

Strong signals are MORE degraded than weak ones. The `normalized` variable should
be used directly, not inverted:

**Fix (all 5 locations):**

```python
# propagation.py:131 — BEFORE (WRONG)
crackle_rate = 0.5 + (1.0 - noise_amp / 0.12) * 4.5

# propagation.py:131 — AFTER (CORRECT)
crackle_rate = 0.5 + (noise_amp / 0.12) * 4.5

# Same pattern for all 5 occurrences:
# am.py:81 — rate_per_sample
# am.py:108 — fade_rate
# am.py:109 — depth
# propagation.py:140 — fade_depth
```

**Lines changed: 5 × 1-line formula fix**

---

## B4 — Player Thread Race on self._process

**File:** `src/engine/player.py:95-96, 88`

**What happens:** The refill thread reads `self._process` twice:

```python
if self._process is None or self._process.poll() is not None:
```

Between `self._process is None` (line 95, bytecode ~5) and `self._process.poll()`
(line 96, bytecode ~15), `stop()` can execute from the main thread and set
`self._process = None`. Then line 96 raises `AttributeError` on None.poll().

Same bug in `is_playing` (line 88).

**Fix:** Capture a local reference:

```python
proc = self._process
if proc is None or proc.poll() is not None:
    break
```

```python
# is_playing property
proc = self._process
return self._running and proc is not None and proc.poll() is None
```

**Lines changed: ~4**
