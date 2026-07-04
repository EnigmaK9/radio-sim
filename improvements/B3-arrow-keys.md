# B3 — Arrow Key Handling Fragile Across Terminals (HIGH)

## What's wrong

`tui.py:258-273` — Arrow keys are matched against hardcoded escape sequences:

```python
elif key == "\x1b[A":  # Up arrow — only works in xterm/vt100
elif key == "\x1b[B":  # Down arrow
elif key == "\x1b[C":  # Right arrow
elif key == "\x1b[D":  # Left arrow
```

Problems:
1. Some terminals send `\x1bOA` instead of `\x1b[A` (application mode)
2. tmux/screen may transform these sequences
3. SSH with different TERM settings changes the codes
4. Windows Terminal / ConPTY uses different sequences
5. No handling of Home/End/PgUp/PgDn which could be useful
6. Single `\x1b` (Escape key) is ambiguous — it's also the start of every arrow sequence

## Root cause

Rich's `getch` returns raw bytes without decoding escape sequences. We're
doing manual terminal sequence parsing, which is inherently fragile.

## Fix

Use a proper key parser that handles multi-byte escape sequences:

```python
# tui.py — replace _poll_key with Rich's built-in key handling
def _poll_key(self) -> str | None:
    """Non-blocking key poll using Rich's getch with sequence decoding."""
    import sys, select
    if not select.select([sys.stdin], [], [], 0.0)[0]:
        return None
    try:
        from rich import getch
        ch = getch.getch()
        if ch == '\x1b':
            # Read the rest of the escape sequence with a short timeout
            seq = '\x1b'
            import termios, tty
            old = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin)
            try:
                import select
                while select.select([sys.stdin], [], [], 0.01)[0]:
                    seq += sys.stdin.read(1)
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
            return seq
        return ch
    except Exception:
        return None
```

Then handle sequences properly:

```python
def _handle_key(self, key: str) -> None:
    if key == "q" or key == "Q":
        self._running = False
    elif key == "\x1b":  # lone escape
        self._running = False
    elif key in ("\x1b[A", "\x1bOA"):  # Up
        self.state.volume = min(1.0, self.state.volume + 0.05)
        self._on_volume_change(self.state.volume)
    elif key in ("\x1b[B", "\x1bOB"):  # Down
        ...
    # etc.
```

### Alternative: Use `rich.text.Text.keys` or `prompt_toolkit`

Rich doesn't have built-in key parsing. The above is the minimal
cross-terminal fix. If we want full robustness, `prompt_toolkit`
adds a dependency. Not worth it for 4 arrow keys.

### Lines changed: ~20 in tui.py

## Verification

```bash
# Test in different terminals
python -m src.main --mode fm --freq 101.1 --source ~/Music/
# Press arrows, ensure they work in: gnome-terminal, tmux, SSH, xterm
```
