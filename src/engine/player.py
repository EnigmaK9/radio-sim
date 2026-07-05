"""Audio output via ffplay subprocess pipe — zero native library dependencies."""

import subprocess
import threading
import time

import numpy as np


class Player:
    """Plays audio by piping raw PCM to ffplay via subprocess.

    Uses a refill thread to pull from the pipeline and write to ffplay's
    stdin. No PortAudio/pyaudio/sounddevice needed — just ffmpeg on PATH.
    """

    def __init__(
        self,
        pipeline: object,  # AudioPipeline
        volume: float = 0.8,
        device_index: int | None = None,
    ):
        self.pipeline = pipeline
        self.volume = max(0.0, min(1.0, volume))
        self.device_index = device_index  # ignored; ffplay uses system default

        self._process: subprocess.Popen | None = None
        self._running = False
        self._refill_thread: threading.Thread | None = None

        # Stats
        self.underruns: int = 0
        self.total_chunks: int = 0

    # ---- Public API ----

    def start(self) -> None:
        """Launch ffplay and start the refill thread."""
        self._running = True

        # ffplay: read raw PCM from stdin, play through default audio device
        cmd = [
            "ffplay",
            "-f", "s16le",                       # raw signed 16-bit little-endian
            "-ar", str(self.pipeline.sample_rate),  # sample rate
            "-ac", str(self.pipeline.channels),     # channels
            "-nodisp",                           # no video window
            "-loglevel", "error",                # quiet
            "-i", "pipe:0",                      # read from stdin
        ]

        env = {**__import__("os").environ, "SDL_AUDIODRIVER": "alsa"}
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        self._refill_thread = threading.Thread(
            target=self._refill_loop, daemon=True, name="radiosim-refill"
        )
        self._refill_thread.start()

    def stop(self) -> None:
        """Stop playback and terminate ffplay."""
        self._running = False

        if self._refill_thread and self._refill_thread.is_alive():
            self._refill_thread.join(timeout=2.0)

        if self._process:
            try:
                self._process.stdin.close()
                self._process.terminate()
                self._process.wait(timeout=3)
            except (BrokenPipeError, ProcessLookupError, subprocess.TimeoutExpired):
                self._process.kill()
            self._process = None

    def set_volume(self, vol: float) -> None:
        """Set output volume 0.0–1.0."""
        self.volume = max(0.0, min(1.0, vol))

    @property
    def is_playing(self) -> bool:
        proc = self._process
        return self._running and proc is not None and proc.poll() is None

    # ---- Internal ----

    def _refill_loop(self) -> None:
        """Producer loop — pulls from pipeline, writes to ffplay stdin."""
        try:
            while self._running:
                proc = self._process
                if proc is None or proc.poll() is not None:
                    break

                if self.pipeline.buffer_fill >= self.pipeline.buffer_capacity - 2:
                    time.sleep(0.005)
                    continue

                ok = self.pipeline.push_chunk()
                if not ok:
                    time.sleep(0.1)
                    continue

                chunk = self.pipeline.pop_chunk()
                self.total_chunks += 1

                if np.all(chunk == 0):
                    self.underruns += 1

                # Guard against NaN/Inf
                chunk = np.nan_to_num(chunk, nan=0.0, posinf=1.0, neginf=-1.0)
                chunk = chunk * self.volume
                int_data = (np.clip(chunk, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()

                try:
                    proc.stdin.write(int_data)
                except (BrokenPipeError, OSError, ValueError):
                    break
        except Exception:
            import sys, traceback
            print("Audio refill thread crashed — playback stopped", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    @staticmethod
    def list_devices() -> list[dict]:
        """Check ffplay availability (no real device enumeration)."""
        try:
            subprocess.run(["ffplay", "-version"], capture_output=True, timeout=3)
            return [{"index": 0, "name": "ffplay (default output)", "channels": 2, "sample_rate": 44100}]
        except Exception:
            return []
