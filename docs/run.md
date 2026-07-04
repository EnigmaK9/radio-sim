# RadioSim — Run Guide

## Prerequisites

- **Python 3.10+**
- **ffmpeg** (required for YouTube sources and some audio formats)
- **PortAudio** library (required by PyAudio)

### Install system dependencies

```bash
# Debian/Ubuntu
sudo apt install python3 python3-venv python3-dev portaudio19-dev ffmpeg

# macOS
brew install python portaudio ffmpeg

# Arch
sudo pacman -S python python-pip portaudio ffmpeg
```

## Setup

```bash
# Clone or enter the project directory
cd radio-sim

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

## Quick Start

### Local MP3 files as an FM station

```bash
python -m src.main --mode fm --freq 101.1 --source ~/Music/
```

### YouTube audio as an AM station

```bash
python -m src.main --mode am --freq 880 --source "https://www.youtube.com/watch?v=jfKfPfyJRdk"
```

### DAB+ digital radio

```bash
python -m src.main --mode dab --freq 202.0 --source ~/podcasts/
```

### Headless mode (no TUI)

```bash
python -m src.main --mode fm --freq 95.5 --source ~/Music/ --no-tui
```

## Keyboard Controls (TUI Mode)

| Key | Action |
|-----|--------|
| `Q` / `Esc` | Quit |
| `M` / `Tab` | Cycle mode: FM → AM → AMHD → FMHD → DAB+ |
| `←` `→` | Tune frequency down/up |
| `↑` `↓` | Volume up/down |
| `+` `-` | Volume up/down (alternate) |
| `[` `]` | RSSI down/up (weaker/stronger signal) |
| `R` | Randomize RSSI |
| `N` | Next track (MP3 source) |
| `Space` | Toggle play/pause |
| `S` | Toggle source type display |

## CLI Options

```
Usage: python -m src.main [OPTIONS]

Options:
  -m, --mode [fm|am|amhd|fmhd|dab]  Radio mode (default: fm)
  -f, --freq FLOAT                   Frequency (auto-selects center if omitted)
  -s, --source TEXT                  MP3 directory path or YouTube URL
  -r, --rssi FLOAT                   Initial RSSI in dBm (default: -45)
  -v, --volume FLOAT                 Volume 0.0–1.0 (default: 0.8)
  --tui / --no-tui                   Launch interactive TUI (default: yes)
  --help                             Show help
  --version                          Show version
```

## Mode Reference

| Mode | Frequency Band | Tuning Step | Stereo | Audio Quality |
|------|---------------|-------------|--------|---------------|
| FM | 87.5–108.0 MHz | 0.1 MHz | Yes | Good (50Hz–15kHz) |
| AM | 530–1710 kHz | 1 kHz | No | Limited (50Hz–5kHz) |
| AMHD | 530–1710 kHz | 1 kHz | Yes (digital) | Good (50Hz–15kHz) |
| FMHD | 87.5–108.0 MHz | 0.1 MHz | Yes | Excellent (20Hz–20kHz) |
| DAB+ | 174–240 MHz | 0.1 MHz | Yes | Excellent (20Hz–20kHz) |

## Troubleshooting

### "No audio devices found" / PyAudio errors

```bash
# Check available devices
python -c "import pyaudio; p = pyaudio.PyAudio(); print(p.get_device_count())"

# On Linux, ensure user is in the audio group
sudo usermod -a -G audio $USER
# Log out and back in
```

### "ffmpeg not found" (YouTube sources)

```bash
which ffmpeg  # should return a path
# If not: sudo apt install ffmpeg (or equivalent)
```

### "yt-dlp: command not found"

```bash
pip install --upgrade yt-dlp
```

### "No supported audio files found"

Ensure the source directory contains files with supported extensions:
`.mp3`, `.wav`, `.flac`, `.ogg`, `.m4a`, `.aac`

### Audio stuttering / underruns

- Reduce system load (close other CPU-intensive apps)
- Increase buffer size: edit `src/engine/pipeline.py` → `buffer_chunks=64`
- Reduce chunk_size: 512 instead of 1024

### Import errors about `src.*`

Run from the `radio-sim/` directory (the parent of `src/`):
```bash
cd radio-sim
python -m src.main ...
```
