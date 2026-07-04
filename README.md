# RadioSim — Radio Stations Simulation Tool

Simulate realistic radio broadcast reception across five modes: FM, AM, AMHD, FMHD, and DAB+. Each mode reproduces authentic audio characteristics — bandwidth limiting, noise profiles, stereo behavior, and signal degradation.

## Features

- **5 Radio Modes**: FM, AM, AM HD Radio, FM HD Radio, DAB+
- **Realistic Signal Simulation**: RSSI-driven noise, fading, multipath — stronger signal = cleaner audio
- **Dual Audio Sources**: Local files (MP3/FLAC/WAV/OGG) with playlists, or YouTube URLs
- **Rich Terminal UI**: Interactive radio receiver faceplate with live tuning and visual feedback
- **Per-Mode Audio Processing**: Correct bandwidth, EQ curves, stereo/mono behavior per mode
- **WAV Export**: Capture processed audio for A/B comparison across modes
- **Zero native dependencies**: Only needs Python + ffmpeg on PATH

## Quick Start

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m src.main --mode fm --freq 101.1 --source ./music/
```

## Modes

| Mode | Band | Audio BW | Stereo | Noise Character |
|------|------|----------|--------|-----------------|
| FM | 87.5–108 MHz | 50Hz–15kHz | Yes | Hiss, multipath |
| AM | 530–1710 kHz | 50Hz–5kHz | No | Static, crackle, fading |
| AMHD | 530–1710 kHz | 50Hz–15kHz | Yes (digital) | Light artifacts, frame drops |
| FMHD | 87.5–108 MHz | 20Hz–20kHz | Yes | Near-none, rare glitches |
| DAB+ | 174–240 MHz | 20Hz–20kHz | Yes | Burst errors, cliff effect |

## Keyboard Controls (TUI)

| Key | Action |
|-----|--------|
| `Q` / `Esc` | Quit |
| `M` / `Tab` | Cycle mode: FM → AM → AMHD → FMHD → DAB+ |
| `←` `→` | Tune frequency |
| `↑` `↓` | Volume up/down |
| `[` `]` | RSSI weaker/stronger (affects noise level) |
| `R` | Randomize RSSI |
| `N` | Next track |

## Documentation

- [User Guide](docs/user-guide.md) — full manual with recipes
- [Run Guide](docs/run.md) — minimal setup & troubleshooting
- [Architecture](docs/architecture.md) — system design & component map
- [Signal Flowcharts](docs/flowcharts.md) — per-mode processing chains
- [Improvement Plan](improvements/README.md) — audit results & fix log (v0.2)

## Requirements

- Python 3.10+
- ffmpeg (for audio decode & playback)
- yt-dlp (optional, for YouTube sources)

No PortAudio, no pyaudio, no system audio libraries needed — just ffmpeg.
