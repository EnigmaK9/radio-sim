"""Quick sanity — all modes process 1s tone without crash. Runs in <5s."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from conftest import tone, tone_stereo, silence, assert_audio_ok, assert_not_silent, run_all_modes


def test_all_modes_process_tone():
    """Every mode should process a 440Hz stereo tone without error."""
    t = tone(440, 1.0, amplitude=0.5)
    results = run_all_modes(t)
    for name, out in results.items():
        assert_not_silent(out, name)
    print(f"  PASS: all 5 modes process 1s tone")


def test_silence_does_not_crash():
    """Silent input should not crash any mode."""
    s = silence(0.5)
    results = run_all_modes(s)
    for name, out in results.items():
        assert_audio_ok(out, name)
    print(f"  PASS: silence processed without crash")


def test_stereo_preserved():
    """FM at strong RSSI should preserve stereo separation."""
    t = tone_stereo(440, 1000, 0.5, amplitude=0.5)
    from src.modes.fm import FMMode
    fm = FMMode()
    out = fm.process(t, signal_db=-30)
    corr = np.corrcoef(out[:, 0], out[:, 1])[0, 1]
    assert corr < 0.5, f"FM strong signal should have low L/R correlation, got {corr:.3f}"
    print(f"  PASS: FM stereo preserved (corr={corr:.3f})")


def test_weak_signal_noisier():
    """Weak RSSI should produce more noise than strong RSSI."""
    t = tone(1000, 0.5, amplitude=0.5)
    from src.modes.am import AMMode
    am = AMMode()
    strong = am.process(t.copy(), signal_db=-30)
    weak = am.process(t.copy(), signal_db=-90)
    strong_rms = float(np.sqrt(np.mean((strong - t) ** 2)))
    weak_rms = float(np.sqrt(np.mean((weak - t) ** 2)))
    assert weak_rms > strong_rms, f"weak={weak_rms:.4f} should be > strong={strong_rms:.4f}"
    print(f"  PASS: weak signal noisier ({strong_rms:.3f} → {weak_rms:.3f})")


def test_no_nan_after_long_run():
    """60 seconds of continuous processing should produce no NaN."""
    t = tone(440, 1.0, amplitude=0.5)
    from src.modes.fm import FMMode
    fm = FMMode()
    acc = t.copy()
    for _ in range(60):
        acc = fm.process(t, signal_db=-45)
        if np.any(np.isnan(acc)):
            assert False, "NaN detected in FM output"
    assert_audio_ok(acc, "FM after 60s")
    print(f"  PASS: no NaN after 60s continuous FM processing")


def test_clip_no_crash():
    """Processing near-full-scale audio should not crash or NaN."""
    t = tone(440, 0.5, amplitude=0.999)
    results = run_all_modes(t, signal_db=-30)
    for name, out in results.items():
        peak = float(abs(out).max())
        assert peak <= 2.0, f"{name}: peak {peak:.3f} exceeds 2.0 (pipeline clips)"
    print(f"  PASS: near-0dBFS input handled without NaN/crash")


if __name__ == "__main__":
    print("test_smoke.py — quick sanity suite\n")
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
            except Exception as e:
                print(f"  FAIL: {name} — {e}")
                failures += 1
    print(f"\n{failures} failures")
    sys.exit(failures)
