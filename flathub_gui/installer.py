"""Batch installation runner with streamed output."""

import subprocess


def stream_command(cmd: list, on_line) -> int:
    """Run ``cmd``, calling ``on_line(str)`` for each output line.

    stdout and stderr are merged (Flatpak progress goes to stdout).
    Returns the process exit code; 127 if the executable is missing.
    """
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        on_line("ERROR: flatpak executable not found.")
        return 127
    for line in proc.stdout:
        on_line(line.rstrip())
    proc.wait()
    return proc.returncode


__all__ = ["stream_command"]
