# RadioSim — Run Guide

## Prerequisites

- **Python 3.10+**
- **ffmpeg** (audio decode + playback)

That's it. No PortAudio, no pyaudio, no system audio libraries.

### Install system dependencies

```bash
# Debian/Ubuntu
sudo apt install python3 python3-venv ffmpeg

# macOS
brew install python ffmpeg

# Arch
sudo pacman -S python python-pip ffmpeg
```

## Setup

```bash
# Enter the project directory
cd radio-sim

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

On first launch, RadioSim checks that `ffmpeg` and `ffplay` are on PATH.
If missing, it prints a clear error and exits.

## Quick Start

### Local audio files as an FM station

```bash
python -m src.main --mode fm --freq 101.1 --source ~/Music/
```

### YouTube audio as an AM station with weak signal

```bash
python -m src.main --mode am --freq 880 --rssi -80 --source "https://www.youtube.com/watch?v=jfKfPfyJRdk"
```

### DAB+ digital radio

```bash
python -m src.main --mode dab --freq 202.0 --source ~/podcasts/
```

### Headless mode (no TUI, shows now-playing on stderr)

```bash
python -m src.main --mode fm --freq 95.5 --source ~/Music/ --no-tui
```

### Export processed audio to WAV

```bash
python -m src.main --mode am --freq 880 --rssi -85 --source ~/Music/song.mp3 \
    --wav /tmp/am_weak.wav --duration 30 --no-tui
```

## Keyboard Controls (TUI Mode)

| Key | Action |
|-----|--------|
| `Q` / `Esc` | Quit |
| `M` / `Tab` | Cycle mode: FM → AM → AMHD → FMHD → DAB+ |
| `←` `→` | Tune frequency down/up |
| `↑` `↓` | Volume up/down (flash feedback on change) |
| `+` `-` | Volume up/down (alternate) |
| `[` `]` | RSSI down/up — weaker/stronger signal (flash feedback on change) |
| `R` | Randomize RSSI |
| `N` | Next track (MP3 source) |

Frequency auto-clamps to the center of the new band when switching modes.

## CLI Options

```
Usage: python -m src.main [OPTIONS]

Options:
  -m, --mode [fm|am|amhd|fmhd|dab]  Radio mode (default: fm)
  -f, --freq FLOAT                   Frequency (auto-selects center if omitted)
  -s, --source TEXT                  MP3 directory/file or YouTube URL
  -r, --rssi FLOAT                   Initial RSSI in dBm, -120 to -10 (default: -45)
  -v, --volume FLOAT                 Volume 0.0–1.0 (default: 0.8)
  -w, --wav PATH                     Export processed audio to WAV file instead of playing
  -d, --duration FLOAT               Duration in seconds for --wav export (default: 10)
  --tui / --no-tui                   Launch interactive TUI (default: --tui)
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

### No sound

RadioSim uses `ffplay` with ALSA for audio output:

```bash
# Check audio devices
aplay -l

# Test direct playback
aplay /tmp/radiosim_fm.wav

# Check if muted
alsamixer
```

### "Error: ffmpeg not found on PATH"

```bash
# Debian/Ubuntu
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

### "yt-dlp: command not found" (YouTube sources)

```bash
pip install --upgrade yt-dlp
```

### "No supported audio files found"

Ensure the source directory contains files with supported extensions:
`.mp3`, `.wav`, `.flac`, `.ogg`, `.m4a`, `.aac`, `.opus`

### Audio stuttering / dropouts

- Reduce system load (close other CPU-intensive apps)
- The refill thread loops as fast as possible; stutters indicate CPU-bound DSP
- Try a simpler mode (FM is lighter than AMHD/FMHD)

### Import errors about `src.*`

Run from the `radio-sim/` directory (the parent of `src/`):
```bash
cd radio-sim
source venv/bin/activate
python -m src.main ...
```
