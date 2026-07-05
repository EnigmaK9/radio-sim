"""Tests for error recovery and edge cases."""

import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from src.sources.youtube import YouTubeSource
from src.sources.mp3 import MP3Source
from src.modes.fm import FMMode
from src.modes.am import AMMode
from src.signal.propagation import SignalSimulator
from src.engine.pipeline import AudioPipeline
from src.engine.player import Player

SR = 44100


def _make_wav(path, sr=SR):
    audio = np.zeros((sr, 2), dtype=np.float32)
    int16 = (audio * 32767.0).astype(np.int16)
    with wave.open(str(path), "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(int16.tobytes())
    return path


def _temp_dir():
    return Path(tempfile.mkdtemp(prefix="radiosim_test_"))


def test_frequency_clamping():
    fm = FMMode()
    assert fm.validate_frequency(50) is False
    assert fm.validate_frequency(200) is False
    assert fm.validate_frequency(98.5) is True
    print("  PASS: frequency clamping")


def test_rssi_clamping():
    sim = SignalSimulator(-200)
    assert sim.rssi == -120, f"Expected -120, got {sim.rssi}"
    sim2 = SignalSimulator(500)
    assert sim2.rssi == -10, f"Expected -10, got {sim2.rssi}"
    print("  PASS: RSSI clamping")


def test_source_close_idempotent():
    d = _temp_dir()
    _make_wav(d / "test.wav")
    src = MP3Source(str(d))
    try:
        src.open()
    except (RuntimeError, FileNotFoundError):
        pass
    src.close()
    src.close()  # second close must not crash
    print("  PASS: source close idempotent")


def test_player_stop_idempotent():
    d = _temp_dir()
    _make_wav(d / "test.wav")
    source = MP3Source(str(d))
    pipeline = AudioPipeline(source=source, sample_rate=SR, channels=2)
    player = Player(pipeline)
    try:
        player.start()
    except Exception:
        pass
    player.stop()
    player.stop()  # second stop must not crash
    print("  PASS: player stop idempotent")


def test_empty_playlist_handling():
    d = _temp_dir()
    src = MP3Source(str(d))
    try:
        src.open()
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError as e:
        assert "no supported audio files" in str(e).lower()
    print("  PASS: empty playlist raises clear error")


def test_frequency_step_per_mode():
    fm = FMMode()
    assert fm.frequency_step == 0.1, f"FM step expected 0.1, got {fm.frequency_step}"
    am = AMMode()
    assert am.frequency_step == 1.0, f"AM step expected 1.0, got {am.frequency_step}"
    print("  PASS: frequency step per mode")


def test_source_directory_not_found():
    src = MP3Source("/nonexistent/path/xyz")
    try:
        src.open()
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError as e:
        assert "not found" in str(e).lower()
    print("  PASS: missing dir raises clear error")


def test_rssi_update_clamping():
    sim = SignalSimulator(-45)
    sim.update_rssi(-1000)  # should clamp, not crash
    assert sim.rssi == -120, f"Expected -120 after massive drop, got {sim.rssi}"
    sim.update_rssi(1000)
    assert sim.rssi == -10, f"Expected -10 after massive rise, got {sim.rssi}"
    print("  PASS: RSSI update clamps correctly")


if __name__ == "__main__":
    print("test_error_recovery.py — error handling\n")
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
            except Exception as e:
                print(f"  FAIL: {name} — {e}")
                failures += 1
    print(f"\n{failures} failures")
    sys.exit(failures)
