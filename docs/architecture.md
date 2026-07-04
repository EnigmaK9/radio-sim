# RadioSim — System Architecture

## Overview

RadioSim simulates radio broadcast reception across five modes (FM, AM, AMHD, FMHD, DAB+). Audio sources (local MP3 files or YouTube URLs) are processed through mode-specific DSP chains and output via PyAudio in real time. A Rich-based TUI provides an interactive radio receiver faceplate.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      Main Thread (TUI)                          │
│                                                                 │
│  ┌──────────┐   ┌────────────┐   ┌──────────────────────────┐  │
│  │ Rich TUI │   │  Keyboard  │   │  Shared State (TUIState) │  │
│  │ Live UI  │◄──│  Handler   │──►│  freq, rssi, mode, vol   │  │
│  └────┬─────┘   └────────────┘   └───────────┬──────────────┘  │
│       │                                      │                  │
│       │ renders                              │ reads state      │
└───────┼──────────────────────────────────────┼──────────────────┘
        │                                      │
        │                                      ▼
        │                         ┌────────────────────────┐
        │                         │    Refill Thread       │
        │                         │                        │
        │                         │  loop:                 │
        │                         │    chunk = source      │
        │                         │      .read_chunk(N)    │
        │                         │    chunk = mode        │
        │                         │      .process(chunk)   │
        │                         │    chunk = signal_sim  │
        │                         │      .apply_degrad...  │
        │                         │    buffer.write(chunk) │
        │                         └───────────┬────────────┘
        │                                     │
        │                                     ▼
        │                         ┌────────────────────────┐
        │                         │    Ring Buffer         │
        │                         │    deque(maxlen=32)    │
        │                         └───────────┬────────────┘
        │                                     │
        │                                     ▼
        │                         ┌────────────────────────┐
        │                         │  Audio Callback Thread │
        │                         │  (PyAudio)             │
        │                         │                        │
        │                         │  on_request(frames):   │
        │                         │    return buffer       │
        │                         │      .pop_chunk()      │
        │                         │      → speakers        │
        │                         └────────────────────────┘
```

## Threading Model

| Thread | Role | Blocking Ops | Critical Path |
|--------|------|-------------|---------------|
| **Main** | TUI render + keyboard input | `rich.Live` refresh, stdin poll | Must keep UI responsive |
| **Refill** | Audio decode + DSP + buffer fill | File I/O, yt-dlp subprocess, scipy filters | Must not underrun |
| **Audio** | PyAudio callback → speakers | None (pre-allocated buffer reads) | Must never block |

## Data Flow

```
[MP3 File / YT URL]
       │
       ▼
┌──────────────┐
│ AudioSource  │  .read_chunk(n_frames) → float32[n_frames, 2]
│ (mp3/yt)     │
└──────┬───────┘
       │ raw audio [-1.0, 1.0]
       ▼
┌──────────────┐
│ RadioMode    │  .process(audio, signal_db)
│ (fm/am/...)  │  Applies: EQ, bandwidth limit, stereo blend, noise
└──────┬───────┘
       │ mode-processed audio
       ▼
┌──────────────┐
│ SignalSim    │  .apply_degradation(audio, mode)
│              │  Applies: noise floor, fading, multipath, burst errors
└──────┬───────┘
       │ degraded audio
       ▼
┌──────────────┐
│ Ring Buffer  │  deque[ndarray], maxlen=32
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ PyAudio      │  Callback reads from buffer → int16 → speakers
└──────────────┘
```

## Module Map

```
src/
├── main.py                  CLI entry, wires components, launches TUI
├── engine/
│   ├── pipeline.py          AudioPipeline — processor chain + ring buffer
│   └── player.py            Player — PyAudio stream manager
├── modes/
│   ├── base.py              RadioMode ABC + ModeParameters
│   ├── fm.py                FMMode (87.5–108 MHz, stereo, 50–15kHz)
│   ├── am.py                AMMode (530–1710 kHz, mono, 50–5kHz)
│   ├── amhd.py              AMHDMode (hybrid digital AM)
│   ├── fmhd.py              FMHDMode (hybrid digital FM, multicasting)
│   └── dab.py               DABMode (174–240 MHz, digital, burst errors)
├── signal/
│   ├── noise.py             Noise generators (white, pink, impulsive, fading)
│   ├── filters.py           EQ presets, bandpass, de-emphasis, stereo blend
│   └── propagation.py       SignalSimulator, PropagationModel, RSSI→noise mapping
├── sources/
│   ├── base.py              AudioSource ABC
│   ├── mp3.py               MP3Source — local file playlist
│   └── youtube.py           YouTubeSource — yt-dlp + ffmpeg pipe
└── ui/
    └── tui.py               Rich-based radio receiver faceplate
```

## Class Hierarchy

```
RadioMode (ABC)
├── FMMode        analog FM broadcast
├── AMMode        analog AM broadcast
├── AMHDMode      hybrid digital AM (analog + digital paths)
├── FMHDMode      hybrid digital FM (analog + digital paths, subchannels)
└── DABMode       fully digital DAB+ (cliff effect, burst errors)

AudioSource (ABC)
├── MP3Source     local filesystem: recursive scan, playlist, pydub decode
└── YouTubeSource remote: yt-dlp + ffmpeg pipe

SignalSimulator  RSSI tracking → noise, fading, errors
AudioPipeline    source → processors[] → ring buffer → consumer
Player           PyAudio lifecycle, callback, refill thread
RadioTUI         Rich Live layout, keyboard handler, state display
```

## Key Design Decisions

1. **Linear processor chain, not a graph** — Each mode's `process()` is a sequence of stages. No DAG/plugin system needed for a simulation tool.

2. **Three-thread model** — Main (TUI), Refill (DSP + buffer fill), Audio (PyAudio callback). Single lock on shared state; lock hold time is ~1 µs (setting an int).

3. **PyAudio callback (non-blocking)** — Leaves main thread free for TUI. Ring buffer decouples production from consumption.

4. **numpy float32 internal format** — All processing in [-1, 1] float32. Convert to int16 only at the PyAudio boundary.

5. **yt-dlp as subprocess** — More reliable than the Python API for URL extraction. ffmpeg handles format conversion. Trade-off: 2-5 second startup for YouTube sources.

6. **No Web UI in v1** — Rich TUI is the MVP. Web faceplate is a future addition.
