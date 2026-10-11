"""Batch installation runner with streamed output."""

import subprocess
import threading


def stream_command(cmd: list, on_line, timeout: int = 600) -> int:
    """Run ``cmd``, calling ``on_line(str)`` for each output line.

    stdout and stderr are merged (Flatpak progress goes to stdout).
    Returns the process exit code; 127 if the executable is missing;
    124 if the process is killed after ``timeout`` seconds.
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

    lines = []
    timed_out = threading.Event()

    def _reader():
        for line in proc.stdout:
            lines.append(line.rstrip())

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out.set()
        proc.kill()
        proc.wait()

    reader_thread.join()

    for line in lines:
        on_line(line)

    if timed_out.is_set():
        on_line(f"ERROR: command timed out after {timeout}s.")
        return 124

    return proc.returncode


__all__ = ["stream_command"]
