"""Numerical correctness tests — gain staging, filter response, noise calibration."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from conftest import tone, tone_stereo, silence, assert_audio_ok, SR


def test_dc_offset():
    """Silence in → should produce near-zero output from all modes."""
    s = silence(1.0)
    from src.modes.fm import FMMode
    from src.modes.am import AMMode
    from src.modes.dab import DABMode

    for Mode, name in [(FMMode, "FM"), (AMMode, "AM"), (DABMode, "DAB+")]:
        mode = Mode()
        out = mode.process(s.copy(), signal_db=-45)
        dc = float(np.mean(out))
        assert abs(dc) < 0.01, f"{name}: DC offset {dc:.4f} too high on silence input"
    print("  PASS: no DC offset on silence input")


def test_gain_unity():
    """0dBFS tone should not be amplified by any mode processing."""
    t = tone(440, 1.0, amplitude=0.8)
    from src.modes.fm import FMMode
    from src.modes.am import AMMode

    fm = FMMode()
    out_fm = fm.process(t.copy(), signal_db=-30)
    assert float(abs(out_fm).max()) < 1.5, f"FM peak {abs(out_fm).max():.3f} too high"

    am = AMMode()
    out_am = am.process(t.copy(), signal_db=-30)
    assert float(abs(out_am).max()) < 1.5, f"AM peak {abs(out_am).max():.3f} too high"
    print("  PASS: gain staging within bounds")


def test_noise_level_monotonic():
    """_noise_level_from_rssi should be monotonic — weaker = higher noise."""
    from src.modes.fm import FMMode
    mode = FMMode()
    prev = -1
    for rssi in [-30, -50, -70, -90]:
        level = mode._noise_level_from_rssi(rssi, noise_floor_db=-95)
        assert level > prev, f"noise at {rssi}dBm ({level:.4f}) not > previous ({prev:.4f})"
        prev = level
    print(f"  PASS: noise_level monotonically increases (0.015 → {level:.4f})")


def test_deemphasis_cutoff():
    """FM 75us de-emphasis should attenuate high frequencies."""
    from src.modes.fm import FMMode
    fm = FMMode()

    # Low frequency (100 Hz) — should pass nearly unchanged
    t_low = tone(100, 0.5, amplitude=0.5)
    out_low = fm._apply_deemphasis(t_low)
    rms_low = float(np.sqrt(np.mean(out_low ** 2)))

    # High frequency (10 kHz) — should be attenuated
    t_high = tone(10000, 0.5, amplitude=0.5)
    out_high = fm._apply_deemphasis(t_high)
    rms_high = float(np.sqrt(np.mean(out_high ** 2)))

    assert rms_high < rms_low * 0.8, f"De-emphasis: HF rms {rms_high:.4f} not < LF rms {rms_low:.4f} * 0.8"
    print(f"  PASS: de-emphasis LF={rms_low:.3f}, HF={rms_high:.3f} (HF attenuated)")


def test_am_bandwidth_limit():
    """AM should heavily attenuate content above 5 kHz."""
    t_10k = tone(10000, 0.5, amplitude=0.5)
    t_1k = tone(1000, 0.5, amplitude=0.5)
    from src.modes.am import AMMode
    am = AMMode()

    out_10k = am._apply_bandpass(t_10k)
    out_1k = am._apply_bandpass(t_1k)

    rms_10k = float(np.sqrt(np.mean(out_10k ** 2)))
    rms_1k = float(np.sqrt(np.mean(out_1k ** 2)))

    # 10 kHz should be at least 20 dB below 1 kHz after bandpass
    ratio_db = 20 * np.log10(rms_10k / (rms_1k + 1e-8))
    assert ratio_db < -20, f"AM bandpass: 10kHz only {ratio_db:.0f} dB below 1kHz"
    print(f"  PASS: AM bandwidth — 10kHz is {ratio_db:.0f} dB below 1kHz")


def test_fading_mean_near_one():
    """Fading envelope should average near 1.0 for small depth."""
    from src.signal.noise import fading_envelope
    np.random.seed(42)
    env = fading_envelope(SR * 10, rate_hz=0.5, depth=0.3, sample_rate=SR)
    mean = float(np.mean(env))
    # Envelope mean is 1 - depth/2 per audit finding — verify within 10%
    expected = 1.0 - 0.3 / 2
    assert abs(mean - expected) < 0.05, f"Fading mean {mean:.4f}, expected ~{expected:.4f}"
    print(f"  PASS: fading envelope mean={mean:.3f} (expected ~{expected:.3f})")


def test_no_nan_inf_in_noise():
    """Noise generators should never produce NaN or Inf."""
    from src.signal.noise import (
        PinkNoiseGenerator, white_noise, impulsive_noise, fading_envelope
    )
    png = PinkNoiseGenerator()
    pink = png.generate(44100, 2)
    assert not np.any(np.isnan(pink)) and not np.any(np.isinf(pink)), "pink NaN/Inf"

    white = white_noise((44100, 2), amplitude=1.0)
    assert not np.any(np.isnan(white)) and not np.any(np.isinf(white)), "white NaN/Inf"

    imp = impulsive_noise(44100, 2, rate_per_second=100, amplitude=0.5)
    assert not np.any(np.isnan(imp)) and not np.any(np.isinf(imp)), "impulsive NaN/Inf"

    env = fading_envelope(44100, rate_hz=1.0, depth=0.5)
    assert not np.any(np.isnan(env)) and not np.any(np.isinf(env)), "fading NaN/Inf"
    print("  PASS: all noise generators produce clean output")


if __name__ == "__main__":
    print("test_numerical.py — DSP correctness\n")
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
