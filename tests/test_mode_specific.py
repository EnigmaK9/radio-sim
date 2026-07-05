"""Mode-specific behavioral tests — de-emphasis, mono/crossfade, subchannel, burst, cliff, multipath, crackle."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from conftest import tone, tone_stereo, SR


# ── test 1: FM de-emphasis ────────────────────────────────────────────────

def test_fm_deemphasis():
    """75 µs de-emphasis: 10 kHz attenuated >= 10 dB vs 100 Hz."""
    from src.modes.fm import FMMode
    fm = FMMode()

    lf = tone(100, 1.0, amplitude=0.5)
    hf = tone(10000, 1.0, amplitude=0.5)

    lf_out = fm.process(lf, signal_db=-30)
    hf_out = fm.process(hf, signal_db=-30)

    lf_rms = float(np.sqrt(np.mean(lf_out ** 2)))
    hf_rms = float(np.sqrt(np.mean(hf_out ** 2)))

    # dB difference: 20 * log10(hf_rms / lf_rms)
    diff_db = 20.0 * np.log10(hf_rms / lf_rms + 1e-12)
    assert diff_db <= -10.0, (
        f"HF (10kHz) should be attenuated >= 10dB vs LF (100Hz), "
        f"got {diff_db:.1f} dB (hf_rms={hf_rms:.4f}, lf_rms={lf_rms:.4f})"
    )
    print(f"  PASS: FM de-emphasis {diff_db:.1f} dB (HF vs LF)")


# ── test 2: AM mono ───────────────────────────────────────────────────────

def test_am_mono():
    """AM mode: L/R correlation > 0.99 (mono downmix)."""
    from src.modes.am import AMMode
    am = AMMode()

    # Stereo input with different L/R content
    audio = tone_stereo(440, 880, 0.8, amplitude=0.5)
    out = am.process(audio, signal_db=-30)

    corr = float(np.corrcoef(out[:, 0], out[:, 1])[0, 1])
    assert corr > 0.99, f"AM L/R correlation should be > 0.99, got {corr:.6f}"
    print(f"  PASS: AM mono correlation={corr:.6f}")


# ── test 3: AMHD crossfade ────────────────────────────────────────────────

def test_amhd_crossfade():
    """AMHD: RSSI=-30 → wideband+stereo, RSSI=-100 → narrow+mono."""
    from src.modes.amhd import AMHDMode

    # Stereo tone with different L/R
    audio = tone_stereo(440, 880, 0.8, amplitude=0.5)

    amhd_strong = AMHDMode()
    amhd_weak = AMHDMode()

    out_strong = amhd_strong.process(audio.copy(), signal_db=-30)
    out_weak = amhd_weak.process(audio.copy(), signal_db=-100)

    # Strong: should have high bandwidth (lots of HF energy from 880 Hz)
    # Weak: should be mono (L/R correlation high) and have less HF
    strong_hf = float(np.sqrt(np.mean(out_strong ** 2)))
    weak_hf = float(np.sqrt(np.mean(out_weak ** 2)))

    # Strong should have more energy overall (wider band preserved)
    assert strong_hf > weak_hf * 1.2, (
        f"Strong RSSI should have more HF energy than weak, "
        f"strong={strong_hf:.4f} weak={weak_hf:.4f}"
    )

    # Weak should be near-mono (high L/R correlation)
    corr_strong = float(np.corrcoef(out_strong[:, 0], out_strong[:, 1])[0, 1])
    corr_weak = float(np.corrcoef(out_weak[:, 0], out_weak[:, 1])[0, 1])

    assert corr_weak > corr_strong, (
        f"Weak RSSI should have higher L/R correlation (mono blend) than strong, "
        f"weak={corr_weak:.4f} strong={corr_strong:.4f}"
    )
    assert corr_weak > 0.9, f"Weak RSSI should be near-mono, corr={corr_weak:.4f}"
    print(f"  PASS: AMHD crossfade (strong_rms={strong_hf:.4f}, weak_rms={weak_hf:.4f}, "
          f"corr_strong={corr_strong:.4f}, corr_weak={corr_weak:.4f})")


# ── test 4: FMHD subchannel ───────────────────────────────────────────────

def test_fmhd_subchannel():
    """FMHD subchannel 2 (64kbps) has less HF energy than subchannel 0 (300kbps)."""
    from src.modes.fmhd import FMHDMode

    audio = tone(14000, 1.0, amplitude=0.5)  # 14 kHz — above subch2 cutoff (~9.7kHz)

    fmhd_0 = FMHDMode(subchannel=0)
    fmhd_2 = FMHDMode(subchannel=2)

    out_0 = fmhd_0.process(audio.copy(), signal_db=-30)
    out_2 = fmhd_2.process(audio.copy(), signal_db=-30)

    rms_0 = float(np.sqrt(np.mean(out_0 ** 2)))
    rms_2 = float(np.sqrt(np.mean(out_2 ** 2)))

    assert rms_2 < rms_0 * 0.95, (
        f"Subchannel 2 should have less HF energy than subchannel 0, "
        f"ch0_rms={rms_0:.4f} ch2_rms={rms_2:.4f}"
    )
    print(f"  PASS: FMHD subchannel (ch0_rms={rms_0:.4f}, ch2_rms={rms_2:.4f})")


# ── test 5: DAB burst rate ────────────────────────────────────────────────

def test_dab_burst_rate():
    """DAB: RSSI=-45 near zero burst errors, RSSI=-95 many burst errors."""
    from src.modes.dab import DABMode

    audio = tone(440, 2.0, amplitude=0.5)

    dab_strong = DABMode()
    dab_weak = DABMode()

    out_strong = dab_strong.process(audio.copy(), signal_db=-45)
    out_weak = dab_weak.process(audio.copy(), signal_db=-95)

    # Count zeros (burst errors produce silence)
    strong_zeros = float(np.mean(np.abs(out_strong) < 1e-8))
    weak_zeros = float(np.mean(np.abs(out_weak) < 1e-8))

    assert strong_zeros < 0.01, (
        f"Strong RSSI (-45) should have near-zero burst errors, "
        f"got {strong_zeros*100:.1f}% zeros"
    )
    assert weak_zeros > strong_zeros * 3, (
        f"Weak RSSI (-95) should have many more burst errors than strong, "
        f"strong_zeros={strong_zeros*100:.1f}% weak_zeros={weak_zeros*100:.1f}%"
    )
    print(f"  PASS: DAB burst rate (strong_zeros={strong_zeros*100:.1f}%, "
          f"weak_zeros={weak_zeros*100:.1f}%)")


# ── test 6: DAB cliff ─────────────────────────────────────────────────────

def test_dab_cliff():
    """DAB cliff effect: clean at -75 dBm, heavy mutes at -95 dBm."""
    from src.modes.dab import DABMode

    audio = tone(440, 2.0, amplitude=0.5)

    dab_clean = DABMode()
    dab_muted = DABMode()

    out_clean = dab_clean.process(audio.copy(), signal_db=-75)
    out_muted = dab_muted.process(audio.copy(), signal_db=-95)

    # At -75: almost no silence gaps (above/at threshold)
    clean_zeros = float(np.mean(np.abs(out_clean) < 1e-8))
    muted_zeros = float(np.mean(np.abs(out_muted) < 1e-8))

    assert clean_zeros < 0.02, (
        f"At -75 dBm audio should be mostly clean, "
        f"got {clean_zeros*100:.1f}% zeros"
    )
    # At -95: significant dropouts
    assert muted_zeros > clean_zeros * 5, (
        f"At -95 dBm should have significantly more mutes than at -75, "
        f"clean_zeros={clean_zeros*100:.1f}% muted_zeros={muted_zeros*100:.1f}%"
    )
    print(f"  PASS: DAB cliff (clean_zeros={clean_zeros*100:.1f}%, "
          f"muted_zeros={muted_zeros*100:.1f}%)")


# ── test 7: FM multipath ──────────────────────────────────────────────────

def test_fm_multipath():
    """Weak RSSI has more signal variation than strong (multipath interference)."""
    from src.modes.fm import FMMode

    audio = tone(1000, 2.0, amplitude=0.5)

    fm_strong = FMMode()
    fm_weak = FMMode()

    out_strong = fm_strong.process(audio.copy(), signal_db=-30)
    out_weak = fm_weak.process(audio.copy(), signal_db=-90)

    # Multipath causes amplitude variation (constructive/destructive interference)
    # Measure envelope std relative to mean
    env_strong = np.abs(scipy_hilbert(np.mean(out_strong, axis=1)))
    env_weak = np.abs(scipy_hilbert(np.mean(out_weak, axis=1)))

    var_strong = float(np.std(env_strong) / (np.mean(env_strong) + 1e-12))
    var_weak = float(np.std(env_weak) / (np.mean(env_weak) + 1e-12))

    assert var_weak > var_strong * 1.2, (
        f"Weak RSSI should have more amplitude variation than strong, "
        f"strong_cv={var_strong:.4f} weak_cv={var_weak:.4f}"
    )
    print(f"  PASS: FM multipath (strong_cv={var_strong:.4f}, weak_cv={var_weak:.4f})")


def scipy_hilbert(x):
    """Hilbert transform via scipy for envelope detection."""
    from scipy import signal as scipy_signal
    return scipy_signal.hilbert(x)


# ── test 8: AM crackle ────────────────────────────────────────────────────

def test_am_crackle():
    """Weak RSSI has more crackle events than strong."""
    from src.modes.am import AMMode

    audio = tone(440, 3.0, amplitude=0.5)

    am_strong = AMMode()
    am_weak = AMMode()

    out_strong = am_strong.process(audio.copy(), signal_db=-30)
    out_weak = am_weak.process(audio.copy(), signal_db=-90)

    # Crackle = sudden amplitude spikes. Count samples where absolute value
    # exceeds the 99.9th percentile of the strong signal (as baseline)
    strong_amp = np.abs(out_strong)
    weak_amp = np.abs(out_weak)

    threshold = np.percentile(strong_amp, 99.9) * 1.5
    # Count "spike" samples in each
    strong_spikes = float(np.mean(strong_amp > threshold))
    weak_spikes = float(np.mean(weak_amp > threshold))

    assert weak_spikes > strong_spikes * 2, (
        f"Weak RSSI should have more crackle spikes than strong, "
        f"strong_spikes={strong_spikes*100:.2f}% weak_spikes={weak_spikes*100:.2f}%"
    )
    print(f"  PASS: AM crackle (strong_spikes={strong_spikes*100:.2f}%, "
          f"weak_spikes={weak_spikes*100:.2f}%)")


# ── runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("test_mode_specific.py — mode-specific behavioral tests\n")
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
            except Exception as e:
                print(f"  FAIL: {name} — {e}")
                failures += 1
    print(f"\n{failures} failures")
    sys.exit(failures)
