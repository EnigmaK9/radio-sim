"""Rich-based radio receiver TUI — interactive faceplate with live tuning."""

import time
from dataclasses import dataclass
from typing import Callable

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box


@dataclass
class TUIState:
    """Mutable state shared between TUI and engine."""

    frequency: float = 101.1
    mode_index: int = 0  # index into MODE_ORDER
    rssi: float = -45.0
    volume: float = 0.8
    playing: bool = False
    source_type: str = "mp3"  # "mp3" or "youtube"
    source_path: str = "./music/"

    # Read-only from engine
    metadata: dict | None = None
    buffer_fill: int = 0
    buffer_capacity: int = 32


MODE_ORDER = ["fm", "am", "amhd", "fmhd", "dab"]


class RadioTUI:
    """Interactive terminal radio receiver using Rich.

    Displays a simulated radio faceplate with frequency dial,
    signal strength meter, now-playing info, and keyboard controls.
    """

    def __init__(
        self,
        on_mode_change: Callable[[str], None] | None = None,
        on_freq_change: Callable[[float], None] | None = None,
        on_rssi_change: Callable[[float], None] | None = None,
        on_volume_change: Callable[[float], None] | None = None,
        on_next_track: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
        get_display_info: Callable[[], dict] | None = None,
    ):
        self.state = TUIState()
        self.console = Console()
        self._running = False
        self._start_time = time.time()
        self._dirty = True
        self._flash_rssi = 0.0
        self._flash_vol = 0.0

        # Callbacks to engine
        self._on_mode_change = on_mode_change or (lambda m: None)
        self._on_freq_change = on_freq_change or (lambda f: None)
        self._on_rssi_change = on_rssi_change or (lambda r: None)
        self._on_volume_change = on_volume_change or (lambda v: None)
        self._on_quit = on_quit or (lambda: None)
        self._on_next_track = on_next_track or (lambda: None)
        self._get_display_info = get_display_info or (lambda: {})

    def update_metadata(self, meta: dict) -> None:
        self.state.metadata = meta

    def update_buffer(self, fill: int, capacity: int) -> None:
        self.state.buffer_fill = fill
        self.state.buffer_capacity = capacity

    def run(self) -> None:
        """Main TUI event loop."""
        self._running = True

        try:
            with Live(self._render(), console=self.console, refresh_per_second=15, screen=True) as live:
                while self._running:
                    key = self._poll_key()
                    if key:
                        self._handle_key(key)
                    if self._dirty:
                        live.update(self._render())
                        self._dirty = False
                    time.sleep(0.04)  # ~25 fps
        except KeyboardInterrupt:
            pass
        finally:
            self._on_quit()

    def stop(self) -> None:
        self._running = False

    # ---- render ----

    def _render(self) -> Layout:
        """Build the full Rich layout tree."""
        root = Layout()
        root.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=5),
        )

        root["body"].split_row(
            Layout(name="dial", ratio=2),
            Layout(name="info", ratio=2),
        )

        root["header"].update(self._render_header())
        root["body"]["dial"].update(self._render_dial())
        root["body"]["info"].update(self._render_info())
        root["footer"].update(self._render_footer())

        return root

    def _render_header(self) -> Panel:
        mode = MODE_ORDER[self.state.mode_index].upper()
        unit = "MHz" if mode in ("FM", "FMHD", "DAB+") else "kHz"
        freq_str = f"{self.state.frequency:.1f}" if unit == "MHz" else f"{self.state.frequency:.0f}"

        bars = self._rssi_bars(self.state.rssi)

        text = Text()
        text.append(f"  RADIOSIM  │  {mode}  ", style="bold white on blue")
        text.append(f"│  {freq_str} {unit}  ", style="bold cyan")
        if time.time() - self._flash_rssi < 0.3:
            rssi_style = "reverse white on green"
        else:
            rssi_style = "green"
        text.append(f"│  RSSI {bars} {self.state.rssi:.0f} dBm  ", style=rssi_style)
        if time.time() - self._flash_vol < 0.3:
            vol_style = "reverse white on yellow"
        else:
            vol_style = "yellow"
        text.append(f"│  Vol: {int(self.state.volume * 100)}%  ", style=vol_style)

        return Panel(text, box=box.HEAVY, style="blue")

    def _render_dial(self) -> Panel:
        mode = MODE_ORDER[self.state.mode_index].upper()
        freq = self.state.frequency
        unit = "MHz" if mode in ("FM", "FMHD", "DAB+") else "kHz"

        # Frequency dial as ASCII art
        bar = self._freq_bar(freq, mode)

        content = Text()
        content.append("\n")
        content.append("     ╔═══════════════════════════════════╗\n", style="blue")
        content.append("     ║                                   ║\n", style="blue")
        content.append(f"     ║         {bar}         ║\n", style="blue")
        content.append("     ║                                   ║\n", style="blue")
        content.append(f"     ║       TUNED: {freq:>8.1f} {unit:<4}      ║\n", style="cyan bold")
        content.append("     ║                                   ║\n", style="blue")
        content.append("     ╚═══════════════════════════════════╝\n", style="blue")
        content.append("\n")
        content.append(f"     ◄◄  ◄  ►  ►►    step: {self._step_size(mode)} {unit}", style="dim")

        return Panel(content, title="Tuner", border_style="blue", box=box.ROUNDED)

    def _render_info(self) -> Panel:
        mode_key = MODE_ORDER[self.state.mode_index]
        mode = mode_key.upper()

        # Mode details table
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Property", style="dim", width=14)
        table.add_column("Value", style="bold")

        info = self._get_display_info()

        table.add_row("Mode:", f"[cyan]{mode}[/cyan]")
        table.add_row("Band:", info.get("band", ""))
        table.add_row("Audio BW:", info.get("audio_bw", ""))
        table.add_row("Stereo:", info.get("stereo", ""))
        table.add_row("Noise:", info.get("noise", ""))
        table.add_row("RSSI:", f"{self.state.rssi:.0f} dBm  {self._rssi_bars(self.state.rssi)}")
        table.add_row("Buffer:", f"{self.state.buffer_fill}/{self.state.buffer_capacity} chunks")

        # Now playing
        meta = self.state.metadata or {}
        table.add_row("", "")
        table.add_row("Now Playing:", f"[bold yellow]{meta.get('title', '—')}[/bold yellow]")
        if meta.get("artist"):
            table.add_row("", meta["artist"])
        table.add_row("Source:", f"{meta.get('track', '—')}  [{meta.get('album', '—')}]")

        return Panel(table, title="Station Info", border_style="cyan", box=box.ROUNDED)

    def _render_footer(self) -> Panel:
        mode_order_str = "  ".join(
            f"[{'reverse cyan' if i == self.state.mode_index else 'dim'}]{m.upper()}[/{'reverse cyan' if i == self.state.mode_index else 'dim'}]"
            for i, m in enumerate(MODE_ORDER)
        )

        content = Text()
        content.append(f"  {mode_order_str}\n", style="bold")
        content.append(
            "  [Q]uit  [M]ode  [←→]Tune  [↑↓]Vol  [N]ext  [R]SSI",
            style="dim",
        )

        return Panel(content, box=box.HEAVY, border_style="blue")

    # ---- keyboard ----

    def _poll_key(self) -> str | None:
        import sys, select
        if not select.select([sys.stdin], [], [], 0.0)[0]:
            return None
        try:
            from rich import getch
            ch = getch.getch()
            if ch == '\x1b':
                # Read rest of escape sequence with short timeout
                import termios, tty
                seq = '\x1b'
                old = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin)
                try:
                    while select.select([sys.stdin], [], [], 0.01)[0]:
                        seq += sys.stdin.read(1)
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
                return seq
            return ch
        except Exception:
            return None

    def _handle_key(self, key: str) -> None:
        if key in ("q", "Q", "\x1b"):  # q or Esc
            self._running = False
        elif key in ("m", "M", "\t"):  # m or Tab
            self.state.mode_index = (self.state.mode_index + 1) % len(MODE_ORDER)
            self._on_mode_change(MODE_ORDER[self.state.mode_index])
            self._dirty = True
        elif key in ("n", "N"):
            self._on_next_track()
            self._dirty = True
        elif key in ("r", "R"):
            # Randomize RSSI
            import random
            self.state.rssi = random.uniform(-90, -30)
            self._on_rssi_change(self.state.rssi)
            self._flash_rssi = time.time()
            self._dirty = True
        elif key in ("[",):
            self.state.rssi = max(-120, self.state.rssi - 5)
            self._on_rssi_change(self.state.rssi)
            self._flash_rssi = time.time()
            self._dirty = True
        elif key in ("]",):
            self.state.rssi = min(-10, self.state.rssi + 5)
            self._on_rssi_change(self.state.rssi)
            self._flash_rssi = time.time()
            self._dirty = True
        # Arrow keys come as escape sequences
        elif key in ("\x1b[A", "\x1bOA"):  # Up arrow
            self.state.volume = min(1.0, self.state.volume + 0.05)
            self._on_volume_change(self.state.volume)
            self._flash_vol = time.time()
            self._dirty = True
        elif key in ("\x1b[B", "\x1bOB"):  # Down arrow
            self.state.volume = max(0.0, self.state.volume - 0.05)
            self._on_volume_change(self.state.volume)
            self._flash_vol = time.time()
            self._dirty = True
        elif key in ("\x1b[C", "\x1bOC"):  # Right arrow
            step = self._step_size(MODE_ORDER[self.state.mode_index])
            self.state.frequency += step
            self.state.frequency = round(self.state.frequency, 1)
            self._on_freq_change(self.state.frequency)
            self._dirty = True
        elif key in ("\x1b[D", "\x1bOD"):  # Left arrow
            step = self._step_size(MODE_ORDER[self.state.mode_index])
            self.state.frequency -= step
            self.state.frequency = round(self.state.frequency, 1)
            self._on_freq_change(self.state.frequency)
            self._dirty = True
        elif key in ("+", "="):
            self.state.volume = min(1.0, self.state.volume + 0.05)
            self._on_volume_change(self.state.volume)
            self._flash_vol = time.time()
            self._dirty = True
        elif key in ("-", "_"):
            self.state.volume = max(0.0, self.state.volume - 0.05)
            self._on_volume_change(self.state.volume)
            self._flash_vol = time.time()
            self._dirty = True
        elif key == "s":
            self.state.source_type = "youtube" if self.state.source_type == "mp3" else "mp3"
            self._dirty = True

    # ---- helpers ----

    def _rssi_bars(self, rssi: float) -> str:
        """S-meter style: 0–5 bars."""
        if rssi > -40:
            n = 5
        elif rssi > -55:
            n = 4
        elif rssi > -70:
            n = 3
        elif rssi > -85:
            n = 2
        elif rssi > -100:
            n = 1
        else:
            n = 0
        bars = "█" * n + "░" * (5 - n)
        if n >= 4:
            color = "green"
        elif n >= 2:
            color = "yellow"
        else:
            color = "red"
        return f"[{color}]{bars}[/{color}]"

    def _freq_bar(self, freq: float, mode: str) -> str:
        """ASCII frequency dial bar."""
        ranges = {
            "FM": (87.5, 108.0),
            "AM": (530, 1710),
            "AMHD": (530, 1710),
            "FMHD": (87.5, 108.0),
            "DAB+": (174.0, 240.0),
        }
        r = ranges.get(mode, (87.5, 108.0))
        pos = (freq - r[0]) / (r[1] - r[0])
        pos = max(0, min(1, pos))
        width = 29
        tick = int(pos * width)
        bar = "─" * tick + "█" + "─" * (width - tick - 1)
        return f"[cyan]{bar}[/cyan]"

    def _step_size(self, mode: str) -> float:
        if mode in ("FM", "FMHD", "DAB+"):
            return 0.1
        return 1.0  # kHz for AM/AMHD
