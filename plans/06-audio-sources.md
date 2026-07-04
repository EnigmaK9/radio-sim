# Step 06 — Audio Sources

## Goal

Implement the `AudioSource` abstraction and two concrete sources: local MP3 filesystem playback (with playlist management) and YouTube URL streaming via yt-dlp. Sources must provide a uniform interface so the audio pipeline doesn't care where audio comes from.

## Files Created

```
src/sources/
├── __init__.py
├── base.py      # AudioSource ABC
├── mp3.py       # MP3Source — local file playback
└── youtube.py   # YouTubeSource — yt-dlp streaming
```

## Design

### `AudioSource` ABC (`base.py`)

```python
class AudioSource(ABC):
    """Abstract audio source. Produces raw PCM chunks on demand."""

    def __init__(self, uri: str):
        self.uri = uri                       # Path or URL
        self.sample_rate: int = 44100
        self.channels: int = 2
        self._current_track_meta: dict = {}  # Now-playing metadata

    @abstractmethod
    def open(self) -> None:
        """Initialize the source. Called once before reading."""
        ...

    @abstractmethod
    def read_chunk(self, n_frames: int) -> np.ndarray | None:
        """Return (n_frames, n_channels) float32 array, or None if EOF/error."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release resources."""
        ...

    @abstractmethod
    def metadata(self) -> dict:
        """Return {"title": ..., "artist": ..., "album": ...} for current track."""
        ...

    def advance_track(self) -> bool:
        """Move to next track in playlist. Return False if no more tracks."""
        ...
```

### `MP3Source` (`mp3.py`)

```python
class MP3Source(AudioSource):
    """Plays MP3 files from a directory, with playlist support."""

    def __init__(self, uri: str, shuffle: bool = True, recursive: bool = True):
        super().__init__(uri)
        self.shuffle = shuffle
        self.recursive = recursive
        self.playlist: list[Path] = []
        self._current_idx: int = -1
        self._current_segment: pydub.AudioSegment | None = None
        self._position: int = 0  # sample offset in current segment

    def open(self) -> None:
        """Scan directory for .mp3 files, build playlist."""
        ...

    def read_chunk(self, n_frames: int) -> np.ndarray | None:
        """Read next chunk from current pydub segment.
        Auto-advances to next track on EOF."""
        ...

    def metadata(self) -> dict:
        """Read ID3 tags from current file via pydub or mutagen."""
        ...
```

**Playlist behavior:**
- Scans `uri` recursively for `*.mp3` files
- Sorts alphabetically, optionally shuffles
- Loops infinitely (wraps around when playlist exhausted)
- `advance_track()` skips to next file

**Audio decoding:**
- `pydub.AudioSegment.from_mp3()` decodes the file
- Convert to numpy: `np.array(segment.get_array_of_samples()).reshape(-1, segment.channels) / 32768.0`
- Resample to 44100 Hz if needed via `segment.set_frame_rate(44100)`
- Mono sources are duplicated to stereo

### `YouTubeSource` (`youtube.py`)

```python
class YouTubeSource(AudioSource):
    """Streams audio from a YouTube URL via yt-dlp."""

    def __init__(self, uri: str, cache_dir: str = "/tmp/radiosim_cache"):
        super().__init__(uri)
        self.cache_dir = Path(cache_dir)
        self._process: subprocess.Popen | None = None
        self._pipe: io.BufferedReader | None = None

    def open(self) -> None:
        """Extract direct audio URL with yt-dlp, then open ffmpeg pipe.
        yt-dlp --extract-audio --audio-format mp3 --output - <url>
        piped to ffmpeg decoding to raw PCM on stdout."""
        ...

    def read_chunk(self, n_frames: int) -> np.ndarray | None:
        """Read bytes from ffmpeg stdout pipe, convert to numpy array."""
        ...

    def metadata(self) -> dict:
        """yt-dlp JSON metadata: title, uploader, duration."""
        ...
```

**YouTube flow:**
1. `yt-dlp -j <url>` → extract JSON metadata (title, duration, formats)
2. `yt-dlp -f bestaudio -o - <url>` → pipe best audio stream to stdout
3. `ffmpeg -i pipe:0 -f s16le -ac 2 -ar 44100 pipe:1` → decode to raw PCM
4. Read PCM chunks from pipe, wrap as numpy arrays

**Streaming vs. downloading:** The source streams in real-time; no full download before playback starts. Optional cache to `/tmp` for repeated plays.

## Integration with Pipeline

```python
# In main.py (Step 07), the source is wired to the pipeline:
source = MP3Source(uri="./music/")  # or YouTubeSource(uri="https://...")
source.open()
pipeline = AudioPipeline(source=source)
pipeline.add_processor(fm_mode.process)
pipeline.add_processor(signal_sim.apply_degradation)
player = Player(pipeline)
player.start()
```

## Verification

```bash
# Test MP3 source with a folder
python -c "
from src.sources.mp3 import MP3Source
src = MP3Source('./test_audio/')
src.open()
chunk = src.read_chunk(1024)
print(f'Chunk shape: {chunk.shape}, meta: {src.metadata()}')
"

# Test YouTube source (requires network)
python -c "
from src.sources.youtube import YouTubeSource
src = YouTubeSource('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
src.open()
print(f'Metadata: {src.metadata()}')
chunk = src.read_chunk(1024)
print(f'Chunk shape: {chunk.shape}')
"
```

## Dependencies

- **Step 01–02** — package, engine. `AudioPipeline` holds an `AudioSource`.
- **Step 03–05** — modes consume source output as input to `process()`.
- External: `ffmpeg` must be on `$PATH` for YouTube source (yt-dlp uses it internally).
