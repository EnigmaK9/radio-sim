"""RadioMode abstract base class — defines the interface for all radio modes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ModeParameters:
    """Static configuration for a radio mode."""

    name: str
    frequency_min: float  # MHz (FM/FMHD/DAB) or kHz (AM/AMHD)
    frequency_max: float
    frequency_unit: str  # "MHz" or "kHz"
    audio_bandwidth_low: float  # Hz, high-pass cutoff
    audio_bandwidth_high: float  # Hz, low-pass cutoff
    stereo: bool
    sample_rate: int = 44100


class RadioMode(ABC):
    """Abstract base for all radio broadcast modes.

    Each mode applies its characteristic frequency response, stereo/mono
    processing, and noise profile to an audio chunk. Modes are stateless
    aside from cached filter coefficients.
    """

    params: ModeParameters

    def __init__(self):
        self._sample_rate = 44100
        self._filter_cache: dict = {}  # ponytail: cache sos coefs per frequency param

    @abstractmethod
    def process(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Apply mode-specific processing.

        Args:
            audio: float32 array shape (n_samples, n_channels), range [-1, 1].
            signal_db: current RSSI in dBm (e.g. -45 = strong, -90 = weak).

        Returns:
            Processed audio, same shape as input.
        """
        ...

    def validate_frequency(self, freq: float) -> bool:
        """Check whether `freq` is within this mode's broadcast band."""
        return self.params.frequency_min <= freq <= self.params.frequency_max

    @property
    def frequency_step(self) -> float:
        """Tuning step size. FM uses 0.1 MHz / 100 kHz, AM uses 1 kHz / 10 kHz."""
        if self.params.frequency_unit == "MHz":
            return 0.1
        return 1.0  # kHz

    @property
    def name(self) -> str:
        return self.params.name

    @property
    def frequency_range(self) -> tuple[float, float]:
        return (self.params.frequency_min, self.params.frequency_max)

    @property
    def stereo(self) -> bool:
        return self.params.stereo

    def rds_metadata(self, source_meta: dict | None = None) -> dict:
        """Return simulated RDS / station metadata."""
        meta = {
            "station": f"{self.name} {self.params.frequency_min + (self.params.frequency_max - self.params.frequency_min) / 2:.1f}",
            "program_type": "Music",
            "radiotext": "",
        }
        if source_meta:
            meta["radiotext"] = f"{source_meta.get('artist', '')} — {source_meta.get('title', '')}"
        return meta

    def display_info(self) -> dict:
        """Display information for the TUI station info panel."""
        p = self.params
        bw_l = int(p.audio_bandwidth_low)
        bw_h = int(p.audio_bandwidth_high)

        band = f"{p.frequency_min} – {p.frequency_max} {p.frequency_unit}"
        bw = f"{bw_l} Hz – {bw_h / 1000:.0f} kHz" if bw_h >= 1000 else f"{bw_l} Hz – {bw_h} Hz"

        if p.stereo:
            stereo = "● Yes (digital)" if p.name == "AMHD" else "● Yes"
        else:
            stereo = "○ No"

        descriptions = {
            "FM": "Hiss + multipath",
            "AM": "Static + fading",
            "AMHD": "Digital artifacts",
            "FMHD": "Rare glitches",
            "DAB+": "Burst errors / cliff",
        }

        return {
            "band": band,
            "audio_bw": bw,
            "stereo": stereo,
            "noise": descriptions.get(p.name, ""),
        }

    def _noise_level_from_rssi(self, signal_db: float, noise_floor_db: float = -100) -> float:
        """Convert RSSI in dBm to a noise amplitude factor.

        Strong signal (-30 dBm) → ~0.001 amplitude
        Weak signal (-90 dBm) → ~0.1 amplitude
        """
        # Clamp RSSI between noise floor and "perfect" signal
        clamped = max(noise_floor_db, min(-20.0, signal_db))
        # Linear mapping: -100 dBm → 1.0 noise, -20 dBm → 0.0 noise
        normalized = (clamped - noise_floor_db) / (-20.0 - noise_floor_db)
        # Invert: strong signal = low noise
        noise_factor = 1.0 - normalized
        # Scale to amplitude range
        return noise_factor * 0.15  # max noise amplitude at threshold
