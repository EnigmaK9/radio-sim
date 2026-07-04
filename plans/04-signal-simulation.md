# Step 04 — Signal Simulation

## Goal

Build the signal simulation layer: a `SignalSimulator` that tracks RSSI (Received Signal Strength Indicator), applies propagation effects, and injects realistic noise that varies with signal strength. Extract noise generators and filter presets into their own modules.

## Files Created

```
src/signal/
├── __init__.py
├── noise.py         # Noise generators: white, pink, impulsive, fading envelope
├── filters.py       # EQ presets, bandpass/bandstop, de-emphasis per mode
└── propagation.py   # SignalSimulator, PropagationModel, RSSI tracking
```

## Design

### Noise Generators (`noise.py`)

```python
def white_noise(n_samples: int, amplitude: float = 0.01) -> np.ndarray:
    """Uniform Gaussian noise. The thermal noise floor of any receiver."""
    ...

def pink_noise(n_samples: int, amplitude: float = 0.01) -> np.ndarray:
    """1/f noise via Voss-McCartney algorithm. More natural-sounding hiss."""
    ...

def impulsive_noise(n_samples: int, rate: float = 0.001, amplitude: float = 0.3) -> np.ndarray:
    """Random impulse train — simulates lightning, ignition, power-line noise."""
    ...

def fading_envelope(n_samples: int, rate: float = 0.5, depth: float = 0.3, sample_rate: int = 44100) -> np.ndarray:
    """Slow amplitude modulation envelope — simulates ionospheric fading.
    rate in Hz, depth 0.0-1.0."""
    ...

def multipath_comb(n_samples: int, delay_ms: float = 0.5, depth: float = 0.3, sample_rate: int = 44100) -> np.ndarray:
    """Comb filter from ground/sky wave interference — delayed copy mixed with original."""
    ...
```

### Filter Presets (`filters.py`)

```python
@dataclass
class EQPreset:
    """Biquad/Butterworth filter preset for a mode."""
    name: str
    highpass: float | None     # Hz, None = no highpass
    lowpass: float | None      # Hz, None = no lowpass
    deemphasis_tau: float | None  # µs, None = no deemphasis
    order: int = 4

PRESETS = {
    "fm":    EQPreset("FM", highpass=50, lowpass=15000, deemphasis_tau=75),
    "am":    EQPreset("AM", highpass=50, lowpass=5000, deemphasis_tau=None),
    "amhd":  EQPreset("AMHD", highpass=50, lowpass=15000, deemphasis_tau=None),
    "fmhd":  EQPreset("FMHD", highpass=20, lowpass=20000, deemphasis_tau=None),
    "dab":   EQPreset("DAB+", highpass=20, lowpass=20000, deemphasis_tau=None),
}

def apply_eq(audio: np.ndarray, preset: EQPreset, sample_rate: int = 44100) -> np.ndarray:
    """Apply Butterworth bandpass + de-emphasis from a preset."""
    ...

def mono_mixdown(audio: np.ndarray) -> np.ndarray:
    """Convert stereo to dual-mono (L+R)/2."""
    ...
```

### Propagation Model (`propagation.py`)

```python
class SignalSimulator:
    """Manages RSSI and applies cumulative signal degradation."""

    def __init__(self, initial_rssi_db: float = -45.0):
        self.rssi: float = initial_rssi_db     # dBm
        self.noise_floor: float = -100.0        # dBm (thermal)
        self.propagation = PropagationModel()

    def update_rssi(self, delta_db: float) -> None:
        """Adjust signal strength. Positive = stronger, negative = weaker."""
        ...

    def get_noise_amplitude(self) -> float:
        """Noise amplitude scales inversely with signal strength.
        Strong signal (-30 dBm) → very low noise.
        Weak signal (-90 dBm) → high noise, near threshold."""
        ...

    def apply_degradation(self, audio: np.ndarray, mode_noise_profile: str) -> np.ndarray:
        """Apply all signal degradation: noise floor, fading, impulsive events.
        Intensity of each is driven by current RSSI."""
        ...

class PropagationModel:
    """Distance-based path loss and multipath simulation."""

    def free_space_path_loss(self, distance_km: float, frequency_mhz: float) -> float:
        """FSPL in dB. 20*log10(d) + 20*log10(f) + 32.45."""
        ...

    def multipath_response(self, distance_km: float) -> np.ndarray:
        """Returns IR kernel for multipath comb filtering."""
        ...
```

## RSSI → Noise Mapping

| RSSI (dBm) | Signal Quality | Noise Level | Perceived Audio |
|------------|---------------|-------------|-----------------|
| -30        | Excellent      | Near zero   | Pristine |
| -45        | Very good      | Barely audible hiss | Clean |
| -60        | Fair           | Noticeable hiss, occasional crackle | Listenable |
| -75        | Weak           | Strong noise, fading dips | Marginal |
| -90        | Threshold      | Noise dominates signal | Barely intelligible |
| -100       | Noise floor    | Pure noise | Unusable |

## Integration

The `SignalSimulator` wraps the mode processor in the pipeline:

```
[Source] → [RadioMode.process()] → [SignalSimulator.apply_degradation()] → [Output]
```

The mode applies its EQ/filter characteristics. The simulator then layers on environment effects driven by RSSI.

## Verification

```bash
python -c "
import numpy as np
from src.signal.noise import white_noise, pink_noise, impulsive_noise, fading_envelope
from src.signal.filters import PRESETS, apply_eq
from src.signal.propagation import SignalSimulator

tone = np.column_stack([0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100))] * 2)

# Test filter
eqd = apply_eq(tone, PRESETS['fm'])
print(f'EQ output shape: {eqd.shape}')

# Test simulator at different RSSI levels
sim = SignalSimulator(initial_rssi_db=-45)
clean = sim.apply_degradation(tone, 'fm')
sim.update_rssi(-50)  # drop to -95 dBm
noisy = sim.apply_degradation(tone, 'fm')
print(f'Strong RSSI range: [{clean.min():.3f}, {clean.max():.3f}]')
print(f'Weak RSSI range:   [{noisy.min():.3f}, {noisy.max():.3f}]')
print('Signal simulation OK')
"
```

## Dependencies

- **Step 01–02** — package, engine.
- **Step 03** — mode processors supply the EQ stage; simulator adds environment effects on top.
