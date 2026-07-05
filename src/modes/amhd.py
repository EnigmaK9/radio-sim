"""AMHD (AM HD Radio) — hybrid digital AM, 530–1710 kHz, 50Hz-15kHz, stereo."""

import numpy as np

from src.modes.base import ModeParameters, RadioMode
from src.signal.filters import PRESETS, apply_eq, mono_mixdown
from src.signal.noise import fading_envelope, pink_noise, white_noise


class AMHDMode(RadioMode):
    """AM HD Radio: hybrid analog-digital on the AM band.

    Maintains two parallel processing paths:
      - Analog path: same as AM but quieter noise floor (backward compatible).
      - Digital path: full 15 kHz bandwidth, stereo, low-bitrate artifacts.

    At strong RSSI (> -70 dBm): full digital quality.
    At weak RSSI (< -90 dBm): blends toward analog AM quality.
    """

    params = ModeParameters(
        name="AMHD",
        frequency_min=530.0,
        frequency_max=1710.0,
        frequency_unit="kHz",
        audio_bandwidth_low=50.0,
        audio_bandwidth_high=15000.0,
        stereo=True,
    )

    def process(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        # Compute blend factor: 0 = full digital, 1 = full analog
        blend = float(np.clip((-80.0 - signal_db) / 20.0, 0.0, 1.0))

        # Digital path
        digital = self._digital_path(audio.copy(), signal_db)

        # Analog fallback path
        analog = self._analog_path(audio.copy(), signal_db)

        # Crossfade
        if blend <= 0.0:
            return digital.astype(np.float32, copy=False)
        elif blend >= 1.0:
            return analog.astype(np.float32, copy=False)
        return ((1.0 - blend) * digital + blend * analog).astype(np.float32, copy=False)

    # ---- paths ----

    def _digital_path(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Full-bandwidth stereo digital processing."""
        audio = apply_eq(audio, PRESETS["amhd"], self._sample_rate)

        # Light quantization noise (lossy codec simulation)
        noise_amp = self._noise_level_from_rssi(signal_db, noise_floor_db=-95) * 0.3
        audio += white_noise(audio.shape, amplitude=noise_amp)

        # Frame drops at weak signal
        if signal_db < -80:
            audio = self._inject_drops(audio, signal_db)

        return audio

    def _analog_path(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Mono, bandwidth-limited analog fallback (quieter than pure AM)."""
        audio = mono_mixdown(audio)
        audio = apply_eq(audio, PRESETS["am"], self._sample_rate)

        noise_amp = self._noise_level_from_rssi(signal_db, noise_floor_db=-95) * 0.6
        n_samples, n_channels = audio.shape

        audio += pink_noise(n_samples, n_channels, amplitude=noise_amp * 0.5)
        audio += white_noise(audio.shape, amplitude=noise_amp * 0.3)

        if signal_db < -85:
            env = fading_envelope(n_samples, rate_hz=1.0, depth=0.4, sample_rate=self._sample_rate)
            audio = audio * env[:, np.newaxis]

        return audio

    def _inject_drops(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Frame drops: brief silence gaps in digital audio stream."""
        drop_prob = float(np.clip((-80.0 - signal_db) / 40.0, 0.0, 0.15))
        n = len(audio)
        frame = 60  # samples
        i = 0
        while i < n:
            if np.random.random() < drop_prob:
                end = min(i + frame, n)
                audio[i:end, :] = 0.0
                i = end
            else:
                i += frame
        return audio
