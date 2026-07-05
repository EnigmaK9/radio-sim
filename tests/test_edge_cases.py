"""Edge case tests — mono input, DC, near-Nyquist, extreme RSSI, etc."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from conftest import tone, silence, assert_audio_ok, run_all_modes, SR


def test_mono_to_stereo():
    """1ch audio through FM becomes 2ch (FM is a stereo mode)."""
    from src.modes.fm import FMMode
    fm = FMMode()
    n = 44100
    mono = np.random.randn(n, 1).astype(np.float32) * 0.1
    out = fm.process(mono, signal_db=-30)
    assert out.shape == (n, 2), f"Expected ({n},2) stereo, got {out.shape}"
    assert_audio_ok(out, "FM mono->stereo")
    print("  PASS: FM expands mono to stereo")


def test_silence_near_silent_output():
    """Silence at strong FM has RMS < 0.01.

    At signal_db=-20 the noise model produces zero noise (clamp ceiling),
    so silence + strong signal stays silent.
    """
    from src.modes.fm import FMMode
    fm = FMMode()
    s = silence(1.0)
    out = fm.process(s, signal_db=-20)
    rms = float(np.sqrt(np.mean(out.astype(np.float64) ** 2)))
    assert rms < 0.01, f"RMS {rms:.6f} >= 0.01"
    print(f"  PASS: silence RMS={rms:.6f} < 0.01")


def test_extreme_rssi():
    """RSSI=-120 and -10 produce valid audio in all modes."""
    t = tone(440, 0.5, amplitude=0.5)
    for rssi in (-120, -10):
        results = run_all_modes(t, signal_db=float(rssi))
        for name, out in results.items():
            assert_audio_ok(out, name)
    print("  PASS: RSSI=-120 and -10 processed without error")


def test_zero_volume():
    """vol=0 multiply gives all zeros."""
    t = tone(440, 0.5, amplitude=0.5)
    z = t * 0.0
    assert np.all(z == 0.0), "vol=0 should produce all zeros"
    print("  PASS: vol=0 all zeros")


def test_single_chunk_pad():
    """512-sample audio processes without padding to 1024."""
    from src.modes.fm import FMMode
    fm = FMMode()
    n = 512
    audio = np.random.randn(n, 2).astype(np.float32) * 0.1
    out = fm.process(audio, signal_db=-30)
    assert out.shape == (n, 2), f"Expected ({n},2), got {out.shape}"
    assert_audio_ok(out, "512-sample FM")
    print(f"  PASS: {n}-sample audio remains {n} samples")


def test_very_low_amplitude():
    """1e-6 tone processes without NaN."""
    t = tone(440, 0.5, amplitude=1e-6)
    results = run_all_modes(t, signal_db=-45)
    for name, out in results.items():
        assert not np.any(np.isnan(out)), f"{name}: NaN detected"
    print("  PASS: 1e-6 amplitude processed without NaN")


def test_dc_input():
    """Constant 0.5 processes without NaN."""
    n = int(SR * 0.5)
    dc = np.full((n, 2), 0.5, dtype=np.float32)
    results = run_all_modes(dc, signal_db=-45)
    for name, out in results.items():
        assert not np.any(np.isnan(out)), f"{name}: NaN detected"
    print("  PASS: DC input processed without NaN")


def test_rapid_rssi():
    """100 RSSI changes doesn't crash any mode."""
    t = tone(440, 0.5, amplitude=0.5)
    rssi_values = np.linspace(-120, -10, 100)

    from src.modes.fm import FMMode
    from src.modes.am import AMMode
    from src.modes.amhd import AMHDMode
    from src.modes.fmhd import FMHDMode
    from src.modes.dab import DABMode

    modes = {
        "FM": FMMode(),
        "AM": AMMode(),
        "AMHD": AMHDMode(),
        "FMHD": FMHDMode(),
        "DAB+": DABMode(),
    }
    for rssi in rssi_values:
        for name, mode in modes.items():
            out = mode.process(t.copy(), signal_db=float(rssi))
            assert_audio_ok(out, name)
    print("  PASS: 100 RSSI changes handled without crash")


def test_long_silence():
    """10s silence through AM weak RSSI doesn't crash."""
    from src.modes.am import AMMode
    am = AMMode()
    s = silence(10.0)
    out = am.process(s, signal_db=-90)
    assert_audio_ok(out, "AM long silence")
    print("  PASS: 10s silence through AM at -90 dBm")


def test_high_frequency():
    """20kHz tone (near Nyquist) doesn't produce NaN."""
    t = tone(20000, 0.5, amplitude=0.5)
    results = run_all_modes(t, signal_db=-45)
    for name, out in results.items():
        assert not np.any(np.isnan(out)), f"{name}: NaN detected"
    print("  PASS: 20kHz tone processed without NaN")


if __name__ == "__main__":
    print("test_edge_cases.py -- edge case suite\n")
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
            except Exception as e:
                print(f"  FAIL: {name} -- {e}")
                failures += 1
    print(f"\n{failures} failures")
    sys.exit(failures)
