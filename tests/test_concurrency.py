"""Concurrency and threading tests — rapid switching, multi-mode, thread safety."""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from conftest import tone, silence, assert_audio_ok, assert_not_silent, temp_dir, wav_file, SR


def test_rapid_mode_switching():
    """Alternate RSSI 200x on one FM mode -- no crash, valid output each time."""
    from src.modes.fm import FMMode
    fm = FMMode()
    t = tone(440, 0.05, amplitude=0.5)
    for i in range(200):
        rssi = -30 if i % 2 == 0 else -90
        out = fm.process(t.copy(), signal_db=float(rssi))
        assert_audio_ok(out, f"FM rapid switch iter {i}")
    print("  PASS: 200 rapid RSSI switches on FM")


def test_all_modes_same_input():
    """Same tone through all 5 modes concurrently via threading.Thread."""
    from src.modes.fm import FMMode
    from src.modes.am import AMMode
    from src.modes.amhd import AMHDMode
    from src.modes.fmhd import FMHDMode
    from src.modes.dab import DABMode

    t = tone(440, 1.0, amplitude=0.5)
    modes = {
        "FM": FMMode(),
        "AM": AMMode(),
        "AMHD": AMHDMode(),
        "FMHD": FMHDMode(),
        "DAB+": DABMode(),
    }

    results = {}
    errors = []
    lock = threading.Lock()

    def process_mode(name, mode):
        try:
            out = mode.process(t.copy(), signal_db=-45)
            with lock:
                results[name] = out
        except Exception as e:
            with lock:
                errors.append((name, e))

    threads = [threading.Thread(target=process_mode, args=(n, m)) for n, m in modes.items()]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert not errors, f"Thread errors: {errors}"
    assert len(results) == 5, f"Expected 5 results, got {len(results)}"
    for name, out in results.items():
        assert_audio_ok(out, name)
        assert_not_silent(out, name)
    print("  PASS: all 5 modes processed concurrently without error")


def test_signal_simulator_rssi_bounds():
    """SignalSimulator.set_rssi clamps to [-120, -10] dBm."""
    from src.signal.propagation import SignalSimulator

    s = SignalSimulator()
    s.set_rssi(-200.0)
    assert s.rssi == -120.0, f"Expected -120.0, got {s.rssi}"
    s.set_rssi(1000.0)
    assert s.rssi == -10.0, f"Expected -10.0, got {s.rssi}"
    print("  PASS: RSSI clamped to [-120, -10]")


def test_player_start_stop_cycle():
    """Start/stop Player 5x -- no exceptions, no zombie ffplay."""
    import subprocess

    # Skip if ffplay not available
    try:
        subprocess.run(["ffplay", "-version"], capture_output=True, timeout=3)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("  SKIP: ffplay not available")
        return

    from src.engine.pipeline import AudioPipeline
    from src.engine.player import Player

    class SimpleSource:
        def read_chunk(self, n_frames):
            return np.zeros((n_frames, 2), dtype=np.float32)

    pipeline = AudioPipeline(source=SimpleSource())
    player = Player(pipeline)

    for _ in range(5):
        player.start()
        time.sleep(0.3)
        player.stop()
        time.sleep(0.05)

    # Verify no leftover ffplay processes
    result = subprocess.run(["pgrep", "-x", "ffplay"], capture_output=True, timeout=5)
    assert result.returncode != 0, "Zombie ffplay process(es) still running"
    print("  PASS: 5 start/stop cycles, no zombie ffplay")


def test_metadata_thread_safety():
    """5 threads calling MP3Source.metadata() concurrently for 2 s."""
    from src.sources.mp3 import MP3Source

    # Prepare a temp directory with a real WAV file
    tmp = temp_dir()
    audio = tone(440, 0.5, amplitude=0.3)
    wav_file(str(tmp / "test.wav"), audio, SR)

    source = MP3Source(str(tmp))
    source.open()

    errors = []
    lock = threading.Lock()
    stop_flag = False

    def read_metadata():
        while not stop_flag:
            try:
                _ = source.metadata()
            except Exception as e:
                with lock:
                    errors.append(e)
                break

    threads = [threading.Thread(target=read_metadata) for _ in range(5)]
    for th in threads:
        th.start()

    time.sleep(2.0)
    stop_flag = True

    for th in threads:
        th.join()

    source.close()
    assert not errors, f"Thread safety errors in metadata(): {errors}"
    print("  PASS: concurrent metadata() calls -- no exceptions")


def test_pipeline_thread_safety():
    """push_chunk() called from multiple threads should not crash."""
    from src.engine.pipeline import AudioPipeline

    class LoopingSource:
        def __init__(self):
            self.chunk = np.full((1024, 2), 0.01, dtype=np.float32)

        def read_chunk(self, n_frames):
            return self.chunk[:n_frames].copy()

    pipeline = AudioPipeline(source=LoopingSource())
    errors = []

    def producer(n_iter):
        try:
            for _ in range(n_iter):
                c = pipeline.push_chunk()
                if c is None or c.shape != (1024, 2):
                    errors.append(f"bad chunk: {c.shape if c is not None else None}")
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=producer, args=(100,)) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors, f"Thread safety errors: {errors}"
    print("  PASS: 3 threads × 100 push_chunk -- state consistent")


if __name__ == "__main__":
    print("test_concurrency.py -- concurrency and threading suite\n")
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
            except Exception as e:
                print(f"  FAIL: {name} -- {e}")
                failures += 1
    print(f"\n{failures} failures")
    sys.exit(failures)
