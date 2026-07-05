"""Shared test helpers — tone generators, temp dirs, audio assertions."""

import sys
import tempfile
import wave
from pathlib import Path

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np


SR = 44100
CHUNK = 1024
CHANNELS = 2


def tone(freq: float, duration: float, amplitude: float = 0.5, sr: int = SR) -> np.ndarray:
    """Generate a stereo sine tone. Returns float32 (n_samples, 2)."""
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    wave_data = amplitude * np.sin(2 * np.pi * freq * t)
    return np.column_stack([wave_data, wave_data]).astype(np.float32)


def tone_stereo(freq_l: float, freq_r: float, duration: float, amplitude: float = 0.5, sr: int = SR) -> np.ndarray:
    """Generate stereo tone with different L/R frequencies."""
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    left = amplitude * np.sin(2 * np.pi * freq_l * t)
    right = amplitude * np.sin(2 * np.pi * freq_r * t)
    return np.column_stack([left, right]).astype(np.float32)


def silence(duration: float, sr: int = SR) -> np.ndarray:
    """Generate silent stereo audio."""
    n = int(sr * duration)
    return np.zeros((n, CHANNELS), dtype=np.float32)


def wav_file(path: str, audio: np.ndarray, sr: int = SR) -> str:
    """Write a WAV file to disk. Returns the path."""
    audio = np.clip(audio, -1.0, 1.0)
    int16_data = (audio * 32767.0).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(audio.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(int16_data.tobytes())
    return path


def temp_dir() -> Path:
    """Create a temporary directory for test files."""
    return Path(tempfile.mkdtemp(prefix="radiosim_test_"))


def temp_wav(audio: np.ndarray, sr: int = SR) -> str:
    """Create a temporary WAV file. Caller is responsible for cleanup."""
    d = temp_dir()
    p = str(d / "test.wav")
    wav_file(p, audio, sr)
    return p


def assert_audio_ok(audio: np.ndarray, name: str = "audio") -> None:
    """Assert audio array has valid shape, dtype, range, and no NaN."""
    assert isinstance(audio, np.ndarray), f"{name}: not ndarray (got {type(audio)})"
    assert audio.ndim == 2, f"{name}: expected 2D, got {audio.ndim}D"
    assert audio.shape[1] == CHANNELS, f"{name}: expected {CHANNELS} channels, got {audio.shape[1]}"
    assert audio.dtype == np.float32, f"{name}: expected float32, got {audio.dtype}"
    assert not np.any(np.isnan(audio)), f"{name}: contains NaN"
    assert not np.any(np.isinf(audio)), f"{name}: contains Inf"
    peak = float(abs(audio).max())
    assert peak < 10.0, f"{name}: absurd peak {peak:.2f}"


def assert_not_silent(audio: np.ndarray, name: str = "audio") -> None:
    """Assert audio is not all zeros."""
    rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    assert rms > 1e-6, f"{name}: unexpectedly silent (rms={rms:.6f})"


def run_all_modes(audio: np.ndarray, signal_db: float = -45.0) -> dict:
    """Run the input through all 5 modes, return {mode_name: output}."""
    from src.modes.fm import FMMode
    from src.modes.am import AMMode
    from src.modes.amhd import AMHDMode
    from src.modes.fmhd import FMHDMode
    from src.modes.dab import DABMode

    modes = {
        "FM": FMMode(),
        "AM": AMMode(),
        "AMHD": AMHDMode(),
        "FMHD": FMHDMode(),
        "DAB+": DABMode(),
    }
    results = {}
    for name, mode in modes.items():
        out = mode.process(audio.copy(), signal_db)
        assert_audio_ok(out, name)
        results[name] = out
    return results
