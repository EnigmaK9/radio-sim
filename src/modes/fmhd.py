"""FMHD (FM HD Radio) — hybrid digital FM, 87.5–108 MHz, 20Hz-20kHz, CD quality."""

import numpy as np
from scipy import signal as scipy_signal

from src.modes.base import ModeParameters, RadioMode
from src.signal.filters import PRESETS, apply_eq, stereo_blend
from src.signal.noise import white_noise


class FMHDMode(RadioMode):
    """FM HD Radio: hybrid analog-digital on the FM band.

    Digital sidebands around the analog FM carrier provide near-CD-quality
    audio (20 Hz – 20 kHz) and multicasting (up to 3 subchannels on one frequency).

    At strong RSSI (> -60 dBm): full digital, transparent quality.
    At weak RSSI (< -95 dBm): blends toward analog FM quality.
    """

    params = ModeParameters(
        name="FMHD",
        frequency_min=87.5,
        frequency_max=108.0,
        frequency_unit="MHz",
        audio_bandwidth_low=20.0,
        audio_bandwidth_high=20000.0,
        stereo=True,
    )

    MAX_SUBCHANNELS = 3

    def __init__(self, subchannel: int = 0):
        super().__init__()
        self.subchannel = max(0, min(subchannel, self.MAX_SUBCHANNELS - 1))
        # ponytail: hardcoded subchannel qualities — real HD Radio varies by station config
        self._subchannel_bitrates = [300, 128, 64]  # kbps equivalent quality
        self._filter_cache = {}

    def process(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        blend = float(np.clip((-80.0 - signal_db) / 30.0, 0.0, 1.0))

        digital = self._digital_path(audio.copy(), signal_db)
        analog = self._analog_path(audio.copy(), signal_db)

        if blend <= 0.0:
            return digital
        elif blend >= 1.0:
            return analog
        return (1.0 - blend) * digital + blend * analog

    # ---- paths ----

    def _digital_path(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Full-bandwidth digital processing with near-transparent quality."""
        audio = apply_eq(audio, PRESETS["fmhd"], self._sample_rate)

        # Subchannel quality degradation
        if self.subchannel > 0:
            audio = self._apply_subchannel_quality(audio)

        # Very low noise floor
        noise_amp = self._noise_level_from_rssi(signal_db, noise_floor_db=-100) * 0.05
        audio += white_noise(audio.shape, amplitude=noise_amp)

        # Rare glitches only at extreme weak signal
        if signal_db < -90:
            audio = self._inject_glitches(audio, signal_db)

        return audio

    def _analog_path(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Analog FM fallback (similar to FMMode but lighter)."""
        audio = apply_eq(audio, PRESETS["fm"], self._sample_rate)
        audio = stereo_blend(audio, float(np.clip((-70.0 - signal_db) / 20.0, 0.0, 1.0)))

        noise_amp = self._noise_level_from_rssi(signal_db, noise_floor_db=-95) * 0.4
        audio += white_noise(audio.shape, amplitude=noise_amp)

        return audio

    def _apply_subchannel_quality(self, audio: np.ndarray) -> np.ndarray:
        """Degrade quality for subchannels — lower bitrate simulation.

        Simulates lossy compression artifacts: slight high-frequency roll-off
        and quantization noise proportional to the subchannel bitrate.
        """
        br = self._subchannel_bitrates[self.subchannel]
        # Quality factor: 300 kbps = 1.0 (transparent), 64 kbps = 0.3
        quality = br / 300.0

        # High-frequency roll-off for low-bitrate subchannels
        if quality < 0.5:
            cache_key = ("fmhd_sub", self.subchannel)
            if cache_key not in self._filter_cache:
                cutoff = 8000 + quality * 8000
                self._filter_cache[cache_key] = scipy_signal.butter(
                    2, cutoff, btype="low", fs=self._sample_rate, output="sos"
                )
            sos = self._filter_cache[cache_key]
            audio = scipy_signal.sosfilt(sos, audio, axis=0)

        # Quantization noise
        quant_noise = np.random.randn(*audio.shape).astype(np.float32) * (1.0 - quality) * 0.003
        audio += quant_noise

        return audio

    def _inject_glitches(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Very rare digital glitches at threshold."""
        prob = float(np.clip((-90.0 - signal_db) / 20.0, 0.0, 0.02))
        n = len(audio)
        glitch_len = 15
        i = 0
        while i < n:
            if np.random.random() < prob:
                end = min(i + glitch_len, n)
                audio[i:end, :] *= 0.3  # attenuated, not muted
                i = end
            else:
                i += glitch_len
        return audio
