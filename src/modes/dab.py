"""DAB/DAB+ (Digital Audio Broadcasting) — 174–240 MHz, 20Hz-20kHz, AAC+."""

import numpy as np
from scipy import signal as scipy_signal

from src.modes.base import ModeParameters, RadioMode
from src.signal.filters import PRESETS, apply_eq
from src.signal.noise import white_noise


class DABMode(RadioMode):
    """DAB+ digital radio: Band III (174–240 MHz), fully digital.

    Key characteristics:
      - HE-AAC v2 codec (simulated via SBR-like HF smoothing at low bitrates).
      - COFDM modulation → "cliff effect": perfect or mute, no gradual degradation.
      - Burst errors cause short silence gaps, not noise.
      - Multiplex: one frequency carries multiple programs (ensemble).

    The `bitrate` parameter controls codec quality simulation (32–256 kbps).
    """

    params = ModeParameters(
        name="DAB+",
        frequency_min=174.0,
        frequency_max=240.0,
        frequency_unit="MHz",
        audio_bandwidth_low=20.0,
        audio_bandwidth_high=20000.0,
        stereo=True,
    )

    def __init__(self, bitrate_kbps: int = 128, program_index: int = 0):
        super().__init__()
        self.bitrate = max(32, min(256, bitrate_kbps))
        self.program_index = program_index
        self._burst_count: int = 0
        self._ensemble_programs = [
            {"label": "MAIN", "bitrate": 192},
            {"label": "EXTRA", "bitrate": 128},
            {"label": "NEWS", "bitrate": 64},
            {"label": "SPORT", "bitrate": 96},
        ]

    @property
    def ensemble_labels(self) -> list[str]:
        return [p["label"] for p in self._ensemble_programs]

    def select_program(self, index: int) -> None:
        self.program_index = max(0, min(index, len(self._ensemble_programs) - 1))

    def process(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        audio = apply_eq(audio, PRESETS["dab"], self._sample_rate)

        # HE-AAC artifact simulation (intensity depends on bitrate)
        audio = self._apply_codec_artifacts(audio)

        # Minimal noise floor (digital — no analog noise)
        noise_amp = self._noise_level_from_rssi(signal_db, noise_floor_db=-110) * 0.02
        audio += white_noise(audio.shape, amplitude=noise_amp)

        # Cliff effect: burst errors and mutes below threshold
        audio = self._apply_burst_errors(audio, signal_db)

        return audio.astype(np.float32, copy=False)

    def _apply_codec_artifacts(self, audio: np.ndarray) -> np.ndarray:
        """Simulate HE-AAC v2 artifacts at different bitrates.

        Low bitrate (< 96 kbps): SBR-like HF smoothing, temporal smearing.
        High bitrate (≥ 192 kbps): essentially transparent.
        """
        quality = self.bitrate / 256.0

        # Spectral Band Replication: at low bitrate, HF is synthesized
        # → simulate as gentle low-pass and slight HF noise
        if quality < 0.6:
            cutoff = 6000 + quality * 10000  # 6 kHz at worst, ~12 kHz at mid
            sos = scipy_signal.butter(
                4, cutoff, btype="low", fs=self._sample_rate, output="sos"
            )
            audio = scipy_signal.sosfilt(sos, audio, axis=0)

            # SBR artifacts: slight HF noise to simulate synthesis
            hf_noise = (
                np.random.randn(*audio.shape).astype(np.float32)
                * (1.0 - quality)
                * 0.004
            )
            # High-pass the noise so it only affects HF
            sos_hp = scipy_signal.butter(
                2, 4000, btype="high", fs=self._sample_rate, output="sos"
            )
            hf_noise = scipy_signal.sosfilt(sos_hp, hf_noise, axis=0)
            audio += hf_noise

        # Temporal pre-echo / smearing at low bitrate
        if quality < 0.4:
            kernel = np.exp(-np.linspace(0, 3, 8))
            kernel = kernel / kernel.sum()
            for ch in range(audio.shape[1]):
                audio[:, ch] = np.convolve(audio[:, ch], kernel, mode="same")

        return audio

    def _apply_burst_errors(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """COFDM burst errors — the DAB 'cliff effect'.

        Above threshold (~ -85 dBm): perfect audio.
        Below threshold: rapidly increasing brief silence gaps.
        """
        n = len(audio)

        # Burst error probability
        if signal_db > -80:
            prob = 0.0
        elif signal_db > -90:
            prob = float((-80.0 - signal_db) / 10.0 * 0.01)  # 0–1%
        else:
            prob = float(min(0.3, (-90.0 - signal_db) / 30.0 * 0.3))  # 1–30%

        if prob <= 0.0:
            return audio

        burst_min = 20  # ~0.5 ms
        burst_max = 120  # ~2.7 ms
        gap_min = 200  # min samples between bursts

        out = audio.copy()
        last_burst_end = -gap_min

        i = 0
        while i < n:
            if i - last_burst_end >= gap_min and np.random.random() < prob:
                burst_len = np.random.randint(burst_min, burst_max)
                end = min(i + burst_len, n)
                out[i:end, :] = 0.0  # Total silence — DAB mutes, doesn't get noisy
                last_burst_end = end
                i = end
            else:
                i += 1

        return out
