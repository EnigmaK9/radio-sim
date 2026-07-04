# Step 03 — Basic Modes (FM & AM)

## Goal

Implement the `RadioMode` abstract base class and the two analog modes — FM and AM. Each mode applies its characteristic frequency response, stereo/mono processing, and basic noise profile to an audio chunk.

## Files Created

```
src/modes/
├── __init__.py
├── base.py      # RadioMode ABC
├── fm.py        # FMMode
└── am.py        # AMMode
```

## Design

### `RadioMode` ABC (`base.py`)

```python
class RadioMode(ABC):
    name: str                          # "FM", "AM", etc.
    frequency_range: tuple[float, float]  # (min, max) in MHz or kHz
    audio_bandwidth: tuple[float, float]  # (low_cut, high_cut) Hz
    stereo: bool                       # True for stereo modes
    sample_rate: int = 44100

    @abstractmethod
    def process(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        """Apply mode-specific processing. audio shape: (n_samples, n_channels)."""
        ...

    def validate_frequency(self, freq: float) -> bool:
        """Check freq is within this mode's band."""
        ...

    def get_rds_metadata(self) -> dict:
        """Return RDS/station info dictionary."""
        ...
```

### `FMMode` (`fm.py`)

- **Frequency band**: 87.5–108.0 MHz
- **Audio bandwidth**: 50 Hz – 15 kHz
- **Processing chain**:
  1. High-pass Butterworth @ 50 Hz (removes subsonic rumble)
  2. Low-pass Butterworth @ 15 kHz (FM channel bandwidth limit)
  3. 75 µs de-emphasis filter (standard FM pre-emphasis compensation)
  4. Stereo passthrough (FM is stereo; 19 kHz pilot tone is implied, not synthesized for simplicity)
  5. Additive white Gaussian noise floor at ~-60 dB (simulates receiver noise)
- **RDS metadata**: station name, program type, radiotext (populated from audio source tags)

### `AMMode` (`am.py`)

- **Frequency band**: 530–1710 kHz
- **Audio bandwidth**: 50 Hz – 5 kHz (narrower — AM channel spacing is 10 kHz)
- **Processing chain**:
  1. High-pass @ 50 Hz
  2. Low-pass @ 5 kHz (steep roll-off)
  3. Mono mixdown: average L+R channels → duplicate to both
  4. Modulated static: amplitude-modulated noise envelope (simulates ionospheric fading)
  5. Impulsive noise injection: occasional crackle/pop events (ignition noise)
  6. Higher noise floor at ~-40 dB (AM is inherently noisier)

## Filter Implementation

Use `scipy.signal.butter` + `scipy.signal.sosfilt` (second-order sections) for numerical stability:

```python
def _design_bandpass(low, high, sr, order=4):
    sos = scipy.signal.butter(order, [low, high], btype='band', fs=sr, output='sos')
    return sos
```

De-emphasis for FM: first-order IIR with time constant τ = 75 µs (USA standard).

## Integration with Engine

The mode's `process()` method is registered as a processor in `AudioPipeline.processors`. Order in the chain:

```
[Source] → [RadioMode.process()] → [SignalSimulator (Step 04)] → [Output]
```

## Verification

```bash
python -c "
import numpy as np
from src.modes.fm import FMMode
from src.modes.am import AMMode

fm = FMMode()
am = AMMode()

# Generate 1 second of 1 kHz sine tone
t = np.linspace(0, 1, 44100, endpoint=False)
tone = np.column_stack([0.5 * np.sin(2 * np.pi * 1000 * t)] * 2)

fm_out = fm.process(tone, signal_db=-45)
am_out = am.process(tone, signal_db=-45)

print(f'FM output shape: {fm_out.shape}, range: [{fm_out.min():.3f}, {fm_out.max():.3f}]')
print(f'AM output shape: {am_out.shape}, range: [{am_out.min():.3f}, {am_out.max():.3f}]')
print('Modes OK')
"
```

## Dependencies

- **Step 01** — package structure.
- **Step 02** — `AudioPipeline` uses `RadioMode.process()` as a processor stage.
- **Step 04** — signal simulation enhances noise injection; basic noise is inline for now.
