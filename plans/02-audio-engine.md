# Step 02 — Audio Engine Core

## Goal

Build the real-time audio pipeline: read decoded audio from a source, push it through a processing chain, and output via PyAudio's callback-based stream. At this stage the pipeline is a **passthrough** — no mode processing yet, just proving the playback loop works.

## Files Created

```
src/engine/
├── __init__.py
├── pipeline.py    # AudioPipeline — source → processors → output buffer
└── player.py      # Player — PyAudio stream manager, callback dispatcher
```

## Design

### `AudioPipeline` (`pipeline.py`)

```
AudioPipeline
├── source: AudioSource          # Reads raw PCM chunks
├── processors: list[callable]   # Each takes (numpy array, sample_rate) → numpy array
├── buffer: collections.deque    # Thread-safe output ring buffer
├── push_chunk(n_samples)        # Pull from source, run processor chain, push to buffer
└── pop_chunk(n_samples)         # Called by PyAudio callback to fetch output
```

At this step, `processors` is an empty list — audio passes through unchanged.

### `Player` (`player.py`)

```
Player
├── pyaudio_instance: PyAudio
├── stream: PyAudio.Stream       # Non-blocking callback mode
├── pipeline: AudioPipeline
├── start()                      # Open stream, begin playback
├── stop()                       # Close stream, terminate PyAudio
└── _callback(in_data, n_frames) # PyAudio callback → pipeline.pop_chunk()
```

**Callback model** — PyAudio calls `_callback` on its own thread when the output buffer needs more data. This avoids blocking the main thread.

### Audio Format

- Sample rate: **44100 Hz**
- Bit depth: **16-bit signed integer** (pyaudio `paInt16`)
- Channels: **2** (stereo)
- Chunk size: **1024 frames** (~23 ms at 44.1 kHz)

## Key Decisions

- **pyaudio callback (non-blocking)** over blocking `write()` — leaves the main thread free for the TUI.
- **numpy float32 [-1.0, +1.0]** internal representation — convert to int16 only at the PyAudio boundary.
- **deque ring buffer** between pipeline and player — decouples processing from consumption, absorbs jitter.

## Verification

```python
# test_engine.py — temporary, deleted after verification
from src.engine.player import Player
from src.engine.pipeline import AudioPipeline

# Will fail gracefully until Step 06 (no real source yet)
# For now, verify imports and class instantiation
pipeline = AudioPipeline(source=None)  # None until Step 06
player = Player(pipeline)
print("Engine classes instantiated OK")
```

```bash
python -c "from src.engine.pipeline import AudioPipeline; from src.engine.player import Player; print('Engine OK')"
```

## Dependencies

- **Step 01** — package structure and dependencies must exist.
- **Step 06** — needs `AudioSource` implementations to play real audio; until then, pipeline is testable with a mock source.
