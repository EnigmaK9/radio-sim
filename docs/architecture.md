# RadioSim — System Architecture

## Overview

RadioSim simulates radio broadcast reception across five modes (FM, AM, AMHD, FMHD, DAB+).
Audio sources (local files or YouTube URLs) are processed through mode-specific DSP chains
and output via ffplay subprocess in real time. A Rich-based TUI provides an interactive
radio receiver faceplate. Zero native audio libraries required — just Python + ffmpeg.

## Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                     Main Thread (TUI)                        │
│                                                              │
│  ┌──────────┐   ┌────────────┐   ┌──────────────────────┐   │
│  │ Rich TUI │   │  Keyboard  │   │ Shared State         │   │
│  │ Live UI  │◄──│  Handler   │──►│ freq, rssi, mode, vol│   │
│  └────┬─────┘   └────────────┘   └──────────┬───────────┘   │
│       │                                     │                │
│       │ renders                             │ reads state    │
└───────┼─────────────────────────────────────┼────────────────┘
        │                                     │
        │                                     ▼
        │                        ┌────────────────────────┐
        │                        │    Refill Thread       │
        │                        │                        │
        │                        │  loop:                 │
        │                        │    raw = source        │
        │                        │      .read_chunk(N)    │
        │                        │    out = mode          │
        │                        │      .process(raw,     │
        │                        │       signal_db)       │
        │                        │    int16 = out * vol   │
        │                        │    ffplay.stdin        │
        │                        │      .write(int16)     │
        │                        └───────────┬────────────┘
        │                                    │
        │                                    ▼
        │                        ┌────────────────────────┐
        │                        │  ffplay subprocess     │
        │                        │  (ALSA backend)        │
        │                        │  pipe:0 → speakers     │
        │                        └────────────────────────┘
```

## Threading Model

| Thread | Role | Blocking Ops | Critical Path |
|--------|------|-------------|---------------|
| **Main** | TUI render + keyboard input | `rich.Live` refresh, stdin poll | Must keep UI responsive |
| **Refill** | Audio decode + DSP + ffplay write | File I/O, yt-dlp subprocess, scipy filters, pipe write | Must not stutter |
| **Metadata** | Poll source.metadata() → TUI state | None (dict reads, lock-guarded) | Background, non-critical |

## Data Flow

```
[MP3 File / YT URL]
       │
       ▼
┌──────────────┐
│ AudioSource  │  .read_chunk(n_frames) → float32[n_frames, 2]
│ (mp3/yt)     │  ffmpeg subprocess decode
└──────┬───────┘
       │ raw audio [-1.0, 1.0]
       ▼
┌──────────────┐
│ RadioMode    │  .process(audio, signal_db)
│ (fm/am/...)  │  Applies in one pass: EQ, bandwidth limit,
│              │  stereo blend, noise, fading, errors.
│              │  RSSI drives degradation intensity — stronger
│              │  signal = cleaner output.
└──────┬───────┘
       │ float32 [-1.0, 1.0]
       ▼
┌──────────────┐
│ Volume +     │  chunk * volume → clip → int16
│ int16 cast   │
└──────┬───────┘
       │ raw s16le bytes
       ▼
┌──────────────┐
│ ffplay       │  pipe:0 → ALSA → speakers
│ subprocess   │  SDL_AUDIODRIVER=alsa
└──────────────┘
```

**v0.2 note:** The `SignalSimulator` was previously a separate pipeline stage adding
a second layer of noise on top of the mode's own noise. This double-degradation
has been removed. Each `RadioMode.process()` now handles all degradation internally,
with RSSI read from the shared `SignalSimulator` state. The `SignalSimulator` remains
as the RSSI state holder and provides `apply_degradation()` for WAV export.

## Module Map

```
src/
├── main.py                  CLI entry, wires components, launches TUI
├── engine/
│   ├── pipeline.py          AudioPipeline — processor chain + ring buffer
│   └── player.py            Player — ffplay subprocess manager
├── modes/
│   ├── base.py              RadioMode ABC + ModeParameters + display_info()
│   ├── fm.py                FMMode (87.5–108 MHz, stereo, 50–15kHz)
│   ├── am.py                AMMode (530–1710 kHz, mono, 50–5kHz)
│   ├── amhd.py              AMHDMode (hybrid digital AM)
│   ├── fmhd.py              FMHDMode (hybrid digital FM, multicasting)
│   └── dab.py               DABMode (174–240 MHz, digital, burst errors)
├── signal/
│   ├── noise.py             Noise generators: PinkNoiseGenerator, white, impulsive, fading
│   ├── filters.py           EQ presets, bandpass, de-emphasis, stereo blend
│   └── propagation.py       SignalSimulator, PropagationModel, RSSI→noise mapping
├── sources/
│   ├── base.py              AudioSource ABC
│   ├── mp3.py               MP3Source — local files via ffmpeg, thread-safe metadata
│   └── youtube.py           YouTubeSource — yt-dlp + ffmpeg pipe
└── ui/
    └── tui.py               Rich-based radio receiver faceplate, flash feedback
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
├── MP3Source     local filesystem: recursive scan, playlist, ffmpeg decode
└── YouTubeSource remote: yt-dlp + ffmpeg pipe

PinkNoiseGenerator  Persistent pink noise — no chunk-boundary artifacts
SignalSimulator     RSSI state holder + per-mode degradation for WAV export
AudioPipeline       source → processors[] → ring buffer
Player              ffplay subprocess lifecycle + refill thread
RadioTUI            Rich Live layout, keyboard handler, flash feedback
```

## Key Design Decisions

1. **Single processor stage** — Each mode's `process()` handles all DSP (EQ + noise +
   fading + errors) in one pass. No separate degradation stage. Simplifies the pipeline
   and fixes double-noise bug from v0.1.

2. **Two-thread model** — Main (TUI), Refill (decode + DSP + ffplay write). Metadata
   on a third background thread. Single lock on source metadata; lock hold time < 1 µs.

3. **ffplay subprocess via ALSA** — `SDL_AUDIODRIVER=alsa` bypasses PulseAudio.
   No PortAudio/pyaudio/sounddevice needed. Raw PCM piped to stdin.

4. **numpy float32 internal format** — All processing in [-1, 1] float32.
   Convert to int16 only at the ffplay boundary.

5. **yt-dlp as subprocess** — More reliable than the Python API for URL extraction.
   ffmpeg handles format conversion. Trade-off: 2-5 second startup for YouTube sources.

6. **PinkNoiseGenerator with persistent state** — Replaced the stateless
   `pink_noise()` function which caused audible clicks at every 1024-sample chunk
   boundary due to Voss-McCartney state reset.

7. **Pre-flight dependency check** — On startup, verifies ffmpeg and ffplay are
   on PATH. Fails with a clear install message instead of silent audio failure.

8. **No Web UI in v1** — Rich TUI is the MVP. Web faceplate is a future addition.
