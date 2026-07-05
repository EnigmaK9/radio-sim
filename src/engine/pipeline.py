"""Audio processing pipeline — source → processors → chunk output."""

from typing import Callable

import numpy as np


class AudioPipeline:
    """Chain of audio processors. Each push_chunk reads from source, runs
    processors, and returns the processed chunk directly."""

    def __init__(
        self,
        source: object | None = None,  # AudioSource, set after Step 06
        sample_rate: int = 44100,
        channels: int = 2,
        chunk_size: int = 1024,
    ):
        self.source = source
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size

        self._processors: list[Callable[[np.ndarray], np.ndarray]] = []
        self._silence = np.zeros((chunk_size, channels), dtype=np.float32)

    def add_processor(self, fn: Callable[[np.ndarray], np.ndarray]) -> None:
        """Register a processing stage. Called in order for each chunk."""
        self._processors.append(fn)

    def clear_processors(self) -> None:
        """Remove all processing stages."""
        self._processors.clear()

    def push_chunk(self) -> np.ndarray | None:
        """Read one chunk from source, run processor chain, return processed audio.

        Returns float32 ndarray, or None on EOF/error.
        """
        if self.source is None:
            return self._silence.copy()

        raw = self.source.read_chunk(self.chunk_size)

        if raw is None:
            return None  # EOF

        # Run processor chain
        processed = raw.astype(np.float32)
        for proc in self._processors:
            processed = proc(processed)

        # Ensure correct shape and clip
        if processed.shape != (self.chunk_size, self.channels):
            processed = self._resize_chunk(processed)

        processed = np.nan_to_num(processed, nan=0.0, posinf=1.0, neginf=-1.0)
        processed = np.clip(processed, -1.0, 1.0, out=processed)
        return processed

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
