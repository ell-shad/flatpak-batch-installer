"""Unit tests for flatpak_batch_installer.helptext and flatpak_batch_installer.resources."""

import unittest

from flatpak_batch_installer import __version__
from flatpak_batch_installer.helptext import USAGE_GUIDE, about_text
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


class AboutTest(unittest.TestCase):
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
