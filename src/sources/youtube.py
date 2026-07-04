"""YouTube audio source — streams audio via yt-dlp + ffmpeg."""

import subprocess
import threading
from pathlib import Path

import numpy as np

from src.sources.base import AudioSource


class YouTubeSource(AudioSource):
    """Streams audio from a YouTube URL in real-time via yt-dlp.

    Pipeline:
        yt-dlp -f bestaudio -o - <url>
            → ffmpeg -i pipe:0 -f s16le -ac 2 -ar 44100 pipe:1
            → read raw PCM from pipe, wrap as numpy arrays

    The audio is streamed (not fully downloaded before playback). Seeking
    is not supported — this is a radio simulation, you tune in and listen.
    """

    def __init__(self, uri: str, cache_dir: str = "/tmp/radiosim_cache"):
        super().__init__(uri)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._process: subprocess.Popen | None = None
        self._metadata: dict = {}
        self._lock = threading.Lock()
        self._bytes_per_frame = 4  # s16le stereo = 2 ch × 2 bytes

    # ---- public API ----

    def open(self) -> None:
        """Extract audio URL and start ffmpeg pipe."""
        self._fetch_metadata()

        # Build pipeline: yt-dlp → ffmpeg → raw PCM on stdout
        ytdlp_cmd = [
            "yt-dlp",
            "-f", "bestaudio",
            "--no-playlist",
            "-o", "-",
            self.uri,
        ]

        ffmpeg_cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-i", "pipe:0",
            "-f", "s16le",
            "-ac", str(self.channels),
            "-ar", str(self.sample_rate),
            "pipe:1",
        ]

        # Launch yt-dlp piping to ffmpeg
        self._process = subprocess.Popen(
            ytdlp_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        self._ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdin=self._process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        # Close yt-dlp's stdout in this process so ffmpeg gets SIGPIPE on exit
        if self._process.stdout:
            self._process.stdout.close()

    def read_chunk(self, n_frames: int) -> np.ndarray | None:
        """Read `n_frames` of raw PCM from the ffmpeg pipe."""
        if self._ffmpeg_process is None or self._ffmpeg_process.stdout is None:
            return None

        n_bytes = n_frames * self.channels * 2  # s16le = 2 bytes per sample

        try:
            raw = self._ffmpeg_process.stdout.read(n_bytes)
        except (BrokenPipeError, OSError):
            return None

        if not raw:
            return None

        # Pad with silence if we got fewer bytes than requested
        if len(raw) < n_bytes:
            padded = bytearray(n_bytes)
            padded[: len(raw)] = raw
            raw = bytes(padded)

        # Convert s16le bytes → float32 numpy array
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        samples = samples.reshape(-1, self.channels)
        return samples / 32768.0

    def close(self) -> None:
        """Terminate subprocesses."""
        for proc in [self._process, getattr(self, "_ffmpeg_process", None)]:
            if proc is not None:
                try:
                    proc.stdout.close() if proc.stdout else None
                    proc.terminate()
                    proc.wait(timeout=3)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    proc.kill()
        self._process = None
        self._ffmpeg_process = None

    def metadata(self) -> dict:
        return self._metadata

    def advance_track(self) -> bool:
        """YouTube source is single-track. Always return True (restart)."""
        return True

    # ---- internal ----

    def _fetch_metadata(self) -> None:
        """Extract video metadata via yt-dlp JSON output."""
        try:
            result = subprocess.run(
                [
                    "yt-dlp",
                    "-j",
                    "--no-playlist",
                    self.uri,
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                import json

                info = json.loads(result.stdout)
                self._metadata = {
                    "title": info.get("title", "Unknown"),
                    "artist": info.get("uploader", info.get("channel", "")),
                    "album": "YouTube",
                    "duration": info.get("duration", 0),
                    "url": self.uri,
                    "track": "1/1",
                }
            else:
                self._metadata = self._fallback_metadata()
        except (subprocess.TimeoutExpired, Exception):
            self._metadata = self._fallback_metadata()

    def _fallback_metadata(self) -> dict:
        return {
            "title": "YouTube Stream",
            "artist": "",
            "album": "YouTube",
            "url": self.uri,
            "track": "1/1",
        }
