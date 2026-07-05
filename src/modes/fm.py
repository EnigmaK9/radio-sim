"""FM (Frequency Modulation) radio mode — 87.5–108.0 MHz, stereo, 50Hz-15kHz."""

import numpy as np
from scipy import signal as scipy_signal

from src.modes.base import ModeParameters, RadioMode


class FMMode(RadioMode):
    """FM broadcast band: 87.5–108 MHz, stereo, 50 Hz – 15 kHz audio bandwidth.

    Processing chain:
      1. Stereo blend → mono at low RSSI (receiver stereo threshold)
      2. Bandpass 50 Hz – 15 kHz (FM channel bandwidth)
      3. 75 µs de-emphasis filter
      4. Multipath comb filtering (ground/sky wave interference)
      5. White noise floor proportional to RSSI
    """

    params = ModeParameters(
        name="FM",
        frequency_min=87.5,
        frequency_max=108.0,
        frequency_unit="MHz",
        audio_bandwidth_low=50.0,
        audio_bandwidth_high=15000.0,
        stereo=True,
    )

    # ---- public ----

    def process(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        audio = self._apply_stereo_blend(audio, signal_db)
        audio = self._apply_bandpass(audio)
        audio = self._apply_deemphasis(audio)
        audio = self._apply_multipath(audio, signal_db)
        audio = self._mix_noise(audio, signal_db)
        return audio.astype(np.float32, copy=False)

    # ---- processing stages ----

    def _apply_stereo_blend(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Blend stereo toward mono as signal weakens.

        FM stereo threshold is typically around -70 dBm; below -90 dBm the
        receiver switches fully to mono to reduce noise.
        """
        if audio.shape[1] < 2:
            return audio

        # Blend factor: 0 = full stereo (strong), 1 = full mono (weak)
        blend = np.float32(np.clip((-70 - signal_db) / 20.0, 0.0, 1.0))
        if blend <= 0.0:
            return audio

        mono = np.mean(audio, axis=1, keepdims=True, dtype=np.float32)
        mono = np.repeat(mono, 2, axis=1).astype(np.float32)
        return ((1.0 - blend) * audio + blend * mono).astype(np.float32)

    def _apply_bandpass(self, audio: np.ndarray) -> np.ndarray:
        """Butterworth bandpass 50 Hz – 15 kHz."""
        cache_key = ("bp", 50.0, 15000.0)
        sos = self._filter_cache.get(cache_key)
        if sos is None:
            sos = scipy_signal.butter(
                4, [50.0, 15000.0], btype="band", fs=self._sample_rate, output="sos"
            )
            self._filter_cache[cache_key] = sos
        return scipy_signal.sosfilt(sos, audio, axis=0)

    def _apply_deemphasis(self, audio: np.ndarray) -> np.ndarray:
        """FM 75 µs de-emphasis filter — first-order IIR low-pass.

        Time constant τ = 75e-6 s → cutoff f_c = 1/(2πτ) ≈ 2122 Hz.
        """
        tau = 75e-6
        dt = 1.0 / self._sample_rate
        alpha = dt / (tau + dt)  # ~0.023 at 44.1 kHz
        # Apply per channel
        out = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            prev = 0.0
            for i in range(len(audio)):
                prev = prev + alpha * (audio[i, ch] - prev)
                out[i, ch] = prev
        return out

    def _apply_multipath(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Simulate multipath interference via delayed copies.

        Stronger multipath at lower RSSI. Delay of 30–100 µs at 44.1 kHz
        corresponds to ~1–4 sample delay.
        """
        if signal_db > -50:
            return audio  # strong signal, negligible multipath

        intensity = float(np.clip((-50 - signal_db) / 40.0, 0.0, 1.0))
        delay_samples = 3
        gain = intensity * 0.25

        delayed = np.zeros_like(audio)
        delayed[delay_samples:] = audio[:-delay_samples]
        return audio + gain * delayed

    def _mix_noise(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Add white noise floor — level inversely proportional to RSSI."""
        noise_amp = self._noise_level_from_rssi(signal_db, noise_floor_db=-95)
        noise = np.random.randn(*audio.shape).astype(np.float32) * noise_amp
        return audio + noise
