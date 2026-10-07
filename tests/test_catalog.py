"""Unit tests for flathub_gui.catalog (headless, stdlib unittest)."""

import os
import tempfile
import unittest

from flathub_gui.catalog import (
    filter_rows,
    load_selection,
    paginate,
    parse_remote_ls,
    save_selection,
)
from flathub_gui.models import App


def make_apps(n=450):
    return [App(app_id=f"org.example.App{i}", name=f"App{i}",
                summary=f"summary {i}") for i in range(n)]


class ParseTest(unittest.TestCase):
    def test_basic(self):
        rows = parse_remote_ls(
            "org.gimp.GIMP\tGIMP\tImage editor\n"
            "org.videolan.VLC\tVLC\tPlayer\n"
        )
        self.assertEqual(rows, [
            App("org.gimp.GIMP", "GIMP", "Image editor"),
            App("org.videolan.VLC", "VLC", "Player"),
        ])

    def test_skips_blank_and_malformed(self):
        rows = parse_remote_ls("\nbadline-without-tabs\norg.a.B\tB\tS\n")
        self.assertEqual(rows, [App("org.a.B", "B", "S")])

    def test_missing_summary(self):
        self.assertEqual(parse_remote_ls("org.a.B\tB"),
                         [App("org.a.B", "B", "")])


class FilterTest(unittest.TestCase):
    def setUp(self):
        self.rows = [App("org.gimp.GIMP", "GIMP", "editor"),
                     App("org.videolan.VLC", "VLC", "player")]

    def test_query_matches_all_fields(self):
        self.assertEqual(len(filter_rows(self.rows, "gimp", set())), 1)
        self.assertEqual(len(filter_rows(self.rows, "vlc", set())), 1)
        self.assertEqual(len(filter_rows(self.rows, "player", set())), 1)
        self.assertEqual(len(filter_rows(self.rows, "", set())), 2)

    def test_status_filters(self):
        installed = {"org.gimp.GIMP"}
        self.assertEqual(
            [a.app_id for a in filter_rows(self.rows, "", installed, "installed")],
            ["org.gimp.GIMP"])
        self.assertEqual(
            [a.app_id for a in filter_rows(self.rows, "", installed, "not-installed")],
            ["org.videolan.VLC"])
        self.assertEqual(
            [a.app_id for a in filter_rows(self.rows, "", installed,
                                           "selected", {"org.videolan.VLC"})],
            ["org.videolan.VLC"])

    def test_model_matches(self):
        self.assertTrue(App("a", "Alpha", "x").matches("ALPHA"))
        self.assertFalse(App("a", "Alpha", "x").matches("zzz"))


class PaginateTest(unittest.TestCase):
    def test_pages(self):
        items = make_apps(450)
        page, total, idx = paginate(items, 0, 200)
        self.assertEqual((len(page), total, idx), (200, 3, 0))
        page, total, idx = paginate(items, 2, 200)
        self.assertEqual(len(page), 50)
        self.assertEqual(page[0].app_id, "org.example.App400")

    def test_clamps(self):
        items = make_apps(450)
        self.assertEqual(paginate(items, 99, 200)[2], 2)
        self.assertEqual(paginate(items, -5, 200)[2], 0)

    def test_empty(self):
        self.assertEqual(paginate([], 0, 200), ([], 0, 0))


class SelectionFileTest(unittest.TestCase):
    def test_round_trip_dedupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sel.txt")
            save_selection(["b", "a", "a", "  "], path)
            with open(path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "b\na\na\n")
            self.assertEqual(load_selection(path), ["b", "a"])

    def test_comments_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sel.txt")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("# comment\norg.a.B\n\norg.c.D\n")
            self.assertEqual(load_selection(path), ["org.a.B", "org.c.D"])


if __name__ == "__main__":
    unittest.main()
