"""GUI smoke tests. Skipped automatically when no display is available."""

import unittest

import tkinter as tk

from flathub_gui import theme as theme_module
from flathub_gui.config import DARK_COLORS, DARK_THEME_NAME, PAGE_SIZE
from flathub_gui.models import App


def make_browser():
    from flathub_gui.ui import FlathubBrowser
    try:
        return FlathubBrowser()
    except tk.TclError as exc:
        raise unittest.SkipTest(f"no display: {exc}")


class BrowserTest(unittest.TestCase):
    def setUp(self):
        self.app = make_browser()
        self.addCleanup(self.app.destroy)

    def test_paging_reaches_everything(self):
        rows = [App(f"org.example.App{i}", f"App{i}", "s") for i in range(450)]
        self.app.all_rows = rows
        self.app.page_size_value = 200
        self.app.apply_filter()
        self.assertEqual(len(self.app.row_by_iid), 200)
        self.assertIn("Page 1/3", self.app.page_label_var.get())
        seen = set()
        while True:
            seen.update(self.app.row_by_iid.values())
            if self.app.page + 1 >= 3:
                break
            self.app.next_page()
        self.assertEqual(seen, {a.app_id for a in rows})
        self.app.next_page()  # clamped at last page
        self.assertEqual(self.app.page, 2)

    def test_selection_persists_across_pages(self):
        self.app.all_rows = [App(f"id{i}", f"N{i}", "") for i in range(250)]
        self.app.page_size_value = 200
        self.app.apply_filter()
        self.app.select_all_visible()
        self.assertEqual(len(self.app.selected_ids), 200)
        self.app.next_page()
        self.assertEqual(len(self.app.selected_ids), 200)

    def test_status_filters_reset_page(self):
        self.app.all_rows = [App("a", "A", ""), App("b", "B", "")]
        self.app.installed = {"a"}
        self.app.page = 1
        self.app.status_filter_var.set("installed")
        self.app.on_status_filter_change()
        self.assertEqual(self.app.page, 0)
        self.assertEqual(len(self.app.row_by_iid), 1)

    def test_theme_toggle_round_trip(self):
        self.app.theme_var.set(False)
        self.app.toggle_theme()
        base = self.app.style.theme_use()
        light_bg = self.app.log.cget("background")
        self.app.theme_var.set(True)
        self.app.toggle_theme()
        self.assertEqual(self.app.style.theme_use(), DARK_THEME_NAME)
        self.assertEqual(self.app.log.cget("background"), DARK_COLORS["bg_alt"])
        self.app.theme_var.set(False)
        self.app.toggle_theme()
        self.assertEqual(self.app.style.theme_use(), base)
        self.assertEqual(self.app.log.cget("background"), light_bg)

    def test_helpers(self):
        self.assertIsInstance(theme_module.system_prefers_dark(), bool)
        self.assertIn("Treeview", theme_module.dark_theme_settings())
        self.assertEqual(PAGE_SIZE, 200)

    def test_modern_chrome(self):
        # no full-width menubar: Help lives in the toolbar dropdown
        self.assertEqual(str(self.app.cget("menu")), "")
        self.assertIsNotNone(self.app._help_menu)
        self.assertEqual(
            self.app._help_menu.entrycget(0, "label"), "How to use…")
        self.assertEqual(
            self.app._help_menu.entrycget(1, "label"), "About…")
        # accent style for the primary action exists in both modes
        for dark in (False, True):
            self.app.theme_var.set(dark)
            self.app.toggle_theme()
            bg = self.app.style.lookup("Accent.TButton", "background")
            self.assertTrue(bg, f"Accent.TButton missing in dark={dark}")
        # rows carry alternating stripe tags
        self.app.all_rows = [App(f"id{i}", f"N{i}", "") for i in range(4)]
        self.app.apply_filter()
        tags = [set(self.app.tree.item(i, "tags"))
                for i in self.app.row_by_iid]
        self.assertEqual(tags[0], {"even"})
        self.assertEqual(tags[1], {"odd"})

    def test_help_and_about_dialogs(self):
        self.app.show_help()
        self.app.show_about()
        titles = set()
        for child in self.app.winfo_children():
            if child.__class__.__name__ == "Toplevel":
                titles.add(child.title())
                child.destroy()
        self.assertIn("How to use", titles)
        self.assertIn("About", titles)
        # reopening reuses a single dialog window
        self.app.show_help()
        self.app.show_help()
        count = sum(1 for c in self.app.winfo_children()
                    if c.__class__.__name__ == "Toplevel")
        self.assertEqual(count, 1)
        for child in self.app.winfo_children():
            if child.__class__.__name__ == "Toplevel":
                child.destroy()


if __name__ == "__main__":
    unittest.main()
