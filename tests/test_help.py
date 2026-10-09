"""Unit tests for flatpak_batch_installer.helptext and flatpak_batch_installer.resources."""

import io
import unittest
from contextlib import redirect_stdout

from flatpak_batch_installer import __version__
from flatpak_batch_installer.helptext import (
    SHORTCUTS,
    USAGE_GUIDE,
    about_text,
    shortcuts_text,
)
from flatpak_batch_installer.resources import icon_path


class GuideTest(unittest.TestCase):
    def test_documents_every_control(self):
        for keyword in ("Load catalog", "Update", "Scope", "Status",
                        "Install selected", "Dark mode", "Filter",
                        "Select page", "Clear", "Save", "Load",
                        "Prev", "Next", "Rows/page", "Working"):
            self.assertIn(keyword, USAGE_GUIDE, keyword)

    def test_workflow_present(self):
        self.assertIn("WHAT THIS APP DOES", USAGE_GUIDE)
        self.assertIn("WORKFLOW", USAGE_GUIDE)
        self.assertIn("TYPICAL FIXES", USAGE_GUIDE)


class ShortcutsTest(unittest.TestCase):
    def test_shortcuts_live_apart_from_guide(self):
        self.assertGreaterEqual(len(SHORTCUTS), 9)
        self.assertIn("KEYBOARD SHORTCUTS", shortcuts_text())
        self.assertIn("Ctrl+K", shortcuts_text())
        self.assertNotIn("KEYBOARD SHORTCUTS", USAGE_GUIDE)

    def test_cli_help_guide_prints_both(self):
        from flatpak_batch_installer.app import run_cli
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = run_cli(["--help-guide"])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("WHAT THIS APP DOES", out)
        self.assertIn("KEYBOARD SHORTCUTS", out)
    def test_about(self):
        text = about_text(__version__)
        self.assertIn(__version__, text)
        self.assertIn("Flatpak Batch Installer", text)
        self.assertIn("GPL", text)


class ResourcesTest(unittest.TestCase):
    def test_icon_bundled(self):
        path = icon_path()
        self.assertIsNotNone(path)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(8), b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
