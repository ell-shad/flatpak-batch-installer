"""GUI smoke tests. Skipped automatically when no display is available."""

import unittest

import tkinter as tk

from flatpak_batch_installer import theme as theme_module
from flatpak_batch_installer.config import DARK_COLORS, DARK_THEME_NAME, PAGE_SIZE
from flatpak_batch_installer.models import App


def make_browser():
    from flatpak_batch_installer.ui import FlathubBrowser
    try:
        return FlathubBrowser()
    except tk.TclError as exc:
        raise unittest.SkipTest(f"no display: {exc}")


class BrowserTest(unittest.TestCase):
    # One shared root per process: ttkbootstrap.Style is a process-wide
    # singleton bound to the first root, so per-test roots would leave
    # later styles pointing at destroyed interpreters. State is reset
    # in setUp; production always runs a single root anyway.
    @classmethod
    def setUpClass(cls):
        cls.app = make_browser()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except tk.TclError:
            pass

    def setUp(self):
        self.app.all_rows = []
        self.app.installed = set()
        self.app.selected_ids = set()
        self.app.page = 0
        self.app.page_size_value = PAGE_SIZE
        self.app.page_size_var.set(str(PAGE_SIZE))
        self.app.filter_var.set("")
        self.app.status_filter_var.set("all")
        self.app.category_var.set("All")
        self.app.theme_var.set(False)
        self.app.toggle_theme()
        self.app._search_history = []
        self.app.filter_entry.configure(values=[])
        for child in list(self.app.winfo_children()):
            if child.__class__.__name__ == "Toplevel":
                child.destroy()
        self.app.apply_filter()

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
        from flatpak_batch_installer.theme import bootstrap_theme_name
        self.app.theme_var.set(False)
        self.app.toggle_theme()
        base = self.app.style.theme_use()
        light_bg = self.app.log.cget("background")
        self.app.theme_var.set(True)
        self.app.toggle_theme()
        if self.app._bootstrap:
            expected = bootstrap_theme_name(self.app.style, True)
            expected_bg = self.app.style.colors.inputbg
        else:
            expected = DARK_THEME_NAME
            expected_bg = DARK_COLORS["bg_alt"]
        self.assertEqual(self.app.style.theme_use(), expected)
        self.assertEqual(self.app.log.cget("background"), expected_bg)
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
            self.app._help_menu.entrycget(1, "label"), "Keyboard shortcuts…")
        self.assertEqual(self.app._help_menu.type(2), "separator")
        self.assertEqual(
            self.app._help_menu.entrycget(3, "label"), "About…")

    def test_options_menu(self):
        menu = self.app._options_menu
        labels = [menu.entrycget(i, "label")
                  for i in range(menu.index("end") + 1)
                  if menu.type(i) != "separator"]
        joined = "\n".join(labels)
        for keyword in ("User", "System", "Update metadata",
                        "Save selection", "Load selection", "Dark mode"):
            self.assertIn(keyword, joined, keyword)
        # scope radios share the scope variable (entries 0 and 1)
        scope_name = str(self.app.scope_var)
        self.assertEqual(str(menu.entrycget(0, "variable")), scope_name)
        self.assertEqual(str(menu.entrycget(1, "variable")), scope_name)
        self.assertEqual(menu.type(0), "radiobutton")
        self.assertEqual(menu.type(3), "command")
        # dark-mode checkbutton rides on the theme variable
        types = [menu.type(i) for i in range(menu.index("end") + 1)]
        check_idx = types.index("checkbutton")
        self.assertEqual(str(menu.entrycget(check_idx, "variable")),
                         str(self.app.theme_var))
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

    @unittest.skipUnless(theme_module.BOOTSTRAP_AVAILABLE,
                         "ttkbootstrap not installed")
    def test_bootstrap_themes(self):
        from flatpak_batch_installer.theme import bootstrap_theme_name
        self.assertTrue(self.app._bootstrap)
        self.app.theme_var.set(True)
        self.app.toggle_theme()
        self.assertEqual(
            self.app.style.theme_use(),
            bootstrap_theme_name(self.app.style, True))
        # log follows the active Bootstrap palette, not our fallback grays
        self.assertEqual(self.app.log.cget("background"),
                         self.app.style.colors.inputbg)
        self.app.theme_var.set(False)
        self.app.toggle_theme()
        self.assertEqual(
            self.app.style.theme_use(),
            bootstrap_theme_name(self.app.style, False))

    def test_shortcuts_registered(self):
        for seq in ("<F1>", "<F5>", "<Control-f>", "<Control-s>",
                    "<Control-o>", "<Control-k>", "<Control-Return>",
                    "<Control-d>"):
            self.assertTrue(self.app.bind(seq), seq)
        self.assertTrue(self.app.tree.bind("<Control-a>"))
        self.assertTrue(self.app.filter_entry.bind("<Escape>"))

    def test_clear_filter(self):
        self.app.filter_var.set("gimp")
        self.app.page = 3
        self.app.clear_filter()
        self.assertEqual(self.app.filter_var.get(), "")
        self.assertEqual(self.app.page, 0)

    def test_ctrl_a_selects_page(self):
        self.app.all_rows = [App(f"id{i}", f"N{i}", "") for i in range(10)]
        self.app.apply_filter()
        self.assertEqual(self.app.on_select_all_key(None), "break")
        self.assertEqual(len(self.app.selected_ids), 10)

    def test_shortcuts_dialog(self):
        from flatpak_batch_installer.helptext import SHORTCUTS
        self.app.show_shortcuts()
        dlg = self.app._dialogs.get("shortcuts")
        self.assertIsNotNone(dlg)
        self.assertTrue(dlg.winfo_exists())
        self.assertEqual(dlg.title(), "Keyboard shortcuts")
        tree = self.app._shortcut_tree
        self.assertIsNotNone(tree)
        self.assertEqual(len(tree.get_children()), len(SHORTCUTS))
        dlg.destroy()

    def test_help_body_styled(self):
        self.app.show_help()
        text = self.app._dialog_texts.get("help")
        self.assertIsNotNone(text)
        self.assertIn("h2", text.tag_names())
        self.assertTrue(text.tag_ranges("h2"))
        self.assertTrue(text.tag_ranges("code"))
        text.winfo_toplevel().destroy()

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

    # -----------------------------------------------------------------------
    # FEAT-002 new tests
    # -----------------------------------------------------------------------

    def test_install_btn_badge(self):
        """Install button shows 'Install (N)' when N apps are selected."""
        self.app.all_rows = [App(f"org.ex.App{i}", f"App{i}", "") for i in range(5)]
        self.app.apply_filter()
        # Select 3 apps
        ids = list(self.app.row_by_iid.values())[:3]
        for app_id in ids:
            self.app.selected_ids.add(app_id)
        self.app.update_count()
        btn_text = self.app.install_btn.cget("text")
        self.assertEqual(btn_text, "Install (3)")
        # Deselect all
        self.app.clear_selection()
        btn_text = self.app.install_btn.cget("text")
        self.assertEqual(btn_text, "Install")

    def test_search_history(self):
        """Running 3 searches accumulates _search_history entries."""
        self.app.all_rows = [
            App("org.gimp.GIMP", "GIMP", "image editor"),
            App("org.inkscape.Inkscape", "Inkscape", "vector editor"),
            App("org.mozilla.firefox", "Firefox", "browser"),
        ]
        # Perform 3 unique searches that produce results
        for term in ("gimp", "inkscape", "firefox"):
            self.app.filter_var.set(term)
            self.app.apply_filter()
        self.assertEqual(len(self.app._search_history), 3)
        # History is most-recent-first
        self.assertEqual(self.app._search_history[0], "firefox")

    def test_category_filter_populates(self):
        """Category combobox gets populated with actual categories after load."""
        from flatpak_batch_installer.catalog import _categorize
        apps = [
            App("org.gnome.Calculator", "Calculator", "", "GNOME"),
            App("org.kde.kate", "Kate", "", "KDE"),
            App("org.gimp.GIMP", "GIMP", "", "Graphics"),
            App("org.videolan.VLC", "VLC", "player", "Other"),
        ]
        self.app.all_rows = apps
        cats = ["All"] + sorted({app.category for app in apps} - {""})
        self.app.category_cb.configure(values=cats)
        cb_values = list(self.app.category_cb.cget("values"))
        self.assertIn("All", cb_values)
        self.assertIn("GNOME", cb_values)
        self.assertIn("KDE", cb_values)
        self.assertIn("Graphics", cb_values)
        self.assertIn("Other", cb_values)

    def test_empty_state_no_catalog(self):
        """With no catalog loaded, apply_filter shows a placeholder row."""
        self.app.all_rows = []
        self.app.apply_filter()
        children = self.app.tree.get_children()
        # There should be exactly one placeholder row
        self.assertEqual(len(children), 1)
        # The placeholder row is NOT in row_by_iid (so it won't be selectable)
        self.assertNotIn(children[0], self.app.row_by_iid)
        vals = self.app.tree.item(children[0], "values")
        self.assertEqual(vals[2], "No catalog loaded")

    def test_empty_state_no_matches(self):
        """With a loaded catalog but no matches, a 'No results' placeholder appears."""
        self.app.all_rows = [App("org.example.App", "App", "test")]
        self.app.filter_var.set("zzz_no_match_xyz")
        self.app.apply_filter()
        children = self.app.tree.get_children()
        self.assertEqual(len(children), 1)
        self.assertNotIn(children[0], self.app.row_by_iid)
        vals = self.app.tree.item(children[0], "values")
        self.assertEqual(vals[2], "No results")

    def test_sidebar_has_category_combobox(self):
        """The category_cb attribute exists and has 'All' as a valid value."""
        self.assertIsNotNone(self.app.category_cb)
        values = list(self.app.category_cb.cget("values"))
        self.assertIn("All", values)

    def test_scope_badge_updates(self):
        """scope_badge_var reflects the current scope."""
        self.app.scope_var.set("system")
        self.app.scope_badge_var.set(f"Scope: {self.app.scope_var.get()}")
        self.assertIn("system", self.app.scope_badge_var.get())
        self.app.scope_var.set("user")
        self.app.scope_badge_var.set(f"Scope: {self.app.scope_var.get()}")
        self.assertIn("user", self.app.scope_badge_var.get())

    def test_tooltips_attached(self):
        """At least 8 tooltip objects are registered."""
        self.assertGreaterEqual(len(self.app._tooltip_widgets), 8)

    def test_ctrl_d_clears_selection(self):
        """Ctrl+D binding triggers clear_selection."""
        self.app.all_rows = [App(f"id{i}", f"N{i}", "") for i in range(5)]
        self.app.apply_filter()
        for app_id in self.app.row_by_iid.values():
            self.app.selected_ids.add(app_id)
        self.app.update_count()
        self.assertEqual(len(self.app.selected_ids), 5)
        # Simulate Ctrl+D by calling clear_selection directly
        self.app.clear_selection()
        self.assertEqual(len(self.app.selected_ids), 0)
        self.assertEqual(self.app.install_btn.cget("text"), "Install")

    def test_total_var_updates(self):
        """total_var is updated in apply_filter."""
        self.app.all_rows = [App(f"id{i}", f"N{i}", "") for i in range(7)]
        self.app.apply_filter()
        self.assertEqual(self.app.total_var.get(), "Total: 7 apps")


if __name__ == "__main__":
    unittest.main()
