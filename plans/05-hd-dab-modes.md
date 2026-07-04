# Step 05 — HD Radio & DAB+ Modes

## Goal

Implement the three digital/hybrid radio modes: AMHD (AM HD Radio), FMHD (FM HD Radio), and DAB+ (Digital Audio Broadcasting). These modes share wider bandwidth, stereo, and digital-domain noise characteristics (packet loss, bitrate artifacts, burst errors) vs. the continuous noise of analog.

## Files Created

```
src/modes/
├── amhd.py    # AMHDMode — hybrid digital AM
├── fmhd.py    # FMHDMode — hybrid digital FM
└── dab.py     # DABMode — fully digital broadcasting
```

## Design

### `AMHDMode` (`amhd.py`)

- **Frequency band**: 530–1710 kHz (same dial as AM)
- **Audio bandwidth**: 50 Hz – 15 kHz (3× AM analog bandwidth)
- **Hybrid nature**: Digital audio coexists with legacy analog AM on same frequency. If signal is weak, falls back to analog-quality audio.
- **Processing chain**:
  1. EQ: bandpass 50 Hz – 15 kHz (wider than AM)
  2. Stereo: true stereo (digital subcarrier carries second channel)
  3. Noise model: low-level quantization noise floor, occasional frame-drop mutes (~50 ms gaps at ~0.1% rate at typical RSSI)
  4. Fallback simulation: if RSSI < -80 dBm, blend toward AM-like quality (narrower BW, more noise)

### `FMHDMode` (`fmhd.py`)

- **Frequency band**: 87.5–108 MHz (same dial as FM)
- **Audio bandwidth**: 20 Hz – 20 kHz (full CD bandwidth)
- **Hybrid nature**: Digital sidebands around analog FM carrier. Near-transparent quality.
- **Processing chain**:
  1. EQ: bandpass 20 Hz – 20 kHz (essentially flat within audible range)
  2. Stereo: full discrete stereo
  3. Noise model: very rare glitches (frame errors at ~0.01% rate), subtle quantization noise
  4. Multicasting concept: `subchannels` property — HD Radio can carry 2–3 programs on one frequency. Simulated as alternate audio stream placeholder.

### `DABMode` (`dab.py`)

- **Frequency band**: 174–240 MHz (Band III) — completely separate from FM/AM bands
- **Audio bandwidth**: 20 Hz – 20 kHz
- **Codec**: HE-AAC v2 (simulated — we apply slight high-frequency smoothing to mimic AAC+ perceptual coding)
- **Processing chain**:
  1. EQ: bandpass 20 Hz – 20 kHz
  2. Stereo: full discrete stereo
  3. Noise model: **burst errors** — DAB uses COFDM; when signal drops below threshold, entire OFDM symbols are lost → brief silence gaps (20–80 ms) rather than gradual noise increase. This is the key DAB+ characteristic: it's either perfect or it mutes.
  4. Signal threshold: below ~-85 dBm → rapid increase in mute events (the "digital cliff")

## Noise Model Comparison (Digital vs. Analog)

| Mode | Noise Character | Degradation Behavior |
|------|----------------|---------------------|
| FM | Continuous hiss + multipath | Gradual — gets noisier as RSSI drops |
| AM | Continuous static + fading | Gradual — noise rises smoothly |
| **AMHD** | Quantization + frame drops | Mostly clean, then artifacts appear abruptly |
| **FMHD** | Rare glitches | Stays clean until very weak, then drops |
| **DAB+** | Burst mutes (silence gaps) | Perfect → occasional mutes → frequent mutes → silence |

## Implementation Pattern

Each digital mode extends `RadioMode` and overrides `process()`:

```python
class AMHDMode(RadioMode):
    def process(self, audio: np.ndarray, signal_db: float) -> np.ndarray:
        # 1. Apply EQ
        audio = apply_eq(audio, PRESETS["amhd"], self.sample_rate)
        # 2. Digital noise floor (quantization dither)
        audio += white_noise(len(audio), amplitude=0.0001)
        # 3. Frame drops proportional to weak signal
        if signal_db < -80:
            audio = self._inject_frame_drops(audio, signal_db)
        # 4. Analog fallback blend
        if signal_db < -85:
            audio = self._blend_to_analog(audio, signal_db)
        return audio
```

## Verification

```bash
python -c "
import numpy as np
from src.modes.amhd import AMHDMode
from src.modes.fmhd import FMHDMode
from src.modes.dab import DABMode

tone = np.column_stack([0.5 * np.sin(2 * np.pi * 1000 * np.linspace(0, 2, 88200))] * 2)

for mode in [AMHDMode(), FMHDMode(), DABMode()]:
    out = mode.process(tone, signal_db=-45)
    # Digital modes should not audibly distort a strong signal
    assert out.shape == tone.shape, f'{mode.name}: shape mismatch'
    # Peak should be within reasonable range
    assert abs(out.max()) < 1.5, f'{mode.name}: clipping detected'
    print(f'{mode.name}: OK (shape={out.shape}, peak={out.max():.3f})')
"
```

## Dependencies

- **Step 01–02** — package, engine.
- **Step 03** — `RadioMode` ABC and base patterns from FM/AM.
- **Step 04** — `apply_eq()`, `white_noise()`, noise generators used by digital modes.
