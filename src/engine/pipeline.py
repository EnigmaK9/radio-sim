"""Audio processing pipeline with ring buffer for thread-safe playback."""

from collections import deque
from typing import Callable

import numpy as np


class AudioPipeline:
    """Chain of audio processors feeding a thread-safe ring buffer.

    Producer (refill thread): source.read_chunk() → processors → buffer.write()
    Consumer (audio callback): buffer.read() → pyaudio output
    """

    def __init__(
        self,
        source: object | None = None,  # AudioSource, set after Step 06
        sample_rate: int = 44100,
        channels: int = 2,
        chunk_size: int = 1024,
        buffer_chunks: int = 32,
    ):
        self.source = source
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.buffer_chunks = buffer_chunks

        self._processors: list[Callable[[np.ndarray], np.ndarray]] = []
        self._buffer: deque[np.ndarray] = deque(maxlen=buffer_chunks)
        self._silence = np.zeros((chunk_size, channels), dtype=np.float32)

    def add_processor(self, fn: Callable[[np.ndarray], np.ndarray]) -> None:
        """Register a processing stage. Called in order for each chunk."""
        self._processors.append(fn)

    def clear_processors(self) -> None:
        """Remove all processing stages."""
        self._processors.clear()

    def push_chunk(self) -> bool:
        """Read one chunk from source, run processor chain, push to buffer.

        Returns True if a chunk was produced, False on EOF/error.
        Called from the refill thread.
        """
        if self.source is None:
            self._buffer.append(self._silence.copy())
            return True

        raw = self.source.read_chunk(self.chunk_size)

        if raw is None:
            return False  # EOF — caller should handle

        # Run processor chain
        processed = raw.astype(np.float32)
        for proc in self._processors:
            processed = proc(processed)

        # Ensure correct shape and clip
        if processed.shape != (self.chunk_size, self.channels):
            processed = self._resize_chunk(processed)

        processed = np.nan_to_num(processed, nan=0.0, posinf=1.0, neginf=-1.0)
        processed = np.clip(processed, -1.0, 1.0, out=processed)
        self._buffer.append(processed)
        return True

    def pop_chunk(self) -> np.ndarray:
        """Read one chunk from the ring buffer for audio output.

        Returns silence if buffer is empty (underrun).
        Called from the PyAudio callback thread.
        """
        if self._buffer:
            return self._buffer.popleft()
        return self._silence.copy()

    @property
    def buffer_fill(self) -> int:
        """Number of chunks currently in the buffer."""
        return len(self._buffer)

    @property
    def buffer_capacity(self) -> int:
        return self.buffer_chunks

    def flush(self) -> None:
        """Clear the buffer (used on mode/source switch)."""
        self._buffer.clear()

    def _resize_chunk(self, data: np.ndarray) -> np.ndarray:
        """Force data to (chunk_size, channels) shape."""
        n_samples = min(len(data), self.chunk_size)
        out = np.zeros((self.chunk_size, self.channels), dtype=np.float32)

        if data.ndim == 1:
            data = np.column_stack([data, data])

        if data.shape[1] == 1 and self.channels == 2:
            data = np.column_stack([data[:, 0], data[:, 0]])
        elif data.shape[1] >= 2:
            data = data[:, : self.channels]

        out[:n_samples] = data[:n_samples]
        return out
