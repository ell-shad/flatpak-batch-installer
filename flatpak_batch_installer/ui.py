"""Tkinter GUI: catalog table, search, pagination, batch install."""

import queue
import threading
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from . import __version__
from .catalog import filter_rows, load_selection, paginate, save_selection
from .config import (
    CHECKED,
    DARK_COLORS,
    DARK_THEME_NAME,
    DEFAULT_SCOPE,
    PAGE_SIZE,
    REMOTE,
    UNCHECKED,
)
from .flatpak import (
    build_install_cmd,
    get_installed_union,
    load_catalog,
    run_flatpak,
    scope_args,
)
from .installer import stream_command
from .helptext import USAGE_GUIDE, about_text
from .resources import load_icon
from .theme import (
    BOOTSTRAP_AVAILABLE,
    bootstrap_theme_name,
    create_style,
    dark_theme_settings,
    is_bootstrap,
    polish_active_theme,
    system_prefers_dark,
)


class FlathubBrowser(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Flatpak Batch Installer")
        self.geometry("1120x680")

        self.all_rows = []
        self.installed = set()
        self.selected_ids = set()
        self.row_by_iid = {}
        self.log_queue = queue.Queue()
        self.busy = False
        self.page = 0
        self.page_size_value = PAGE_SIZE

        self.scope_var = tk.StringVar(value=DEFAULT_SCOPE)
        self.status_filter_var = tk.StringVar(value="all")
        self.filter_var = tk.StringVar()
        self.selected_count = tk.StringVar(value="Selected: 0 apps")
        self.theme_var = tk.BooleanVar(value=False)
        self.page_label_var = tk.StringVar(value="No catalog loaded.")
        self.busy_label_var = tk.StringVar(value="")

        self.style = create_style(self)
        self._base_theme = self.style.theme_use()
        self._dark_ttk_ok = False
        self._bootstrap = is_bootstrap(self.style)
        self._dialogs = {}
        self._icon_refs = []

        self._build_widgets()
        self._init_theme()
        self._set_window_icon()
        self._build_shortcuts()
        self.after(100, self.poll_log)

    # -- layout: two compact top rows; pager lives under the table --------
    def _build_widgets(self):
        # Row 1: catalog source + install action
        bar = ttk.Frame(self, padding=(8, 8, 8, 4))
        bar.pack(fill="x")

        ttk.Button(bar, text="Load catalog",
                   command=self.load_catalog).pack(side="left")

        ttk.Button(bar, text="Update",
                   command=self.update_metadata).pack(side="left", padx=(6, 0))

        ttk.Label(bar, text="Scope:").pack(side="left", padx=(8, 4))
        scope = ttk.Combobox(bar, textvariable=self.scope_var, width=7,
                             state="readonly", values=["user", "system"])
        scope.pack(side="left")
        scope.bind("<<ComboboxSelected>>", lambda e: self.load_catalog())

        ttk.Label(bar, text="Status:").pack(side="left", padx=(8, 4))
        status_cb = ttk.Combobox(
            bar, textvariable=self.status_filter_var, width=12,
            state="readonly",
            values=["all", "installed", "not-installed", "selected"])
        status_cb.pack(side="left")
        status_cb.bind("<<ComboboxSelected>>", self.on_status_filter_change)

        ttk.Button(bar, text="Install selected", style="Accent.TButton",
                   command=self.install_selected).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(bar, text="Dark mode", variable=self.theme_var,
                        command=self.toggle_theme).pack(side="left", padx=(8, 0))

        help_btn = ttk.Menubutton(bar, text="Help")
        help_menu = tk.Menu(help_btn, tearoff=0)
        help_menu.add_command(label="How to use…", accelerator="F1",
                              command=self.show_help)
        help_menu.add_command(label="About…", command=self.show_about)
        help_btn.configure(menu=help_menu)
        help_btn.pack(side="left", padx=(8, 0))
        self._help_menu = help_menu  # keep a ref alongside the menubutton

        # Row 2: search + selection (Save/Load act on the selection, so live here)
        filt = ttk.Frame(self, padding=(8, 0, 8, 4))
        filt.pack(fill="x")
        ttk.Label(filt, text="Filter:").pack(side="left")
        entry = ttk.Entry(filt, textvariable=self.filter_var, width=32)
        entry.pack(side="left", padx=(4, 0))
        entry.bind("<KeyRelease>", lambda e: self.schedule_filter())
        self.filter_entry = entry
        ttk.Button(filt, text="Select page",
                   command=self.select_all_visible).pack(side="left", padx=(8, 0))
        ttk.Button(filt, text="Clear", command=self.clear_selection).pack(
            side="left", padx=4)
        ttk.Label(filt, textvariable=self.selected_count).pack(side="left", padx=8)
        ttk.Button(filt, text="Load…",
                   command=self.load_selection_dialog).pack(side="right")
        ttk.Button(filt, text="Save…",
                   command=self.save_selection_dialog).pack(side="right", padx=(0, 4))

        # Status line doubles as the busy-indicator row (spinner + Working…)
        statusbar = ttk.Frame(self, padding=(8, 0, 8, 2))
        statusbar.pack(fill="x")
        self.status = tk.StringVar(
            value="Click 'Load catalog' first. Click the checkbox column to select apps.")
        ttk.Label(statusbar, textvariable=self.status, anchor="w",
                  wraplength=900).pack(side="left", fill="x", expand=True)
        ttk.Label(statusbar, textvariable=self.busy_label_var).pack(side="right")
        self.progress = ttk.Progressbar(statusbar, mode="indeterminate",
                                        length=120)
        self.progress.pack(side="right", padx=(0, 6))

        columns = ("sel", "status", "name", "appid", "summary")
        self.tree = ttk.Treeview(self, columns=columns, show="headings",
                                 selectmode="extended")
        self.tree.heading("sel", text="✓")
        self.tree.heading("status", text="Status")
        self.tree.heading("name", text="Name")
        self.tree.heading("appid", text="App ID")
        self.tree.heading("summary", text="Summary")
        self.tree.column("sel", width=36, anchor="center", stretch=False)
        self.tree.column("status", width=100, anchor="w", stretch=False)
        self.tree.column("name", width=210, anchor="w")
        self.tree.column("appid", width=270, anchor="w")
        self.tree.column("summary", width=480, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=4)
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<space>", self.on_space_toggle)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_focus)

        # Pager sits under the table it controls (was crowding the top rows)
        pager = ttk.Frame(self, padding=(8, 2, 8, 0))
        pager.pack(fill="x")
        self.prev_btn = ttk.Button(pager, text="< Prev",
                                   command=self.prev_page)
        self.prev_btn.pack(side="left")
        self.next_btn = ttk.Button(pager, text="Next >",
                                   command=self.next_page)
        self.next_btn.pack(side="left", padx=6)
        ttk.Label(pager, textvariable=self.page_label_var).pack(side="left", padx=6)
        ttk.Label(pager, text="Rows/page:").pack(side="left", padx=(8, 4))
        self.page_size_var = tk.StringVar(value=str(PAGE_SIZE))
        page_size_cb = ttk.Combobox(pager, textvariable=self.page_size_var,
                                    width=5, state="readonly",
                                    values=["100", "200", "500"])
        page_size_cb.pack(side="left")
        page_size_cb.bind("<<ComboboxSelected>>", self.on_page_size_change)

        self.detail = tk.StringVar(value="Select a row to see details.")
        ttk.Label(self, textvariable=self.detail, anchor="w",
                  wraplength=1080).pack(fill="x", padx=8, pady=(0, 4))

        self.log = tk.Text(self, height=9, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=False, padx=8, pady=(0, 8))

    # -- logging / status ----------------------------------------------
    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def poll_log(self):
        try:
            while True:
                self.append_log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self.poll_log)

    def set_busy(self, busy):
        self.busy = busy
        if busy:
            self.busy_label_var.set("Working…")
            self.progress.start(12)
        else:
            self.busy_label_var.set("")
            self.progress.stop()

    # -- theme (stdlib only, no extra deps) --------------------------------
    def _init_theme(self):
        if not self._bootstrap:
            try:
                if DARK_THEME_NAME not in self.style.theme_names():
                    parent = ("clam" if "clam" in self.style.theme_names()
                              else self._base_theme)
                    self.style.theme_create(DARK_THEME_NAME, parent=parent,
                                            settings=dark_theme_settings())
                self._dark_ttk_ok = True
            except tk.TclError:
                self._dark_ttk_ok = False
        self._light_root_bg = self.cget("background")
        self._light_text = {
            "background": self.log.cget("background"),
            "foreground": self.log.cget("foreground"),
            "insertbackground": self.log.cget("insertbackground"),
            "selectbackground": self.log.cget("selectbackground"),
        }
        if system_prefers_dark():
            self.theme_var.set(True)
            self._set_dark(True)
        else:
            self._apply_polish()
        if not BOOTSTRAP_AVAILABLE:
            self.append_log(
                "Note: ttkbootstrap is not installed — using built-in "
                "themes. Install it (`pip install ttkbootstrap`) for the "
                "modern light/dark look.")

    def _is_dark_mode(self):
        return bool(self.theme_var.get()
                    and (self._bootstrap or self._dark_ttk_ok))

    def _text_colors(self, dark):
        """One dict for root bg, Text widgets and combobox popups alike."""
        if self._bootstrap:
            col = self.style.colors
            return {
                "root_bg": col.bg,
                "background": col.inputbg,
                "foreground": col.inputfg,
                "insertbackground": col.inputfg,
                "selectbackground": col.selectbg,
                "selectforeground": col.selectfg,
                "listbox_bg": col.inputbg,
                "listbox_fg": col.inputfg,
                "listbox_select_bg": col.selectbg,
                "listbox_select_fg": col.selectfg,
            }
        if dark:
            c = DARK_COLORS
            return {
                "root_bg": c["bg"],
                "background": c["bg_alt"],
                "foreground": c["fg"],
                "insertbackground": c["fg"],
                "selectbackground": c["accent"],
                "selectforeground": c["accent_fg"],
                "listbox_bg": c["bg_alt"],
                "listbox_fg": c["fg"],
                "listbox_select_bg": c["accent"],
                "listbox_select_fg": c["accent_fg"],
            }
        colors = dict(self._light_text)
        colors.setdefault("selectforeground", "black")
        colors["root_bg"] = self._light_root_bg
        colors.update({"listbox_bg": "white", "listbox_fg": "black",
                       "listbox_select_bg": "#0078d7",
                       "listbox_select_fg": "white"})
        return colors

    def _apply_polish(self):
        """Modernize the active theme + match table stripes to the mode."""
        dark = self._is_dark_mode()
        try:
            heading_font = tkfont.nametofont("TkDefaultFont").copy()
            heading_font.configure(weight="bold")
        except tk.TclError:
            heading_font = None
        stripes = polish_active_theme(self.style, dark, heading_font)
        try:
            self.tree.tag_configure("even", background=stripes[0])
            self.tree.tag_configure("odd", background=stripes[1])
        except tk.TclError:
            pass

    def toggle_theme(self):
        self._set_dark(self.theme_var.get())

    def _set_dark(self, on):
        on = bool(on)
        if self._bootstrap:
            self.style.theme_use(bootstrap_theme_name(self.style, on))
        elif on and self._dark_ttk_ok:
            self.style.theme_use(DARK_THEME_NAME)
        else:
            on = False
            self.style.theme_use(self._base_theme)
        self._apply_polish()
        colors = self._text_colors(on)
        self.configure(background=colors["root_bg"])
        self.log.configure(background=colors["background"],
                           foreground=colors["foreground"],
                           insertbackground=colors["insertbackground"],
                           selectbackground=colors["selectbackground"],
                           selectforeground=colors["selectforeground"])
        self.option_add("*TCombobox*Listbox.background", colors["listbox_bg"])
        self.option_add("*TCombobox*Listbox.foreground", colors["listbox_fg"])
        self.option_add("*TCombobox*Listbox.selectBackground",
                        colors["listbox_select_bg"])
        self.option_add("*TCombobox*Listbox.selectForeground",
                        colors["listbox_select_fg"])

    # -- catalog --------------------------------------------------------
    def load_catalog(self):
        if self.busy:
            return
        scope = self.scope_var.get()
        self.set_busy(True)
        self.status.set(f"Loading Flathub catalog (scope: {scope})...")
        self.tree.delete(*self.tree.get_children())
        self.row_by_iid.clear()

        def worker():
            cmd_preview = ["flatpak", *scope_args(scope), "remote-ls",
                           REMOTE, "--app", "--columns=application,name,description"]
            self.log_queue.put("Running: " + " ".join(cmd_preview))
            rows, err = load_catalog(scope)
            if err:
                self.log_queue.put("ERROR: " + err)
                self.after(0, lambda: [
                    self.set_busy(False),
                    self.status.set("Failed to load catalog. See log for details."),
                ])
                return
            installed, inst_errors = get_installed_union()
            for scope_name, scope_err in inst_errors.items():
                self.log_queue.put(f"Note: could not list {scope_name} apps: {scope_err}")
            nameless = sum(1 for app in rows if not app.name and not app.summary)
            self.all_rows = rows
            self.installed = installed

            def finish():
                self.set_busy(False)
                self.page = 0
                self.apply_filter()
                msg = (f"Loaded {len(rows)} apps (scope: {scope}); "
                       f"{len(installed)} installed detected. "
                       f"Browse with Prev/Next ({self.page_size_value} rows/page).")
                if nameless > len(rows) // 2:
                    msg += (" Names/summaries mostly empty — click "
                            "'Update' to fetch AppStream data.")
                self.status.set(msg)
                self.log_queue.put(
                    f"Catalog loaded: {len(rows)} apps; "
                    f"{len(installed)} installed known.")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def update_metadata(self):
        if self.busy:
            return
        scope = self.scope_var.get()
        self.set_busy(True)
        cmd = ["flatpak", *scope_args(scope), "update", "--appstream", REMOTE]
        self.status.set("Updating AppStream metadata...")
        self.log_queue.put("Running: " + " ".join(cmd))

        def worker():
            result = run_flatpak(cmd[1:], timeout=300)
            if result.stdout.strip():
                self.log_queue.put(result.stdout.strip())
            if result.returncode != 0:
                self.log_queue.put(
                    "Metadata update failed: " +
                    (result.stderr.strip() or "unknown error"))
                self.after(0, lambda: [
                    self.set_busy(False),
                    self.status.set("Metadata update failed. See log."),
                ])
                return
            self.log_queue.put("Metadata update finished. Reloading catalog...")
            self.after(0, lambda: [self.set_busy(False), self.load_catalog()])

        threading.Thread(target=worker, daemon=True).start()

    # -- filtering / selection / pagination ------------------------------
    def schedule_filter(self):
        if getattr(self, "_filter_job", None):
            self.after_cancel(self._filter_job)
        self.page = 0
        self._filter_job = self.after(250, self.apply_filter)

    def on_status_filter_change(self, event=None):
        self.page = 0
        self.apply_filter()

    def on_page_size_change(self, event=None):
        try:
            size = int(self.page_size_var.get())
        except ValueError:
            size = PAGE_SIZE
        self.page_size_value = max(1, size)
        self.page = 0
        self.apply_filter()

    def prev_page(self):
        if self.page > 0:
            self.page -= 1
            self.apply_filter()

    def next_page(self):
        self.page += 1
        self.apply_filter()

    def apply_filter(self):
        q = self.filter_var.get()
        filt = self.status_filter_var.get()
        matches = filter_rows(self.all_rows, q, self.installed, filt,
                              self.selected_ids)
        page_items, total_pages, self.page = paginate(
            matches, self.page, self.page_size_value)
        self.tree.delete(*self.tree.get_children())
        self.row_by_iid.clear()
        for index, app in enumerate(page_items):
            mark = CHECKED if app.app_id in self.selected_ids else UNCHECKED
            state = "Installed" if app.app_id in self.installed else ""
            iid = self.tree.insert("", "end", values=(
                mark, state, app.name, app.app_id, app.summary),
                tags=("even" if index % 2 == 0 else "odd",))
            self.row_by_iid[iid] = app.app_id
        self.update_count()
        self.update_pager(len(matches), total_pages)
        if not self.all_rows:
            self.status.set("Catalog is empty. Click 'Load catalog'.")
        elif not matches:
            self.status.set("No matches. Adjust filter or status view.")
        else:
            start = self.page * self.page_size_value + 1
            end = start + len(page_items) - 1
            self.status.set(
                f"Showing {start}–{end} of {len(matches)} match(es) "
                f"(page {self.page + 1}/{total_pages}). "
                "Click the ✓ column to select apps; "
                "selection is kept across pages.")

    def update_pager(self, total_matches, total_pages):
        if total_pages <= 1:
            self.page_label_var.set(
                f"{total_matches} match(es), single page.")
        else:
            self.page_label_var.set(
                f"Page {self.page + 1}/{total_pages} "
                f"({total_matches} match(es)).")
        self.prev_btn.state(["disabled"] if self.page <= 0 else ["!disabled"])
        self.next_btn.state(["disabled"] if self.page + 1 >= total_pages
                            else ["!disabled"])

    def toggle_id(self, app_id):
        if app_id in self.selected_ids:
            self.selected_ids.discard(app_id)
        else:
            self.selected_ids.add(app_id)
        self.refresh_marks()
        self.update_count()

    def refresh_marks(self):
        for iid, app_id in self.row_by_iid.items():
            mark = CHECKED if app_id in self.selected_ids else UNCHECKED
            vals = list(self.tree.item(iid, "values"))
            vals[0] = mark
            self.tree.item(iid, values=tuple(vals))

    def update_count(self):
        self.selected_count.set(f"Selected: {len(self.selected_ids)} apps")

    def on_tree_click(self, event):
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row or row not in self.row_by_iid:
            return
        if col == "#1":  # checkbox column
            self.toggle_id(self.row_by_iid[row])
            return "break"

    def on_space_toggle(self, event):
        for iid in self.tree.selection():
            if iid in self.row_by_iid:
                app_id = self.row_by_iid[iid]
                if app_id in self.selected_ids:
                    self.selected_ids.discard(app_id)
                else:
                    self.selected_ids.add(app_id)
        self.refresh_marks()
        self.update_count()
        return "break"

    def on_row_focus(self, event):
        sel = self.tree.selection()
        if not sel or sel[0] not in self.row_by_iid:
            return
        vals = self.tree.item(sel[0], "values")
        # values: sel, status, name, appid, summary
        self.detail.set(
            f"App ID: {vals[3]}  |  Name: {vals[2] or '(unknown)'}  |  "
            f"Status: {vals[1] or 'Not installed'}  |  Summary: {vals[4] or '(none)'}")

    def select_all_visible(self):
        """Select every app on the current page (selection persists across pages)."""
        for app_id in self.row_by_iid.values():
            self.selected_ids.add(app_id)
        self.refresh_marks()
        self.update_count()

    def clear_selection(self):
        self.selected_ids.clear()
        self.refresh_marks()
        self.update_count()

    # -- keyboard shortcuts ----------------------------------------------
    def _build_shortcuts(self):
        self.bind("<F1>", lambda e: self.show_help())
        self.bind("<F5>", lambda e: self.load_catalog())
        self.bind("<Control-f>", lambda e: self.focus_filter())
        self.bind("<Control-s>", lambda e: self.save_selection_dialog())
        self.bind("<Control-o>", lambda e: self.load_selection_dialog())
        self.bind("<Control-Return>", lambda e: self.install_selected())
        self.tree.bind("<Control-a>", self.on_select_all_key)
        self.filter_entry.bind("<Escape>", lambda e: self.clear_filter())

    def focus_filter(self):
        self.filter_entry.focus_set()
        self.filter_entry.select_range(0, "end")

    def clear_filter(self):
        self.filter_var.set("")
        self.page = 0
        self.apply_filter()
        self.tree.focus_set()

    def on_select_all_key(self, event):
        self.select_all_visible()
        return "break"

    # -- save / load -----------------------------------------------------
    def save_selection_dialog(self):
        if not self.selected_ids:
            messagebox.showinfo("Nothing to save", "No apps are selected.")
            return
        path = filedialog.asksaveasfilename(
            title="Save selected app IDs",
            initialfile="selected-apps.txt",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            save_selection(sorted(self.selected_ids), path)
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.status.set(f"Saved {len(self.selected_ids)} app ID(s) to {path}.")

    def load_selection_dialog(self):
        path = filedialog.askopenfilename(
            title="Load app ID list",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            ids = load_selection(path)
        except OSError as exc:
            messagebox.showerror("Load failed", str(exc))
            return
        known = {app.app_id for app in self.all_rows}
        unknown = [i for i in ids if known and i not in known]
        self.selected_ids.update(ids)
        self.refresh_marks()
        self.page = 0
        self.apply_filter()
        msg = f"Loaded {len(ids)} app ID(s) from file."
        if unknown:
            msg += f" {len(unknown)} not in current catalog view."
            self.log_queue.put("Unknown IDs from file: " + ", ".join(unknown[:20]))
        self.status.set(msg)

    # -- help, about, window icon --------------------------------------
    def _set_window_icon(self):
        icon = load_icon()
        if icon is not None:
            self._icon_refs.append(icon)
            try:
                self.iconphoto(True, icon)
            except tk.TclError:
                pass

    def _style_text_widget(self, widget):
        colors = self._text_colors(self._is_dark_mode())
        widget.configure(background=colors["background"],
                         foreground=colors["foreground"],
                         insertbackground=colors["insertbackground"],
                         selectbackground=colors["selectbackground"],
                         selectforeground=colors["selectforeground"])

    def _single_dialog(self, key, title, geometry):
        dlg = self._dialogs.get(key)
        if dlg is not None and dlg.winfo_exists():
            dlg.lift()
            dlg.focus_force()
            return None
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.geometry(geometry)
        dlg.transient(self)
        self._dialogs[key] = dlg
        return dlg

    def show_help(self):
        dlg = self._single_dialog("help", "How to use", "760x560")
        if dlg is None:
            return
        frame = ttk.Frame(dlg, padding=10)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word")
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.insert("1.0", USAGE_GUIDE)
        text.configure(state="disabled")
        self._style_text_widget(text)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Button(dlg, text="Close",
                   command=dlg.destroy).pack(pady=(0, 10))

    def show_about(self):
        dlg = self._single_dialog("about", "About", "480x420")
        if dlg is None:
            return
        frame = ttk.Frame(dlg, padding=16)
        frame.pack(fill="both", expand=True)
        icon = load_icon(subsample=4)  # 64px
        if icon is not None:
            self._icon_refs.append(icon)
            ttk.Label(frame, image=icon).pack(pady=(4, 8))
        title = ttk.Label(frame, text="Flatpak Batch Installer")
        title.pack()
        try:
            title.configure(font=("TkDefaultFont", 13, "bold"))
        except tk.TclError:
            pass
        ttk.Label(frame, text=f"Version {__version__}").pack(pady=(0, 8))
        body = tk.Text(frame, wrap="word", height=9, relief="flat",
                       highlightthickness=0)
        body.insert("1.0", about_text(__version__).split("\n", 2)[2])
        body.configure(state="disabled")
        self._style_text_widget(body)
        body.pack(fill="both", expand=True)
        ttk.Button(frame, text="Close",
                   command=dlg.destroy).pack(pady=(8, 0))

    # -- install ----------------------------------------------------------
    def install_selected(self):
        if self.busy:
            messagebox.showinfo("Please wait", "Another operation is running.")
            return
        ids = sorted(self.selected_ids)
        if not ids:
            self.status.set("No apps selected. Click the ✓ column first.")
            messagebox.showinfo(
                "No apps selected",
                "Select at least one app (click the ✓ column).")
            return
        scope = self.scope_var.get()
        already = [i for i in ids if i in self.installed]
        cmd = build_install_cmd(scope, REMOTE, ids)
        preview = "\n".join(ids)
        if not messagebox.askyesno(
                "Confirm install",
                f"Install {len(ids)} app(s) with scope '{scope}'?\n\n"
                f"{preview[:2000]}"
                + ("\n..." if len(preview) > 2000 else "")
                + (f"\n\nNote: {len(already)} already installed."
                   if already else "")):
            return
        self.set_busy(True)
        self.status.set(f"Installing {len(ids)} app(s)...")
        self.log_queue.put("Running: " + " ".join(cmd))

        def worker():
            exit_code = stream_command(cmd, self.log_queue.put)
            self.log_queue.put(f"Finished with exit code {exit_code}")
            installed, _ = get_installed_union()
            self.installed = installed

            def finish():
                self.set_busy(False)
                self.apply_filter()
                if exit_code == 0:
                    self.status.set(
                        f"Installed {len(ids)} app(s) successfully.")
                else:
                    self.status.set(
                        "Install command failed. See log. "
                        "Hint: try scope 'User' if permission was denied.")
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()


__all__ = ["FlathubBrowser"]
