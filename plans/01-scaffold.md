# Step 01 — Project Scaffold & Dependencies

## Goal

Create the project skeleton: directory tree, dependency manifest, entry-point CLI, and all package init files. Verify that the Python environment can import the package and enumerate audio devices.

## Files Created

```
radio-sim/
├── requirements.txt          # Python dependencies
├── README.md                 # Project overview
├── src/
│   ├── __init__.py            # Package root, __version__
│   ├── main.py                # Click CLI entry point
│   ├── engine/__init__.py
│   ├── modes/__init__.py
│   ├── signal/__init__.py
│   ├── sources/__init__.py
│   └── ui/__init__.py
└── plans/
    └── 01-scaffold.md         # This file
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| numpy   | ≥1.24   | Vectorized DSP operations |
| scipy   | ≥1.10   | Signal processing (filters, FFT) |
| pydub   | ≥0.25   | Audio file decoding (MP3, WAV, etc.) |
| pyaudio | ≥0.2.13 | Real-time audio output via PortAudio |
| yt-dlp  | ≥2024.1 | YouTube audio extraction |
| rich     | ≥13.0   | Terminal UI framework |
| click   | ≥8.1    | CLI argument parsing |

## Verification

```bash
cd radio-sim
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -c "import pyaudio; p = pyaudio.PyAudio(); print(f'Devices: {p.get_device_count()}')"
python -m src.main --help
python -m src.main --mode am --freq 880 --source ~/Music/
```

## Expected Output

The CLI should print the parsed options and a placeholder message. PyAudio should report at least one output device.

## Dependencies on Other Steps

None — this is the foundation.
