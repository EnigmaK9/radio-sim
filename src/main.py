"""RadioSim entry point — wires sources, modes, signal simulation, and TUI."""

import signal
import sys
import time

import click
import numpy as np

from src import __version__
from src.engine.pipeline import AudioPipeline
from src.engine.player import Player
from src.modes.am import AMMode
from src.modes.amhd import AMHDMode
from src.modes.base import RadioMode
from src.modes.dab import DABMode
from src.modes.fm import FMMode
from src.modes.fmhd import FMHDMode
from src.signal.propagation import SignalSimulator
from src.sources.mp3 import MP3Source
from src.sources.youtube import YouTubeSource

MODE_MAP: dict[str, type[RadioMode]] = {
    "fm": FMMode,
    "am": AMMode,
    "amhd": AMHDMode,
    "fmhd": FMHDMode,
    "dab": DABMode,
}

MODE_DEFAULTS = {
    "fm": 101.1,
    "am": 1070.0,
    "amhd": 1070.0,
    "fmhd": 101.1,
    "dab": 202.0,
}


def _wrapped_processor(fn, state_ref):
    """Wrap a mode.process() call so it always receives the current signal_db.

    `state_ref` is a single-element list holding the current SignalSimulator
    reference, mutable so the TUI can update RSSI without recreating the processor.
    """
    def wrapper(chunk: np.ndarray) -> np.ndarray:
        sim = state_ref[0]
        mode_fn = fn
        return sim.apply_degradation(chunk, MODE_ORDER[state_ref[1]])
    return wrapper


MODE_ORDER = ["fm", "am", "amhd", "fmhd", "dab"]


@click.command()
@click.option(
    "--mode", "-m",
    type=click.Choice(MODE_ORDER),
    default="fm",
    help="Radio mode to simulate.",
)
@click.option(
    "--freq", "-f",
    type=float,
    default=None,
    help="Frequency (MHz for FM/FMHD/DAB, kHz for AM/AMHD). Auto-selects center if omitted.",
)
@click.option(
    "--source", "-s",
    type=str,
    default="./music/",
    help="Audio source: path to MP3 directory or YouTube URL.",
)
@click.option(
    "--rssi", "-r",
    type=float,
    default=-45.0,
    help="Initial signal strength in dBm (-120 to 0).",
)
@click.option(
    "--volume", "-v",
    type=float,
    default=0.8,
    help="Output volume 0.0–1.0.",
)
@click.option(
    "--tui/--no-tui",
    default=True,
    help="Launch interactive terminal UI (default: yes).",
)
@click.option(
    "--wav", "-w",
    type=str,
    default=None,
    help="Export processed audio to WAV file instead of playing.",
)
@click.option(
    "--duration", "-d",
    type=float,
    default=10.0,
    help="Duration in seconds for --wav export (default: 10).",
)
@click.version_option(version=__version__)
def main(mode: str, freq: float | None, source: str, rssi: float, volume: float, tui: bool, wav: str | None, duration: float) -> None:
    """RadioSim — Simulate radio stations across FM, AM, AMHD, FMHD, and DAB+.

    \b
    Examples:
      python -m src.main --mode fm --freq 101.1 --source ~/Music/
      python -m src.main --mode am --freq 880 --source "https://youtube.com/..."
      python -m src.main --mode dab --freq 202.0 --source ./podcasts/
    """
    # ---- 1. Select mode ----
    mode_cls = MODE_MAP[mode]
    radio_mode = mode_cls()
    if freq is None:
        freq = MODE_DEFAULTS[mode]

    if not radio_mode.validate_frequency(freq):
        lo, hi = radio_mode.frequency_range
        click.echo(f"Warning: {freq} outside {mode.upper()} band ({lo}–{hi}). Clamping.", err=True)
        freq = max(lo, min(hi, freq))

    click.echo(f"RadioSim v{__version__}  |  Mode: {mode.upper()}  |  Freq: {freq}  |  RSSI: {rssi} dBm")

    # ---- 2. Select source ----
    is_youtube = source.startswith("http://") or source.startswith("https://")
    if is_youtube:
        audio_source = YouTubeSource(source)
    else:
        audio_source = MP3Source(source, shuffle=True)

    audio_source.open()
    click.echo(f"Source: {'YouTube' if is_youtube else 'MP3'} — {audio_source.metadata().get('title', source)}")

    # ---- 3. Build pipeline ----
    signal_sim = SignalSimulator(initial_rssi_db=rssi)

    # Shared state for the processor wrapper
    sim_ref = [signal_sim]  # mutable container

    pipeline = AudioPipeline(source=audio_source)

    # Mode + signal processor: apply mode EQ/filter, then signal degradation
    def mode_processor(chunk: np.ndarray) -> np.ndarray:
        return radio_mode.process(chunk, signal_sim.rssi)

    pipeline.add_processor(mode_processor)

    def degradation_processor(chunk: np.ndarray) -> np.ndarray:
        return signal_sim.apply_degradation(chunk, mode)

    pipeline.add_processor(degradation_processor)

    # ---- 4. Export WAV or start playback ----
    if wav:
        _export_wav(radio_mode, signal_sim, audio_source, pipeline, mode, volume, wav, duration)
    else:
        player = Player(pipeline, volume=volume)
        if tui:
            _run_tui(radio_mode, signal_sim, audio_source, pipeline, player, mode, freq, volume)
        else:
            _run_headless(audio_source, pipeline, player)


def _export_wav(
    radio_mode: RadioMode,
    signal_sim: SignalSimulator,
    audio_source,
    pipeline: AudioPipeline,
    mode: str,
    volume: float,
    path: str,
    duration: float,
) -> None:
    """Process audio through the radio pipeline and write to a WAV file."""
    import wave

    total_frames = int(44100 * duration)
    chunks = []
    remaining = total_frames

    click.echo(f"Exporting {duration}s of {mode.upper()} radio to {path} ...")

    while remaining > 0:
        ok = pipeline.push_chunk()
        if not ok:
            break
        chunk = pipeline.pop_chunk()
        chunks.append(chunk)
        remaining -= chunk.shape[0]

    full = np.concatenate(chunks)[:total_frames] if chunks else np.zeros((total_frames, 2), dtype=np.float32)
    full = np.clip(full * volume, -1.0, 1.0)
    int16_data = (full * 32767.0).astype(np.int16)

    with wave.open(path, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(int16_data.tobytes())

    click.echo(f"Exported {int16_data.nbytes / 1024:.0f} KB to {path}")
    audio_source.close()


def _run_tui(
    radio_mode: RadioMode,
    signal_sim: SignalSimulator,
    audio_source,
    pipeline: AudioPipeline,
    player: Player,
    mode: str,
    freq: float,
    volume: float,
) -> None:
    """Launch the Rich TUI and wire callbacks to the engine."""
    from src.ui.tui import MODE_ORDER, RadioTUI

    mode_idx = MODE_ORDER.index(mode) if mode in MODE_ORDER else 0

    # TUI callbacks — mutate shared state safely
    def on_mode_change(new_mode: str) -> None:
        nonlocal radio_mode, mode
        mode = new_mode
        cls = MODE_MAP[new_mode]
        radio_mode = cls()
        # Flush buffer on mode switch to avoid stale audio
        pipeline.flush()

    def on_freq_change(new_freq: float) -> None:
        pass  # Frequency is cosmetic in simulation; mode processing is the same

    def on_rssi_change(new_rssi: float) -> None:
        signal_sim.set_rssi(new_rssi)

    def on_volume_change(new_vol: float) -> None:
        player.set_volume(new_vol)

    tui = RadioTUI(
        on_mode_change=on_mode_change,
        on_freq_change=on_freq_change,
        on_rssi_change=on_rssi_change,
        on_volume_change=on_volume_change,
    )
    tui.state.mode_index = mode_idx
    tui.state.frequency = freq
    tui.state.rssi = signal_sim.rssi
    tui.state.volume = volume
    tui.state.source_type = "youtube" if isinstance(audio_source, YouTubeSource) else "mp3"

    # Start audio
    player.start()

    def sig_handler(sig, frame):
        tui.stop()

    signal.signal(signal.SIGINT, sig_handler)

    # Background metadata updater
    import threading

    def metadata_loop():
        while tui._running:
            tui.update_metadata(audio_source.metadata())
            tui.update_buffer(pipeline.buffer_fill, pipeline.buffer_capacity)
            time.sleep(0.5)

    meta_thread = threading.Thread(target=metadata_loop, daemon=True)
    meta_thread.start()

    tui.run()
    player.stop()
    audio_source.close()
    click.echo("RadioSim stopped.")


def _run_headless(audio_source, pipeline: AudioPipeline, player: Player) -> None:
    """Simple headless playback — no TUI."""
    import threading

    player.start()

    stop_event = threading.Event()

    def wait_for_quit():
        try:
            input("Press Enter to stop...\n")
        except (EOFError, KeyboardInterrupt):
            pass
        stop_event.set()

    input_thread = threading.Thread(target=wait_for_quit, daemon=True)
    input_thread.start()
    stop_event.wait()

    player.stop()
    audio_source.close()
    click.echo("RadioSim stopped.")


if __name__ == "__main__":
    main()
