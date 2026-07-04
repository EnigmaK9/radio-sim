"""Signal propagation simulation — RSSI tracking, path loss, degradation."""

import numpy as np

from src.signal.noise import (
    PinkNoiseGenerator,
    apply_multipath,
    fading_envelope,
    impulsive_noise,
    pink_noise,
    white_noise,
)


class PropagationModel:
    """Distance-based path loss and environmental effects."""

    @staticmethod
    def free_space_path_loss(distance_km: float, frequency_mhz: float) -> float:
        """FSPL in dB: 20*log10(d_km) + 20*log10(f_MHz) + 32.45."""
        import math

        if distance_km <= 0.001:
            return 0.0
        return 20 * math.log10(distance_km) + 20 * math.log10(frequency_mhz) + 32.45

    @staticmethod
    def distance_from_rssi(rssi_dbm: float, frequency_mhz: float, tx_power_dbm: float = 50.0) -> float:
        """Approximate distance in km from received RSSI, given TX power."""
        import math

        path_loss = tx_power_dbm - rssi_dbm
        if path_loss <= 0:
            return 0.001
        # Inverse FSPL: d = 10^((path_loss - 32.45 - 20*log10(f))/20)
        return 10 ** ((path_loss - 32.45 - 20 * math.log10(frequency_mhz)) / 20.0)


class SignalSimulator:
    """Manages RSSI and applies cumulative signal degradation.

    Degradation intensity is driven by RSSI: strong signal → clean audio,
    weak signal → noisy, fading, impulsive interference.

    Usage:
        sim = SignalSimulator(initial_rssi_db=-45)
        degraded = sim.apply_degradation(audio, mode="fm")
    """

    def __init__(self, initial_rssi_db: float = -45.0):
        self.rssi: float = initial_rssi_db
        self.noise_floor: float = -100.0  # dBm thermal noise floor
        self.frequency_mhz: float = 98.0  # default FM center
        self._fading_phase: float = 0.0
        self._pink_gen = PinkNoiseGenerator()

    def update_rssi(self, delta_db: float) -> None:
        """Adjust signal strength. Clamped to [-120, -10] dBm."""
        self.rssi = float(np.clip(self.rssi + delta_db, -120.0, -10.0))

    def set_rssi(self, value_db: float) -> None:
        """Set absolute RSSI value."""
        self.rssi = float(np.clip(value_db, -120.0, -10.0))

    def noise_amplitude(self) -> float:
        """Noise amplitude scales inversely with signal strength.

        -30 dBm → ~0.0005 (near-silent noise floor)
        -60 dBm → ~0.015  (barely audible)
        -90 dBm → ~0.10   (noise dominates)
        """
        clamped = max(self.noise_floor, min(-10.0, self.rssi))
        normalized = (clamped - self.noise_floor) / (-20.0 - self.noise_floor)
        return (1.0 - normalized) * 0.12

    def apply_degradation(self, audio: np.ndarray, mode: str) -> np.ndarray:
        """Apply all signal degradation effects based on current RSSI and mode.

        Args:
            audio: (n_samples, n_channels) float32.
            mode: one of "fm", "am", "amhd", "fmhd", "dab".

        Returns:
            Degraded audio, same shape.
        """
        n_samples, n_channels = audio.shape

        if mode in ("fmhd", "dab"):
            # Digital modes: very low noise, rare glitches
            return self._degrade_digital(audio, mode)
        elif mode == "amhd":
            return self._degrade_hybrid(audio)
        elif mode == "am":
            return self._degrade_am(audio)
        else:  # fm
            return self._degrade_fm(audio)

    # ---- per-mode degradation ----

    def _degrade_fm(self, audio: np.ndarray) -> np.ndarray:
        """FM degradation: white noise + multipath at low RSSI."""
        noise_amp = self.noise_amplitude()
        noise = white_noise(audio.shape, amplitude=noise_amp * 0.6)

        # Multipath only at moderate-to-weak signal
        multipath_depth = 0.0
        if self.rssi < -50:
            multipath_depth = float(np.clip((-50 - self.rssi) / 40.0, 0.0, 0.8))

        out = audio + noise
        if multipath_depth > 0.01:
            out = apply_multipath(out, multipath_depth)

        # Fading at weak signal
        if self.rssi < -75:
            depth = float(np.clip((-75 - self.rssi) / 30.0, 0.0, 0.6))
            env = fading_envelope(len(out), rate_hz=0.3, depth=depth, sample_rate=44100)
            out = out * env[:, np.newaxis]

        return out

    def _degrade_am(self, audio: np.ndarray) -> np.ndarray:
        """AM degradation: strong static + crackle + deep fading."""
        noise_amp = self.noise_amplitude()
        n_samples, n_channels = audio.shape

        # Pink + white static (AM's characteristic frying sound)
        pink = self._pink_gen.generate(n_samples, n_channels) * (noise_amp * 1.2 / self._pink_gen.amplitude)
        white = white_noise(audio.shape, amplitude=noise_amp * 0.8)
        static = pink + white

        # Impulsive crackle
        crackle_rate = 0.5 + (noise_amp / 0.12) * 4.5  # 0.5–5 / sec
        crackle = impulsive_noise(
            n_samples, n_channels,
            rate_per_second=crackle_rate,
            amplitude=noise_amp * 2.0,
            sample_rate=44100,
        )

        # Deep Rayleigh-like fading
        fade_depth = 0.15 + (noise_amp / 0.12) * 0.7
        env = fading_envelope(n_samples, rate_hz=0.5, depth=fade_depth, sample_rate=44100)

        out = (audio + static + crackle) * env[:, np.newaxis]
        return out

    def _degrade_hybrid(self, audio: np.ndarray) -> np.ndarray:
        """AMHD hybrid: light noise + occasional frame drops at weak signal."""
        noise_amp = self.noise_amplitude() * 0.4  # Quieter than pure analog
        noise = white_noise(audio.shape, amplitude=noise_amp)

        out = audio + noise

        # Frame drops at weak signal (digital artifact)
        if self.rssi < -80:
            drop_prob = float(np.clip((-80 - self.rssi) / 30.0, 0.0, 0.1))
            out = self._inject_frame_drops(out, drop_prob)

        return out

    def _degrade_digital(self, audio: np.ndarray, mode: str) -> np.ndarray:
        """FMHD / DAB: near-perfect until cliff, then burst errors / mutes."""
        noise_amp = self.noise_amplitude() * 0.1  # Very low noise

        if mode == "dab":
            # DAB+: cliff effect — sudden mutes at threshold
            if self.rssi < -85:
                drop_prob = float(np.clip((-85 - self.rssi) / 20.0, 0.0, 0.5))
                out = self._inject_burst_errors(audio, drop_prob, mode="dab")
            else:
                out = audio + white_noise(audio.shape, amplitude=noise_amp)
        else:
            # FMHD: very rare glitches
            out = audio + white_noise(audio.shape, amplitude=noise_amp)
            if self.rssi < -90:
                drop_prob = float(np.clip((-90 - self.rssi) / 20.0, 0.0, 0.05))
                out = self._inject_burst_errors(out, drop_prob, mode="fmhd")

        return out

    # ---- internal helpers ----

    def _inject_frame_drops(self, audio: np.ndarray, drop_prob: float) -> np.ndarray:
        """Simulate frame drops — short silence gaps in digital audio."""
        n_samples = len(audio)
        drop_length = 50  # ~1 ms frames

        out = audio.copy()
        i = 0
        while i < n_samples:
            if np.random.random() < drop_prob:
                end = min(i + drop_length, n_samples)
                out[i:end, :] = 0.0
                i = end
            else:
                i += drop_length

        return out

    def _inject_burst_errors(self, audio: np.ndarray, error_prob: float, mode: str) -> np.ndarray:
        """Inject burst errors — longer mutes for DAB, shorter glitches for FMHD."""
        n_samples = len(audio)
        burst_len = 80 if mode == "dab" else 20  # samples (~1.8ms vs ~0.5ms)

        out = audio.copy()
        i = 0
        while i < n_samples:
            if np.random.random() < error_prob:
                end = min(i + burst_len + np.random.randint(0, burst_len), n_samples)
                # DAB: total mute; FMHD: attenuated, not muted
                if mode == "dab":
                    out[i:end, :] = 0.0
                else:
                    out[i:end, :] *= 0.3
                i = end
            else:
                i += burst_len

        return out
