"""MP3 file source — plays local audio files via ffmpeg subprocess."""

import random
import subprocess
import threading
from pathlib import Path

import numpy as np

from src.sources.base import AudioSource


class MP3Source(AudioSource):
    """Plays audio files from a directory, with playlist management.

    Decodes audio via ffmpeg subprocess (no pydub needed — just ffmpeg on PATH).
    Scans `uri` recursively for supported files, builds a playlist, and
    streams decoded PCM chunks on demand.

    Attributes:
        shuffle: randomize playlist order.
        recursive: scan subdirectories.
        loop: restart playlist when exhausted.
    """

    SUPPORTED_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus"}

    def __init__(
        self,
        uri: str,
        shuffle: bool = True,
        recursive: bool = True,
        loop: bool = True,
    ):
        super().__init__(uri)
        self.shuffle = shuffle
        self.recursive = recursive
        self.loop = loop

        self.playlist: list[Path] = []
        self._current_idx: int = -1
        self._process: subprocess.Popen | None = None
        self._track_duration: float = 0.0
        self._bytes_per_frame = self.channels * 2  # s16le
        self._lock = threading.Lock()

    # ---- public API ----

    def open(self) -> None:
        """Scan directory and build playlist."""
        root = Path(self.uri)
        if not root.exists():
            raise FileNotFoundError(f"Source path not found: {self.uri}")

        if root.is_file():
            self.playlist = [root]
        else:
            pattern = "**/*" if self.recursive else "*"
            files: list[Path] = []
            for ext in self.SUPPORTED_EXTENSIONS:
                files.extend(root.glob(f"{pattern}{ext}"))
                files.extend(root.glob(f"{pattern}{ext.upper()}"))
            self.playlist = sorted(set(files))

        if not self.playlist:
            raise FileNotFoundError(f"No supported audio files found in: {self.uri}")

        if self.shuffle:
            random.shuffle(self.playlist)

        self._current_idx = -1
        self._launch_current()

    def read_chunk(self, n_frames: int) -> np.ndarray | None:
        """Read next chunk from ffmpeg stdout. Auto-advances on EOF."""
        n_bytes = n_frames * self._bytes_per_frame
        raw = bytearray()
        skips = 0
        max_skips = len(self.playlist) + 1  # prevent infinite loop if all files corrupt

        # Read in a loop — pipes may return partial data
        while len(raw) < n_bytes and skips < max_skips:
            if self._process is None or self._process.stdout is None:
                if not self._launch_current():
                    break
                continue

            try:
                data = self._process.stdout.read(n_bytes - len(raw))
            except (BrokenPipeError, OSError, ValueError):
                data = b""

            if not data:
                # EOF on this track — advance to next
                skips += 1
                if not self._launch_current():
                    break
                continue

            raw.extend(data)

        if len(raw) == 0:
            return None

        # s16le bytes → float32 [-1, 1]
        samples = np.frombuffer(bytes(raw), dtype=np.int16).astype(np.float32) / 32768.0
        n_sample_frames = len(samples) // self.channels
        samples = samples[: n_sample_frames * self.channels].reshape(-1, self.channels)

        # Pad to requested size with silence if short
        if samples.shape[0] < n_frames:
            padded = np.zeros((n_frames, self.channels), dtype=np.float32)
            padded[: samples.shape[0]] = samples
            return padded

        return samples[:n_frames]

    def close(self) -> None:
        if self._process:
            try:
                self._process.stdout.close()
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                self._process.kill()
            self._process = None
        self.playlist.clear()

    def metadata(self) -> dict:
        with self._lock:
            if self._current_idx >= 0 and self._current_idx < len(self.playlist):
                path = self.playlist[self._current_idx]
                return {
                    "title": path.stem,
                    "artist": "",
                    "album": path.parent.name,
                    "file": str(path),
                    "track": f"{self._current_idx + 1}/{len(self.playlist)}",
                }
            return {"title": "No track", "artist": "", "album": "", "file": "", "track": "0/0"}

    def advance_track(self) -> bool:
        """Skip to next track."""
        return self._launch_current()

    @property
    def current_track_index(self) -> int:
        return self._current_idx

    @property
    def track_count(self) -> int:
        return len(self.playlist)

    # ---- internal ----

    def _launch_current(self) -> bool:
        """Start ffmpeg decoding the next file in the playlist."""
        if self._process:
            try:
                self._process.stdout.close()
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                self._process.kill()
            self._process = None

        with self._lock:
            self._current_idx += 1
            if self._current_idx >= len(self.playlist):
                if self.loop:
                    self._current_idx = 0
                    if self.shuffle:
                        random.shuffle(self.playlist)
                else:
                    return False

            path = self.playlist[self._current_idx]

        cmd = [
            "ffmpeg",
            "-loglevel", "error",
            "-i", str(path),
            "-f", "s16le",
            "-acodec", "pcm_s16le",
            "-ac", str(self.channels),
            "-ar", str(self.sample_rate),
            "pipe:1",
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            raise RuntimeError("ffmpeg not found. Install ffmpeg to play audio files.")
        except Exception:
            import sys

            print(f"Warning: skipping unplayable file: {path.name}", file=sys.stderr)
            return self._launch_current()

        # ponytail: metadata() reads _current_idx/playlist directly, no cached field needed
        return True

    def _silence_chunk(self, n_frames: int) -> np.ndarray:
        return np.zeros((n_frames, self.channels), dtype=np.float32)
