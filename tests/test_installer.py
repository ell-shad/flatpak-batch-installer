"""Unit tests for flatpak_batch_installer.installer.stream_command."""

import subprocess
import unittest
from unittest.mock import MagicMock, patch


from flatpak_batch_installer.installer import stream_command


class StreamCommandTest(unittest.TestCase):
    def test_stream_command_success(self):
        """On success, on_line is called for each output line and 0 is returned."""
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["line1\n", "line2\n"])
        mock_proc.returncode = 0

        def fake_wait(timeout):
            pass

        mock_proc.wait.side_effect = fake_wait

        lines_received = []

        with patch("flatpak_batch_installer.installer.subprocess.Popen",
                   return_value=mock_proc):
            rc = stream_command(["flatpak", "--version"],
                                on_line=lines_received.append)

        self.assertEqual(rc, 0)
        self.assertEqual(len(lines_received), 2)
        self.assertIn("line1", lines_received[0])
        self.assertIn("line2", lines_received[1])

    def test_stream_command_timeout(self):
        """When communicate raises TimeoutExpired, returns 124 and reports timeout."""
        mock_proc = MagicMock()
        mock_proc.stdout = iter([])  # no output lines
        mock_proc.returncode = -9

        call_count = [0]

        def fake_wait(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call includes timeout= kwarg — simulate timeout
                raise subprocess.TimeoutExpired(cmd=["flatpak"], timeout=5)
            # Second call (after kill) should succeed

        mock_proc.wait.side_effect = fake_wait

        lines_received = []

        with patch("flatpak_batch_installer.installer.subprocess.Popen",
                   return_value=mock_proc):
            rc = stream_command(["flatpak", "install"],
                                on_line=lines_received.append,
                                timeout=5)

        self.assertEqual(rc, 124)
        # on_line must have been called with something mentioning "timed out"
        self.assertTrue(
            any("timed out" in line.lower() for line in lines_received),
            f"Expected 'timed out' in lines: {lines_received}",
        )

    def test_stream_command_missing_executable(self):
        """FileNotFoundError from Popen returns 127 and reports the error."""
        lines_received = []

        with patch("flatpak_batch_installer.installer.subprocess.Popen",
                   side_effect=FileNotFoundError):
            rc = stream_command(["flatpak", "--version"],
                                on_line=lines_received.append)

        self.assertEqual(rc, 127)
        self.assertTrue(
            any("not found" in line.lower() for line in lines_received),
            f"Expected 'not found' in lines: {lines_received}",
        )


if __name__ == "__main__":
    unittest.main()
