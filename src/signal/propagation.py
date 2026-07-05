"""Signal propagation simulation — RSSI tracking, path loss."""

import numpy as np


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
    """Tracks RSSI state for the radio pipeline."""

    def __init__(self, initial_rssi_db: float = -45.0):
        self.rssi: float = initial_rssi_db
        self.noise_floor: float = -100.0  # dBm thermal noise floor

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
        clamped = max(self.noise_floor, min(-20.0, self.rssi))
        normalized = (clamped - self.noise_floor) / (-20.0 - self.noise_floor)
        return (1.0 - normalized) * 0.12

