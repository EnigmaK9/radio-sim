# B1 — Mode Switching Broken in TUI (CRITICAL)

## What's wrong

`main.py:146-154` — The `mode_processor` and `degradation_processor` closures capture
`radio_mode` and `mode` by reference from the outer scope. When `on_mode_change`
(line 224-230) creates a new `RadioMode` object and updates the local variable,
the pipeline processors **still reference the old object** because closures in Python
capture by name, not by value, and the pipeline's `_processors` list still holds
the old lambdas.

```python
# main.py:146 — This lambda captured the ORIGINAL radio_mode
def mode_processor(chunk):
    return radio_mode.process(chunk, signal_sim.rssi)  # ← still old radio_mode!

# main.py:224 — This creates a new object but doesn't update the pipeline
def on_mode_change(new_mode):
    nonlocal radio_mode, mode
    mode = new_mode
    radio_mode = FMMode()  # ← pipeline never sees this
    pipeline.flush()       # ← flushes buffer but processors are stale
```

## Root cause

The pipeline stores processors as a list of callables. When mode changes,
new processor callables must be registered. The current code only flushes
the buffer — it doesn't replace the processors.

## Fix

Replace pipeline processors on mode change. Use a mutable container for
the mode reference so the existing lambda sees the update without
re-registration.

### Approach: shared cell (minimal diff, no new abstractions)

```python
# main.py — change the processor closures to dereference a mutable cell
_mode_cell = [radio_mode]  # single-element list, mutated on mode switch
_mode_str_cell = [mode]

def mode_processor(chunk):
    return _mode_cell[0].process(chunk, signal_sim.rssi)

def degradation_processor(chunk):
    return signal_sim.apply_degradation(chunk, _mode_str_cell[0])

pipeline.add_processor(mode_processor)
pipeline.add_processor(degradation_processor)

# In on_mode_change:
def on_mode_change(new_mode):
    nonlocal mode
    mode = new_mode
    _mode_cell[0] = MODE_MAP[new_mode]()
    _mode_str_cell[0] = new_mode
    pipeline.flush()
```

### Why this works

Python closures capture names from the enclosing scope. By making
`_mode_cell` a list (mutable container), the closure captures the
*list reference* which never changes. The list's *contents* change
on mode switch. No need to rebuild the processor list.

### Lines changed: ~8

## Verification

```bash
python -m src.main --mode fm --freq 101.1 --source ~/Music/
# Press M to switch to AM — should hear immediate bandwidth reduction + mono
# Press M again for DAB+ — should hear digital clarity
```
