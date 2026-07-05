"""EQ presets and filter utilities for radio mode processing."""

from dataclasses import dataclass

import numpy as np
from scipy import signal as scipy_signal


@dataclass
class EQPreset:
    """Bandpass + de-emphasis configuration for a radio mode."""

    name: str
    highpass: float | None  # Hz, None = no highpass
    lowpass: float | None  # Hz, None = no lowpass
    deemphasis_tau: float | None  # µs, None = no deemphasis
    order: int = 4


# ---- Preset Library ----

PRESETS: dict[str, EQPreset] = {
    "fm": EQPreset("FM", highpass=50.0, lowpass=15000.0, deemphasis_tau=75.0, order=4),
    "am": EQPreset("AM", highpass=50.0, lowpass=5000.0, deemphasis_tau=None, order=6),
    "amhd": EQPreset("AMHD", highpass=50.0, lowpass=15000.0, deemphasis_tau=None, order=4),
    "fmhd": EQPreset("FMHD", highpass=20.0, lowpass=20000.0, deemphasis_tau=None, order=2),
    "dab": EQPreset("DAB+", highpass=20.0, lowpass=20000.0, deemphasis_tau=None, order=2),
}

# Cache for sos coefficients per (low, high, order, sr) key.
_sos_cache: dict[tuple, np.ndarray] = {}


def apply_eq(
    audio: np.ndarray,
    preset: EQPreset,
    sample_rate: int = 44100,
) -> np.ndarray:
    """Apply Butterworth bandpass + optional de-emphasis from a preset.

    Args:
        audio: (n_samples, n_channels) float32.
        preset: EQPreset with highpass/lowpass/deemphasis_tau.
        sample_rate: audio sample rate.
    """
    out = audio

    # Bandpass
    if preset.highpass is not None or preset.lowpass is not None:
        low = preset.highpass or 10.0
        high = preset.lowpass or sample_rate / 2 - 1
        cache_key = (low, high, preset.order, sample_rate)
        sos = _sos_cache.get(cache_key)
        if sos is None:
            sos = scipy_signal.butter(
                preset.order, [low, high], btype="band", fs=sample_rate, output="sos"
            )
            _sos_cache[cache_key] = sos
        out = scipy_signal.sosfilt(sos, out, axis=0)

    # De-emphasis (first-order IIR)
    if preset.deemphasis_tau is not None and preset.deemphasis_tau > 0:
        tau = preset.deemphasis_tau * 1e-6
        dt = 1.0 / sample_rate
        alpha = dt / (tau + dt)

        for ch in range(out.shape[1]):
            prev = 0.0
            for i in range(len(out)):
                out[i, ch] = prev = prev + alpha * (out[i, ch] - prev)

    return out


def mono_mixdown(audio: np.ndarray) -> np.ndarray:
    """Convert stereo to dual-mono: (L + R) / 2 → both channels."""
    if audio.shape[1] < 2:
        return audio
    mono = np.mean(audio[:, :2], axis=1, keepdims=True, dtype=np.float32)
    return np.repeat(mono, audio.shape[1], axis=1)


def stereo_blend(audio: np.ndarray, blend: float) -> np.ndarray:
    """Blend from stereo (blend=0) to mono (blend=1).

    Args:
        audio: (n_samples, n_channels) float32.
        blend: 0.0 = full stereo, 1.0 = full mono.
    """
    if audio.shape[1] < 2 or blend <= 0.0:
        return audio
    mono = mono_mixdown(audio)
    return (1.0 - blend) * audio + blend * mono
