# RadioSim — User Guide

## What is RadioSim?

RadioSim simulates listening to radio broadcasts across five different technologies:
FM, AM, AMHD, FMHD, and DAB+. Each mode recreates the authentic sound of that
broadcast type — including its flaws. A strong FM signal sounds clean with slight
hiss; a weak AM signal crackles and fades like a distant station at night.

You feed it audio files (MP3, WAV, FLAC, etc.) or YouTube URLs, and it
broadcasts them through the simulated radio mode of your choice.

---

## Quick Start

```bash
cd radio-sim
source venv/bin/activate

# Play your music folder as an FM station
python -m src.main --mode fm --freq 101.1 --source ~/Music/

# Play a specific file as AM with weak signal
python -m src.main --mode am --freq 880 --source ~/Music/song.mp3 --rssi -80

# Play a YouTube video as DAB+ digital radio
python -m src.main --mode dab --freq 202.0 --source "https://youtube.com/watch?v=..."
```

---

## The Five Radio Modes

### FM — Frequency Modulation (87.5–108.0 MHz)

The classic. Stereo, 50 Hz – 15 kHz bandwidth, 75 µs de-emphasis.

| RSSI | What you hear |
|------|---------------|
| -30 dBm | Pristine stereo, near-perfect |
| -45 dBm | Clean, barely audible hiss |
| -60 dBm | Noticeable hiss, slight multipath echo |
| -75 dBm | Strong hiss, stereo blend → mono, fading starts |
| -90 dBm | Noise dominates, barely intelligible |

**Characteristics:** Hiss, multipath interference (ghost echoes from buildings),
stereo-to-mono fallback at weak signal. RDS metadata displayed in TUI.

```bash
python -m src.main --mode fm --freq 95.5 --source ~/Music/
```

### AM — Amplitude Modulation (530–1710 kHz)

Mono. 50 Hz – 5 kHz bandwidth. The sound of twentieth-century radio.

| RSSI | What you hear |
|------|---------------|
| -40 dBm | Clear mono, slight background static |
| -60 dBm | Noticeable frying static, occasional crackle |
| -75 dBm | Heavy static, deep fades, impulsive pops |
| -90 dBm | Signal barely punching through noise |

**Characteristics:** Pink+white static ("frying" sound), ionospheric fading
(slow volume wobbles), impulsive crackle (lightning/ignition noise). Always mono.

```bash
python -m src.main --mode am --freq 1070 --source ~/Music/ --rssi -70
```

### AMHD — AM HD Radio (530–1710 kHz)

Hybrid digital AM. The same AM dial, but with a digital sidechannel that
carries stereo and extended bandwidth (50 Hz – 15 kHz) when signal is strong.
Falls back to analog AM quality when signal weakens.

```bash
python -m src.main --mode amhd --freq 880 --source ~/Music/
```

### FMHD — FM HD Radio (87.5–108.0 MHz)

Hybrid digital FM. Full CD bandwidth (20 Hz – 20 kHz), discrete stereo.
Supports multicasting: up to 3 subchannels on one frequency, each at different
quality levels (simulated by bitrate reduction on subchannels).

Near-transparent at strong signal. Very rare glitches. Blends to analog FM
below -95 dBm.

```bash
python -m src.main --mode fmhd --freq 101.1 --source ~/Music/
```

### DAB+ — Digital Audio Broadcasting (174–240 MHz)

Fully digital. HE-AAC v2 codec (simulated). The defining characteristic is the
**cliff effect**: perfect audio above threshold, sudden mutes below it. No
gradual degradation — it's either there or it's not.

The `--bitrate` flag controls simulated codec quality (32–256 kbps). Low
bitrates add SBR-like artifacts and HF roll-off.

```bash
python -m src.main --mode dab --freq 202.0 --source ~/Music/
python -m src.main --mode dab --freq 202.0 --source ~/Music/ --rssi -90  # cliff effect demo
```

---

## Audio Sources

### Local Files (MP3, WAV, FLAC, OGG, M4A, AAC, Opus)

Point `--source` at a directory or a single file. Directories are scanned
recursively, files are shuffled by default.

```bash
# Entire folder, shuffled
python -m src.main --mode fm --source ~/Music/

# Single file
python -m src.main --mode fm --source ~/Music/favorite.mp3

# Folder, sequential order
python -m src.main --mode fm --source ~/Music/ --no-shuffle
```

### YouTube URLs

Any YouTube URL works. Audio is streamed in real time via yt-dlp — no full
download needed. Requires ffmpeg on PATH.

```bash
python -m src.main --mode am --freq 880 --source "https://www.youtube.com/watch?v=jfKfPfyJRdk"
```

---

## CLI Reference

```
python -m src.main [OPTIONS]

Options:
  -m, --mode [fm|am|amhd|fmhd|dab]  Radio mode (default: fm)
  -f, --freq FLOAT                   Frequency (auto: center of band)
  -s, --source TEXT                  MP3 directory, file, or YouTube URL
  -r, --rssi FLOAT                   Signal strength in dBm, -120 to 0 (default: -45)
  -v, --volume FLOAT                 Volume 0.0–1.0 (default: 0.8)
  -w, --wav PATH                     Export processed audio to WAV file instead of playing
  -d, --duration FLOAT               Duration in seconds for --wav export (default: 10)
  --tui / --no-tui                   Launch interactive TUI (default: --tui)
  --help                             Show help
```

### WAV Export

To capture processed audio for comparison or sharing:

```bash
# Export 30 seconds of AM radio with heavy static
python -m src.main --mode am --freq 880 --rssi -85 \
    --source ~/Music/song.mp3 \
    --wav /tmp/am_weak.wav --duration 30 --no-tui

# Export all 5 modes for A/B comparison
for mode in fm am amhd fmhd dab; do
    python -m src.main --mode $mode --freq auto \
        --source ~/Music/song.mp3 \
        --wav /tmp/radiosim_${mode}.wav --no-tui
done
```

---

## TUI — Interactive Mode

Launch without `--no-tui` (the default):

```bash
python -m src.main --mode fm --freq 101.1 --source ~/Music/
```

### Layout

```
┌─────────────────────────────────────────────────────────┐
│  RADIOSIM  │  FM  │  101.1 MHz  │  RSSI ████░ -45 dBm  │
├─────────────────────────────────────────────────────────┤
│  ┌─── Tuner ───────────────────────────────────────┐    │
│  │     ╔═══════════════════════════════════╗        │    │
│  │     ║   ─────────────█───────────────── ║        │    │
│  │     ║       TUNED:   101.1 MHz          ║        │    │
│  │     ╚═══════════════════════════════════╝        │    │
│  │     ◄◄  ◄  ►  ►►    step: 0.1 MHz              │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─── Station Info ────────────────────────────────┐    │
│  │  Mode:     FM                                    │    │
│  │  Band:     87.5 – 108.0 MHz                      │    │
│  │  Audio BW: 50 Hz – 15 kHz                        │    │
│  │  Stereo:   ● Yes                                 │    │
│  │  Noise:    Hiss + multipath                      │    │
│  │  RSSI:     -45 dBm  ████░                        │    │
│  │  Now Playing: Por Una Cabeza                     │    │
│  │  Source: 3/17  [tango]                           │    │
│  └──────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────┤
│  FM  AM  AMHD  FMHD  DAB+                               │
│  [Q]uit [M]ode [←→]Tune [↑↓]Vol [N]ext [R]SSI [S]ource │
└─────────────────────────────────────────────────────────┘
```

### Keyboard Controls

| Key | Action |
|-----|--------|
| `Q` / `Esc` | Quit |
| `M` / `Tab` | Cycle mode: FM → AM → AMHD → FMHD → DAB+ |
| `←` `→` | Tune frequency down/up (fine) |
| `↑` `↓` | Volume up/down |
| `+` `-` | Volume up/down (alternate) |
| `[` `]` | Decrease/increase RSSI (weaker/stronger signal) |
| `R` | Randomize RSSI |
| `Space` | Toggle play/pause |
| `N` | Next track |
| `S` | Toggle source type display |

### Signal Strength Meter

```
█████  -30 dBm  Excellent — studio quality
████░  -45 dBm  Very good — clean
███░░  -60 dBm  Fair — noticeable noise
██░░░  -75 dBm  Weak — heavy noise
█░░░░  -90 dBm  Threshold — barely audible
░░░░░  -100 dBm Noise floor — unusable
```

---

## Practical Recipes

### Compare all modes with the same song

```bash
python -m src.main --mode fm   --freq 101.1 --source ~/Music/song.mp3 --wav /tmp/cmp_fm.wav --no-tui
python -m src.main --mode am   --freq 880  --source ~/Music/song.mp3 --wav /tmp/cmp_am.wav --no-tui
python -m src.main --mode amhd --freq 880  --source ~/Music/song.mp3 --wav /tmp/cmp_amhd.wav --no-tui
python -m src.main --mode fmhd --freq 101.1 --source ~/Music/song.mp3 --wav /tmp/cmp_fmhd.wav --no-tui
python -m src.main --mode dab  --freq 202.0 --source ~/Music/song.mp3 --wav /tmp/cmp_dab.wav --no-tui
```

### Simulate driving away from a station

```bash
# Start strong, then manually decrease RSSI with [ key in TUI
python -m src.main --mode fm --freq 101.1 --source ~/Music/ --rssi -30
# Press [ repeatedly to drop signal → hear the degradation
```

### Simulate a distant AM station at night

```bash
python -m src.main --mode am --freq 880 --rssi -85 --source ~/Music/
# Heavy static, deep fades, occasional crackle — the ionosphere at work
```

### YouTube lo-fi radio

```bash
python -m src.main --mode am --freq 1070 --rssi -75 \
    --source "https://www.youtube.com/watch?v=..."
# Any YouTube audio, broadcast through a tinny AM transmitter
```

### Digital radio with DAB+ cliff effect

```bash
python -m src.main --mode dab --freq 202.0 --rssi -85 --source ~/Music/
# Right at the digital cliff — alternates between perfect and muted
```

---

## Troubleshooting

### No sound

RadioSim uses `ffplay` with ALSA for audio output. Verify:

```bash
# Check audio devices
aplay -l

# Test direct playback
aplay /tmp/radiosim_fm.wav

# If no sound, check if muted
alsamixer
```

### "ffmpeg not found"

```bash
sudo apt install ffmpeg   # Debian/Ubuntu
brew install ffmpeg        # macOS
```

### "yt-dlp: command not found"

```bash
pip install --upgrade yt-dlp
```

### Audio stuttering / dropouts

The buffer may be too small. Edit `src/engine/pipeline.py`:
```python
buffer_chunks=64  # increase from 32
```

### Import errors

Run from the `radio-sim/` directory:
```bash
cd radio-sim
python -m src.main ...
```

---

## File Reference

| File | Purpose |
|------|---------|
| `src/main.py` | CLI entry point, wires all components |
| `src/engine/pipeline.py` | Audio processing chain + ring buffer |
| `src/engine/player.py` | ffplay subprocess audio output |
| `src/modes/base.py` | RadioMode ABC |
| `src/modes/fm.py` | FM mode processor |
| `src/modes/am.py` | AM mode processor |
| `src/modes/amhd.py` | AMHD hybrid mode |
| `src/modes/fmhd.py` | FMHD hybrid mode |
| `src/modes/dab.py` | DAB+ digital mode |
| `src/signal/noise.py` | Noise generators |
| `src/signal/filters.py` | EQ presets and filter utilities |
| `src/signal/propagation.py` | Signal simulator + RSSI model |
| `src/sources/mp3.py` | Local file source (ffmpeg) |
| `src/sources/youtube.py` | YouTube source (yt-dlp) |
| `src/ui/tui.py` | Rich interactive terminal UI |
| `docs/architecture.md` | System architecture |
| `docs/flowcharts.md` | Signal flow diagrams |
| `docs/run.md` | Minimal setup & run guide |
