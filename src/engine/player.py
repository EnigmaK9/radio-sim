"""Audio output via aplay subprocess — WAV file + ALSA playback."""

import subprocess
import threading
import time
import wave
import tempfile
from pathlib import Path

import numpy as np


class Player:
    """Plays processed audio via aplay (ALSA). Writes chunks to a temp WAV
    and spawns aplay to play them. For continuous playback, writes new WAVs
    before the current one finishes, overlapping slightly.

    No PortAudio, no ffplay, no PulseAudio needed — just aplay + ALSA.
    """

    def __init__(
        self,
        pipeline: object,
        volume: float = 0.8,
    ):
        self.pipeline = pipeline
        self.volume = max(0.0, min(1.0, volume))

        self._process: subprocess.Popen | None = None
        self._running = False
        self._refill_thread: threading.Thread | None = None
        self._tmp_dir: Path | None = None

        self.underruns: int = 0
        self.total_chunks: int = 0

    # ---- Public API ----

    def start(self) -> None:
        """Start the refill-and-play loop."""
        self._running = True
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="radiosim_"))
        self._refill_thread = threading.Thread(
            target=self._play_loop, daemon=True, name="radiosim-player"
        )
        self._refill_thread.start()

    def stop(self) -> None:
        """Stop playback and clean up."""
        self._running = False

        if self._refill_thread and self._refill_thread.is_alive():
            self._refill_thread.join(timeout=3.0)

        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                self._process.kill()
            self._process = None

        # Clean up temp WAVs
        if self._tmp_dir and self._tmp_dir.exists():
            import shutil
            shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def set_volume(self, vol: float) -> None:
        self.volume = max(0.0, min(1.0, vol))

    @property
    def is_playing(self) -> bool:
        return self._running and (
            self._process is not None and self._process.poll() is None
        )

    # ---- Internal ----

    def _play_loop(self) -> None:
        """Process audio chunks into WAV files and play them via aplay."""
        chunk_duration = self.pipeline.chunk_size / self.pipeline.sample_rate
        wav_duration = 3.0  # seconds per WAV file
        chunks_per_wav = int(wav_duration / chunk_duration)

        file_idx = 0
        while self._running:
            # Accumulate chunks for one WAV file
            buffer = []
            for _ in range(chunks_per_wav):
                if not self._running:
                    break
                chunk = self.pipeline.push_chunk()
                if chunk is None:
                    time.sleep(0.1)
                    continue
                self.total_chunks += 1
                if np.all(chunk == 0):
                    self.underruns += 1
                # Guard NaN/Inf
                chunk = np.nan_to_num(chunk, nan=0.0, posinf=1.0, neginf=-1.0)
                chunk = chunk * self.volume
                buffer.append(np.clip(chunk, -1.0, 1.0))

            if not buffer:
                break

            # Write WAV
            full = np.concatenate(buffer).astype(np.float32)
            wav_path = self._tmp_dir / f"chunk_{file_idx:04d}.wav"
            self._write_wav(full, wav_path)
            file_idx += 1

            # Wait for previous aplay to finish (if any)
            if self._process is not None:
                try:
                    self._process.wait(timeout=wav_duration + 1)
                except subprocess.TimeoutExpired:
                    self._process.kill()

            # Play
            if self._running:
                self._process = subprocess.Popen(
                    ["aplay", "-q", str(wav_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

        # Wait for final aplay
        if self._process:
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def _write_wav(self, audio: np.ndarray, path: Path) -> None:
        """Write float32 stereo audio to a 16-bit WAV file."""
        int16 = (audio * 32767.0).astype(np.int16)
        with wave.open(str(path), "w") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(self.pipeline.sample_rate)
            w.writeframes(int16.tobytes())

    @staticmethod
    def list_devices() -> list[dict]:
        try:
            result = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=3)
            return [{"index": 0, "name": "aplay (ALSA)", "channels": 2, "sample_rate": 44100}]
        except Exception:
            return []
