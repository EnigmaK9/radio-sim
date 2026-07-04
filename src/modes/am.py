"""AM (Amplitude Modulation) radio mode — 530–1710 kHz, mono, 50Hz-5kHz."""

import numpy as np
from scipy import signal as scipy_signal

from src.modes.base import ModeParameters, RadioMode


class AMMode(RadioMode):
    """AM broadcast band: 530–1710 kHz, mono, 50 Hz – 5 kHz audio bandwidth.

    Processing chain:
      1. Mono downmix (AM is inherently mono)
      2. Bandpass 50 Hz – 5 kHz (AM channel spacing is 10 kHz)
      3. Static noise (1/f pink noise + white noise) proportional to RSSI
      4. Impulsive crackle events (ignition / lightning noise)
      5. Slow amplitude fading (ionospheric propagation)
    """

    params = ModeParameters(
        name="AM",
        frequency_min=530.0,
        frequency_max=1710.0,
        frequency_unit="kHz",
        audio_bandwidth_low=50.0,
        audio_bandwidth_high=5000.0,
        stereo=False,
    )

    def __init__(self):
        super().__init__()
        self._pink_state = np.zeros(5, dtype=np.float32)  # Voss-McCartney state

    # ---- public ----

    def process(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        audio = self._apply_mono(audio)
        audio = self._apply_bandpass(audio)
        audio = self._mix_static(audio, signal_db)
        audio = self._inject_crackle(audio, signal_db)
        audio = self._apply_fading(audio, signal_db)
        return audio

    # ---- processing stages ----

    def _apply_mono(self, audio: np.ndarray) -> np.ndarray:
        """Mix stereo to dual-mono (average L+R)."""
        if audio.shape[1] >= 2:
            mono = np.mean(audio[:, :2], axis=1, keepdims=True)
            return np.repeat(mono, audio.shape[1], axis=1)
        return audio

    def _apply_bandpass(self, audio: np.ndarray) -> np.ndarray:
        """Butterworth bandpass 50 Hz – 5 kHz (AM channel bandwidth)."""
        cache_key = ("bp", 50.0, 5000.0)
        sos = self._filter_cache.get(cache_key)
        if sos is None:
            sos = scipy_signal.butter(
                6, [50.0, 5000.0], btype="band", fs=self._sample_rate, output="sos"
            )
            self._filter_cache[cache_key] = sos
        return scipy_signal.sosfilt(sos, audio, axis=0)

    def _mix_static(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Mix pink noise + white noise — the classic AM 'frying' sound."""
        noise_amp = self._noise_level_from_rssi(signal_db, noise_floor_db=-95)

        # Pink noise via Voss-McCartney algorithm (approximate 1/f)
        white = np.random.randn(len(audio), audio.shape[1]).astype(np.float32)
        pink = self._generate_pink(len(audio), audio.shape[1])

        static = (0.6 * pink + 0.4 * white) * noise_amp * 1.5
        return audio + static

    def _inject_crackle(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Poisson-distributed impulse events — lightning/ignition noise.

        Rate increases as signal weakens: ~0.5/sec at -60 dBm → ~5/sec at -90 dBm.
        """
        n = len(audio)
        rate_per_sample = 0.001 + (1.0 - self._noise_level_from_rssi(signal_db) / 0.15) * 0.005
        impulses = np.random.random(n) < rate_per_sample
        n_impulses = int(np.sum(impulses))

        if n_impulses == 0:
            return audio

        crackle = np.zeros_like(audio)
        idx = np.where(impulses)[0]
        for i in idx:
            length = np.random.randint(10, 100)  # 0.2–2.3 ms burst
            end = min(i + length, n)
            # Damped impulse: exponential decay
            decay = np.exp(-np.linspace(0, 5, end - i))
            amp = np.random.uniform(0.05, 0.2)
            for ch in range(audio.shape[1]):
                crackle[i:end, ch] += amp * decay

        return audio + crackle

    def _apply_fading(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Slow ionospheric fading envelope — amplitude modulation at 0.1–2 Hz.

        Deeper and faster at lower RSSI. Uses filtered noise as envelope.
        """
        n = len(audio)
        # Generate slow random envelope
        fade_rate = 0.2 + (1.0 - self._noise_level_from_rssi(signal_db) / 0.15) * 1.8
        depth = 0.1 + (1.0 - self._noise_level_from_rssi(signal_db) / 0.15) * 0.5

        # Low-frequency noise for envelope
        raw = np.random.randn(n).astype(np.float32)
        sos = scipy_signal.butter(1, fade_rate, btype="low", fs=self._sample_rate, output="sos")
        envelope = scipy_signal.sosfilt(sos, raw)
        # Normalize and scale: envelope oscillates between 1-depth and 1
        envelope = envelope / (np.std(envelope) + 1e-8)
        envelope = 1.0 - depth * 0.5 + depth * 0.5 * envelope
        envelope = np.clip(envelope[:, np.newaxis], 0.1, 1.5)

        return audio * envelope.astype(np.float32)

    def _generate_pink(self, n_samples: int, n_channels: int) -> np.ndarray:
        """Approximate pink (1/f) noise via Voss-McCartney algorithm."""
        out = np.zeros((n_samples, n_channels), dtype=np.float32)
        for ch in range(n_channels):
            for i in range(n_samples):
                # Randomly replace one of 5 octave generators
                k = np.random.randint(5)
                self._pink_state[k] = np.random.randn()
                out[i, ch] = np.mean(self._pink_state)
        # Normalize
        out = out / (np.std(out) + 1e-8)
        return out
