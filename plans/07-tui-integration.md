# Step 07 — TUI & Integration

## Goal

Build the Rich-based terminal UI showing a realistic radio receiver faceplate, wire all components together in `main.py`, and write the three documentation files (`architecture.md`, `flowcharts.md`, `run.md`).

## Files Created

```
src/ui/
├── __init__.py
└── tui.py                # Rich TUI — radio receiver faceplate

docs/
├── architecture.md        # System architecture & component map
├── flowcharts.md          # Signal flow, tuning state machine, source lifecycle
└── run.md                 # Minimal setup & run instructions
```

## TUI Design (`tui.py`)

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  RADIOSIM — FM  │  101.1 MHz  │  RSSI ▂▄▆█  -45 dBm       │
│─────────────────────────────────────────────────────────────│
│                                                             │
│         ┌──────────────────────────┐                        │
│         │      ████████████        │   Mode:    FM          │
│         │     █            █       │   Freq:    101.1 MHz   │
│         │    █   TUNED      █      │   Band:    87.5–108.0  │
│         │     █            █       │   Signal:  ▂▄▆█ -45dBm │
│         │      ████████████        │   Stereo:  ● Yes       │
│         └──────────────────────────┘                        │
│                                                             │
│  ◄◄ ◄ ► ►►    freq: 101.100 MHz                            │
│─────────────────────────────────────────────────────────────│
│  Now Playing: Bohemian Rhapsody — Queen       [03:42/05:55] │
│  Source: MP3  │  Track 3/17  │  📁 ~/Music/                 │
│─────────────────────────────────────────────────────────────│
│  [Q]uit  [M]ode  [S]ource  [←→]Tune  [↑↓]Vol  [N]ext      │
└─────────────────────────────────────────────────────────────┘
```

### Components (Rich widgets)

| Widget | Library | Description |
|--------|---------|-------------|
| `Header` | `rich.Panel` | Mode name, frequency, RSSI bar |
| `DialDisplay` | `rich.Panel` | ASCII art tuning dial |
| `InfoPanel` | `rich.Panel` | Mode details, signal meter bars |
| `PlaybackBar` | `rich.Progress` | Track progress bar |
| `NowPlaying` | `rich.Panel` | Current track metadata |
| `HelpBar` | `rich.Text` | Keyboard shortcuts |
| `FrequencyDisplay` | `rich.Text` | Large-format frequency readout |

### Key Bindings

| Key | Action |
|-----|--------|
| `q` / `Ctrl+C` | Quit |
| `m` | Cycle mode: FM → AM → AMHD → FMHD → DAB+ → FM |
| `s` | Toggle source type (MP3 / YouTube) |
| `←` `→` | Tune frequency down/up |
| `Shift+←` `Shift+→` | Seek within track |
| `↑` `↓` | Volume up/down |
| `n` | Next track |
| `r` | Randomize RSSI (simulate signal fluctuation) |
| `[` `]` | RSSI down/up in 5 dB steps |
| `f` | Jump to specific frequency (prompt) |
| `p` | Pause / Resume |

### Update Loop

```python
class RadioTUI:
    def __init__(self, pipeline, player, mode, signal_sim, source):
        self.pipeline = pipeline
        self.player = player
        self.mode = mode
        self.signal_sim = signal_sim
        self.source = source
        self.volume = 0.8
        self.running = True

    def run(self):
        """Main TUI loop."""
        with Live(self._render(), refresh_per_second=10, screen=True) as live:
            while self.running:
                key = self._get_key()  # non-blocking
                if key:
                    self._handle_key(key)
                live.update(self._render())
                time.sleep(0.05)  # ~20 fps

    def _render(self) -> Layout:
        """Build the full Rich layout tree."""
        ...

    def _handle_key(self, key: str) -> None:
        """Dispatch key to action."""
        ...
```

### Frequency Tuning Logic

```
← (fine):  step = 0.1 MHz (FM/FMHD/DAB) or 1 kHz (AM/AMHD)
→ (fine):  step = 0.1 MHz (FM/FMHD/DAB) or 1 kHz (AM/AMHD)
Shift+← (coarse): step * 10
Shift+→ (coarse): step * 10

On mode switch: jump to center of new mode's band
FM  → 98.0 MHz
AM  → 1070 kHz
DAB → 202.0 MHz
```

## Main Integration (`main.py` rewrite)

```python
def main(mode, freq, source, rssi, volume):
    # 1. Select mode
    mode_map = {"fm": FMMode, "am": AMMode, "amhd": AMHDMode,
                "fmhd": FMHDMode, "dab": DABMode}
    radio_mode = mode_map[mode]()

    # 2. Select source
    if source.startswith("http"):
        audio_source = YouTubeSource(source)
    else:
        audio_source = MP3Source(source)

    # 3. Build pipeline
    signal_sim = SignalSimulator(initial_rssi_db=rssi)
    pipeline = AudioPipeline(source=audio_source)
    pipeline.add_processor(lambda chunk: radio_mode.process(chunk, signal_sim.rssi))
    pipeline.add_processor(lambda chunk: signal_sim.apply_degradation(chunk, mode))

    # 4. Start player
    audio_source.open()
    player = Player(pipeline, volume=volume)
    player.start()

    # 5. Launch TUI
    tui = RadioTUI(pipeline, player, radio_mode, signal_sim, audio_source)
    tui.run()
```

## Documentation

### `architecture.md`
- Component diagram (mermaid)
- Module descriptions
- Data flow through the pipeline
- Class hierarchy
- Thread model (main thread + PyAudio callback thread)

### `flowcharts.md`
- Signal flow from source to speakers (mermaid flowchart)
- Mode processing chains per mode
- Tuning state machine
- Source lifecycle (open → stream → advance → close)
- RSSI → noise mapping curve

### `run.md`
- Prerequisites: Python 3.10+, ffmpeg
- Install: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
- Quick start: `python -m src.main --mode fm --freq 101.1 --source ~/Music/`
- Keyboard controls reference
- Troubleshooting: PyAudio device selection, ffmpeg not found, yt-dlp update

## Verification

```bash
# Full integration test
python -m src.main --mode fm --freq 95.5 --source ./test_audio/

# YouTube mode test
python -m src.main --mode am --freq 880 --source "https://www.youtube.com/watch?v=jfKfPfyJRdk"

# All modes smoke test
for mode in fm am amhd fmhd dab; do
    echo "Testing $mode..."
    timeout 3 python -m src.main --mode $mode --freq auto --source ./test_audio/ || true
done
```

## Dependencies

- **All prior steps** — this is the integration step. Every component created in Steps 01–06 is wired together here.
