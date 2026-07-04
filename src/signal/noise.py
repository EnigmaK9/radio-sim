"""Noise generators for radio signal simulation.

Each generator returns a numpy array matching the input shape and sample rate,
suitable for additive mixing with the audio signal.
"""

import numpy as np
from scipy import signal as scipy_signal


def white_noise(shape: tuple[int, ...], amplitude: float = 0.01) -> np.ndarray:
    """Gaussian white noise — the thermal noise floor of any receiver.

    Args:
        shape: output shape, e.g. (n_samples, n_channels).
        amplitude: RMS amplitude of the noise.
    """
    return np.random.randn(*shape).astype(np.float32) * amplitude


def pink_noise(n_samples: int, n_channels: int = 2, amplitude: float = 0.01) -> np.ndarray:
    """Approximate 1/f (pink) noise via the Voss-McCartney algorithm.

    More natural-sounding than pure white noise — used for analog
    receiver hiss and atmospheric noise.
    """
    n_octaves = 5
    state = np.zeros(n_octaves, dtype=np.float32)
    out = np.zeros((n_samples, n_channels), dtype=np.float32)

    for ch in range(n_channels):
        for i in range(n_samples):
            k = np.random.randint(n_octaves)
            state[k] = np.random.randn()
            out[i, ch] = np.mean(state)

    # Normalize to unit variance
    std = np.std(out) + 1e-8
    return (out / std) * amplitude


def impulsive_noise(
    n_samples: int,
    n_channels: int = 2,
    rate_per_second: float = 1.0,
    amplitude: float = 0.3,
    sample_rate: int = 44100,
) -> np.ndarray:
    """Random impulse train — simulates lightning, ignition, power-line noise.

    Args:
        n_samples: number of samples to generate.
        n_channels: output channels.
        rate_per_second: average number of impulses per second.
        amplitude: peak amplitude of each impulse.
        sample_rate: used to convert rate to per-sample probability.
    """
    prob_per_sample = rate_per_second / sample_rate
    impulses = np.random.random(n_samples) < prob_per_sample
    idx = np.where(impulses)[0]

    out = np.zeros((n_samples, n_channels), dtype=np.float32)
    for i in idx:
        length = np.random.randint(5, 80)  # 0.1–1.8 ms burst
        end = min(i + length, n_samples)
        decay = np.exp(-np.linspace(0, 4, end - i))
        amp = np.random.uniform(0.3, 1.0) * amplitude
        for ch in range(n_channels):
            out[i:end, ch] += amp * decay

    return out


def fading_envelope(
    n_samples: int,
    rate_hz: float = 0.5,
    depth: float = 0.3,
    sample_rate: int = 44100,
) -> np.ndarray:
    """Slow amplitude modulation envelope for ionospheric fading simulation.

    Generates a 1-D envelope vector that oscillates around 1.0 with
    the given rate and depth. Multiply with audio to apply fading.

    Args:
        n_samples: envelope length.
        rate_hz: fade oscillation rate (0.1–2 Hz typical).
        depth: 0.0 = no fading, 1.0 = deep fades to near-zero.
        sample_rate: audio sample rate.
    """
    # Generate low-pass filtered noise for natural fade shape
    raw = np.random.randn(n_samples).astype(np.float32)
    sos = scipy_signal.butter(2, rate_hz * 2, btype="low", fs=sample_rate, output="sos")
    envelope = scipy_signal.sosfilt(sos, raw)

    # Normalize and map to [1-depth, 1+depth*0.2]
    envelope = envelope / (np.std(envelope) + 1e-8)
    envelope = 1.0 - depth * 0.5 + depth * 0.5 * np.tanh(envelope)
    return np.clip(envelope.astype(np.float32), 0.05, 1.3)


def multipath_ir(
    n_taps: int = 3,
    max_delay_samples: int = 5,
    depth: float = 0.3,
) -> np.ndarray:
    """Generate a multipath impulse response (comb filter kernel).

    Args:
        n_taps: number of echo paths (including direct).
        max_delay_samples: maximum delay in samples.
        depth: echo gain relative to direct path.

    Returns:
        1-D float32 array representing the FIR kernel.
    """
    ir = np.zeros(max_delay_samples + 1, dtype=np.float32)
    ir[0] = 1.0  # direct path
    for _ in range(n_taps - 1):
        delay = np.random.randint(1, max_delay_samples + 1)
        gain = np.random.uniform(0.01, depth)
        ir[delay] += gain
    return ir


def apply_multipath(audio: np.ndarray, depth: float) -> np.ndarray:
    """Apply multipath comb filtering to audio.

    Args:
        audio: (n_samples, n_channels) float32.
        depth: echo intensity, 0 = none, 1 = strongest.
    """
    if depth <= 0.01:
        return audio

    delay = 3  # samples (~68 µs at 44.1 kHz)
    gain = depth * 0.3
    delayed = np.zeros_like(audio)
    delayed[delay:] = audio[:-delay]
    return audio + gain * delayed
