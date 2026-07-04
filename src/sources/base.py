"""Abstract AudioSource — uniform interface for audio input backends."""

from abc import ABC, abstractmethod

import numpy as np


class AudioSource(ABC):
    """Abstract audio source. Produces raw PCM float32 chunks on demand.

    All sources provide audio at 44100 Hz stereo float32 [-1, 1].
    """

    def __init__(self, uri: str):
        self.uri = uri
        self.sample_rate: int = 44100
        self.channels: int = 2
        self._current_metadata: dict = {}

    @abstractmethod
    def open(self) -> None:
        """Initialize the source. Called once before reading."""
        ...

    @abstractmethod
    def read_chunk(self, n_frames: int) -> np.ndarray | None:
        """Return (n_frames, n_channels) float32 array, or None on EOF/error."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release resources."""
        ...

    def metadata(self) -> dict:
        """Return {"title": ..., "artist": ..., "album": ...} for current track."""
        return self._current_metadata

    def advance_track(self) -> bool:
        """Move to next track. Return False if no more tracks."""
        return True  # default: single track, loops
