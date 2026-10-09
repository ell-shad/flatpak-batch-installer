"""Static consistency tests for packaging metadata (no display needed)."""

import configparser
import glob
import os
import unittest
import xml.dom.minidom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ID = "io.github.flatpak-batch-installer"


def desktop_path():
    return os.path.join(
        ROOT, "packaging", "desktop", f"{APP_ID}.desktop")


def metainfo_path():
    return os.path.join(
        ROOT, "packaging", "metainfo", f"{APP_ID}.metainfo.xml")


class DesktopTest(unittest.TestCase):
    def test_desktop_file(self):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(desktop_path())
        entry = parser["Desktop Entry"]
        self.assertEqual(entry["Exec"], "flatpak-batch-installer")
        self.assertEqual(entry["Icon"], APP_ID)
        self.assertEqual(entry["Type"], "Application")
        self.assertIn("flatpak", entry.get("Keywords", "").lower())


class MetainfoTest(unittest.TestCase):
    def test_metainfo(self):
        doc = xml.dom.minidom.parse(metainfo_path())
        text = lambda tag: doc.getElementsByTagName(tag)[0].firstChild.data
        self.assertEqual(text("id"), APP_ID)
        self.assertIn("GPL", text("project_license"))
        launchable = doc.getElementsByTagName("launchable")[0]
        self.assertEqual(launchable.firstChild.data, f"{APP_ID}.desktop")


class IconsTest(unittest.TestCase):
    def test_hicolor_set_matches_id(self):
        found = glob.glob(os.path.join(
            ROOT, "assets", "hicolor", "*", "apps", "*.png"))
        self.assertGreaterEqual(len(found), 5)
        for path in found:
            self.assertEqual(os.path.basename(path), f"{APP_ID}.png")

    def test_runtime_icon_exists(self):
        icon = os.path.join(ROOT, "flatpak_batch_installer", "data", "icon.png")
        with open(icon, "rb") as fh:
            self.assertEqual(fh.read(8), b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
