# RadioSim — Radio Stations Simulation Tool

Simulate realistic radio broadcast reception across five modes: FM, AM, AMHD, FMHD, and DAB+. Each mode reproduces authentic audio characteristics — bandwidth limiting, noise profiles, stereo behavior, and signal degradation.

## Features

- **5 Radio Modes**: FM, AM, AM HD Radio, FM HD Radio, DAB+
- **Realistic Signal Simulation**: RSSI, noise, fading, multipath interference per mode
- **Dual Audio Sources**: Local MP3 files (with playlists) or YouTube URLs
- **Rich Terminal UI**: Interactive radio receiver faceplate with live tuning
- **Per-Mode Audio Processing**: Correct bandwidth, EQ curves, stereo encoding

## Quick Start

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m src.main --mode fm --freq 101.1 --source ./music/
```

## Modes

| Mode | Band | Audio BW | Stereo | Characteristics |
|------|------|----------|--------|-----------------|
| FM | 87.5–108 MHz | 50Hz–15kHz | Yes | Hiss, multipath |
| AM | 530–1710 kHz | 50Hz–5kHz | No | Static, fading |
| AMHD | 530–1710 kHz | 50Hz–15kHz | Yes | Digital artifacts |
| FMHD | 87.5–108 MHz | 20Hz–20kHz | Yes | Near-perfect |
| DAB+ | 174–240 MHz | 20Hz–20kHz | Yes | Burst errors |

## Documentation

- [Architecture](docs/architecture.md)
- [Signal Flowcharts](docs/flowcharts.md)
- [Run Guide](docs/run.md)
