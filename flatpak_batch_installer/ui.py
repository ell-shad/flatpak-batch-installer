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
    LIGHT_ACCENT,
    PAGE_SIZE,
    REMOTE,
    UNCHECKED,
)
from .flatpak import (
    build_install_cmd,
    build_uninstall_cmd,
    get_installed_union,
    get_installed_details,
    load_catalog,
    run_flatpak,
    run_update_all,
    scope_args,
)
from .installer import stream_command
from .helptext import SHORTCUTS, USAGE_GUIDE, about_text, shortcuts_text
from .resources import load_icon
from .theme import (
    BOOTSTRAP_AVAILABLE,
    bootstrap_theme_name,
    create_style,
    dark_theme_settings,
    is_bootstrap,
    polish_active_theme,
    stripe_colors,
    system_prefers_dark,
)


class _ToolTip:
    """Lightweight tooltip: appears after a short hover, disappears on leave."""

    _DELAY_MS = 700

    def __init__(self, widget, text: str):
        self._widget = widget
        self._text = text
        self._tip_window = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._cancel, add="+")
        widget.bind("<ButtonPress>", self._cancel, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._after_id = self._widget.after(self._DELAY_MS, self._show)

    def _cancel(self, _event=None):
        if self._after_id is not None:
            self._widget.after_cancel(self._after_id)
            self._after_id = None
        if self._tip_window is not None:
            try:
                self._tip_window.destroy()
            except tk.TclError:
                pass
            self._tip_window = None

    def _show(self):
        if self._tip_window is not None:
            return
        try:
            x = self._widget.winfo_rootx() + 20
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + 2
            tw = tk.Toplevel(self._widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            lbl = tk.Label(tw, text=self._text, justify="left",
                           background="#ffffe0", foreground="#333333",
                           relief="solid", borderwidth=1,
                           font=("TkDefaultFont", 9))
            lbl.pack(ipadx=4, ipady=2)
            self._tip_window = tw
        except tk.TclError:
            pass


class FlathubBrowser(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Flatpak Batch Installer")
        self.geometry("1200x740")

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
        self.category_var = tk.StringVar(value="All")
        self.selected_count = tk.StringVar(value="Selected: 0 apps")
        self.theme_var = tk.BooleanVar(value=False)
        self.page_label_var = tk.StringVar(value="No catalog loaded.")
        self.busy_label_var = tk.StringVar(value="")
        self.total_var = tk.StringVar(value="Total: 0 apps")
        self.scope_badge_var = tk.StringVar(value=f"Scope: {DEFAULT_SCOPE}")
        self.status = tk.StringVar(
            value="Click Refresh to load the catalog. Click the ✓ column to select apps.")

        self.style = create_style(self)
        self._base_theme = self.style.theme_use()
        self._dark_ttk_ok = False
        self._bootstrap = is_bootstrap(self.style)
        self._dialogs = {}
        self._dialog_texts = {}
        self._shortcut_tree = None
        self._icon_refs = []
        self._alive = True
        self._filter_job = None
        self._search_history: list[str] = []
        self._tooltip_widgets: list[_ToolTip] = []
        # Installed tab state
        self.installed_rows: list[dict] = []
        self.installed_tab_selected: set[str] = set()
        self._installed_tab_loaded: bool = False
        self._installed_row_by_iid: dict[str, str] = {}  # iid -> app_id

        self._build_widgets()
        self._init_theme()
        self._set_window_icon()
        self._build_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self.poll_log)

    # -----------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------
    def _build_widgets(self):
        # ── Header bar ──────────────────────────────────────────────────────
        header = ttk.Frame(self, padding=(8, 6, 8, 6))
        header.pack(fill="x")

        # Left: icon + title
        icon = load_icon(subsample=8)  # ~32px
        if icon is not None:
            self._icon_refs.append(icon)
            ttk.Label(header, image=icon).pack(side="left", padx=(0, 6))
        try:
            title_font = tkfont.nametofont("TkDefaultFont").copy()
            title_font.configure(size=title_font["size"] + 2, weight="bold")
        except tk.TclError:
            title_font = "TkDefaultFont"
        ttk.Label(header, text="Flatpak Batch Installer",
                  font=title_font).pack(side="left")

        # Right: action buttons and menus
        help_btn = ttk.Menubutton(header, text="Help")
        help_menu = tk.Menu(help_btn, tearoff=0)
        help_menu.add_command(label="How to use…", accelerator="F1",
                              command=self.show_help)
        help_menu.add_command(label="Keyboard shortcuts…", accelerator="Ctrl+K",
                              command=self.show_shortcuts)
        help_menu.add_separator()
        help_menu.add_command(label="About…", command=self.show_about)
        help_btn.configure(menu=help_menu)
        help_btn.pack(side="right", padx=(4, 0))
        self._help_menu = help_menu

        options_btn = ttk.Menubutton(header, text="Options")
        options_menu = tk.Menu(options_btn, tearoff=0)
        options_menu.add_radiobutton(label="Scope: User (recommended)",
                                     variable=self.scope_var, value="user",
                                     command=self._on_scope_change)
        options_menu.add_radiobutton(label="Scope: System",
                                     variable=self.scope_var, value="system",
                                     command=self._on_scope_change)
        options_menu.add_separator()
        options_menu.add_command(label="Update metadata…",
                                 command=self.update_metadata)
        options_menu.add_separator()
        options_menu.add_command(label="Save selection…", accelerator="Ctrl+S",
                                 command=self.save_selection_dialog)
        options_menu.add_command(label="Load selection…", accelerator="Ctrl+O",
                                 command=self.load_selection_dialog)
        options_menu.add_separator()
        options_menu.add_checkbutton(label="Dark mode",
                                     variable=self.theme_var,
                                     command=self.toggle_theme)
        options_btn.configure(menu=options_menu)
        options_btn.pack(side="right", padx=(4, 0))
        self._options_menu = options_menu

        refresh_btn = ttk.Button(header, text="Refresh",
                                 command=self.load_catalog)
        refresh_btn.pack(side="right", padx=(4, 0))

        update_btn = ttk.Button(header, text="Update All",
                                command=self._update_all)
        update_btn.pack(side="right", padx=(4, 0))

        self.install_btn = ttk.Button(header, text="Install",
                                      style="Accent.TButton",
                                      command=self.install_selected)
        self.install_btn.pack(side="right", padx=(4, 0))

        # Add tooltips for header buttons
        self._add_tooltip(self.install_btn,
                          "Install the selected apps (Ctrl+Enter)")
        self._add_tooltip(update_btn,
                          "Update all installed Flatpak apps (streams output)")
        self._add_tooltip(refresh_btn,
                          "Reload the Flathub catalog (F5)")
        self._add_tooltip(options_btn,
                          "Scope, metadata update, save/load, dark mode")
        self._add_tooltip(help_btn,
                          "Usage guide, keyboard shortcuts, about")

        # ── Notebook: Browse Catalog / Installed Apps ───────────────────────
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=0, pady=0)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # ── Tab 1: Browse Catalog ───────────────────────────────────────────
        browse_tab = ttk.Frame(self.notebook)
        self.notebook.add(browse_tab, text="Browse Catalog")

        # ── Horizontal split: sidebar + content ────────────────────────────
        paned = ttk.PanedWindow(browse_tab, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=0, pady=0)

        # ── Left sidebar ────────────────────────────────────────────────────
        sidebar = ttk.Frame(paned, padding=(6, 6, 6, 6))
        paned.add(sidebar, weight=0)
        # Fix sidebar width
        sidebar.pack_propagate(False)
        sidebar.configure(width=224)

        ttk.Label(sidebar, text="Search").pack(anchor="w", pady=(0, 2))
        self.filter_entry = ttk.Combobox(sidebar, textvariable=self.filter_var,
                                         width=22, state="normal")
        self.filter_entry.pack(fill="x")
        self.filter_entry.bind("<KeyRelease>", lambda e: self.schedule_filter())
        self.filter_entry.bind("<<ComboboxSelected>>",
                               lambda e: self.schedule_filter())
        self.filter_entry.bind("<Escape>", lambda e: self.clear_filter())

        clear_btn = ttk.Button(sidebar, text="Clear ✕",
                               command=self.clear_filter)
        clear_btn.pack(fill="x", pady=(4, 0))
        self._add_tooltip(self.filter_entry,
                          "Search app name, ID and summary (Ctrl+F)")
        self._add_tooltip(clear_btn, "Clear the search filter (Esc)")

        ttk.Separator(sidebar, orient="horizontal").pack(
            fill="x", pady=(8, 6))

        ttk.Label(sidebar, text="Status").pack(anchor="w", pady=(0, 2))
        status_cb = ttk.Combobox(
            sidebar, textvariable=self.status_filter_var, width=22,
            state="readonly",
            values=["all", "installed", "not-installed", "selected"])
        status_cb.pack(fill="x")
        status_cb.bind("<<ComboboxSelected>>", self.on_status_filter_change)
        self._add_tooltip(status_cb,
                          "Filter by install status or selection")

        ttk.Label(sidebar, text="Category").pack(
            anchor="w", pady=(8, 2))
        self.category_cb = ttk.Combobox(
            sidebar, textvariable=self.category_var, width=22,
            state="readonly", values=["All"])
        self.category_cb.pack(fill="x")
        self.category_cb.bind(
            "<<ComboboxSelected>>",
            lambda e: (setattr(self, "page", 0), self.apply_filter()))
        self._add_tooltip(self.category_cb,
                          "Filter apps by category")

        ttk.Separator(sidebar, orient="horizontal").pack(
            fill="x", pady=(8, 6))

        ttk.Label(sidebar, text="Scope").pack(anchor="w", pady=(0, 2))
        scope_user = ttk.Radiobutton(sidebar, text="User (recommended)",
                                     variable=self.scope_var, value="user",
                                     command=self._on_scope_change)
        scope_user.pack(anchor="w")
        scope_sys = ttk.Radiobutton(sidebar, text="System",
                                    variable=self.scope_var, value="system",
                                    command=self._on_scope_change)
        scope_sys.pack(anchor="w")
        self._add_tooltip(scope_user,
                          "Install for current user only (no root needed)")
        self._add_tooltip(scope_sys,
                          "Install system-wide (may require root)")

        ttk.Separator(sidebar, orient="horizontal").pack(
            fill="x", pady=(8, 6))

        select_page_btn = ttk.Button(sidebar, text="Select Page",
                                     command=self.select_all_visible)
        select_page_btn.pack(fill="x")
        self._add_tooltip(select_page_btn,
                          "Select every app on the current page (Ctrl+A)")

        clear_sel_btn = ttk.Button(sidebar, text="Clear  (Ctrl+D)",
                                   command=self.clear_selection)
        clear_sel_btn.pack(fill="x", pady=(4, 0))
        self._add_tooltip(clear_sel_btn,
                          "Deselect all apps (Ctrl+D)")

        select_cat_btn = ttk.Button(sidebar, text="Select All in Category",
                                    command=self._select_by_category)
        select_cat_btn.pack(fill="x", pady=(4, 0))
        self._add_tooltip(select_cat_btn,
                          "Select all apps in the current category")

        # Keep sidebar references for theme recoloring
        self._sidebar_frame = sidebar

        # ── Right content pane ──────────────────────────────────────────────
        right_pane = ttk.Frame(paned, padding=(0, 4, 4, 0))
        paned.add(right_pane, weight=1)

        columns = ("sel", "status", "name", "appid", "summary")
        self.tree = ttk.Treeview(right_pane, columns=columns,
                                 show="headings", selectmode="extended")
        self.tree.heading("sel", text="✓")
        self.tree.heading("status", text="Status")
        self.tree.heading("name", text="Name")
        self.tree.heading("appid", text="App ID")
        self.tree.heading("summary", text="Summary")
        self.tree.column("sel", width=36, anchor="center", stretch=False)
        self.tree.column("status", width=100, anchor="w", stretch=False)
        self.tree.column("name", width=210, anchor="w")
        self.tree.column("appid", width=270, anchor="w")
        self.tree.column("summary", width=430, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=(4, 0))
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<space>", self.on_space_toggle)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_focus)

        # Pager
        pager = ttk.Frame(right_pane, padding=(4, 2, 0, 0))
        pager.pack(fill="x")
        self.prev_btn = ttk.Button(pager, text="< Prev",
                                   command=self.prev_page)
        self.prev_btn.pack(side="left")
        self.next_btn = ttk.Button(pager, text="Next >",
                                   command=self.next_page)
        self.next_btn.pack(side="left", padx=6)
        ttk.Label(pager, textvariable=self.page_label_var).pack(
            side="left", padx=6)
        ttk.Label(pager, text="Rows/page:").pack(side="left", padx=(8, 4))
        self.page_size_var = tk.StringVar(value=str(PAGE_SIZE))
        page_size_cb = ttk.Combobox(pager, textvariable=self.page_size_var,
                                    width=5, state="readonly",
                                    values=["100", "200", "500"])
        page_size_cb.pack(side="left")
        page_size_cb.bind("<<ComboboxSelected>>", self.on_page_size_change)
        self._add_tooltip(self.prev_btn, "Go to previous page")
        self._add_tooltip(self.next_btn, "Go to next page")
        self._add_tooltip(page_size_cb, "Number of rows shown per page")

        # Detail panel
        self._detail_panel = ttk.Frame(right_pane, padding=(4, 4, 0, 2))
        self._detail_panel.pack(fill="x")
        self._detail_panel_visible = False

        try:
            name_font = tkfont.nametofont("TkDefaultFont").copy()
            name_font.configure(weight="bold",
                                size=name_font["size"] + 1)
        except tk.TclError:
            name_font = "TkDefaultFont"
        try:
            mono_font = tkfont.nametofont("TkFixedFont")
        except tk.TclError:
            mono_font = "TkFixedFont"

        self.detail_name_var = tk.StringVar(value="")
        self.detail_id_var = tk.StringVar(value="")
        self.detail_status_var = tk.StringVar(value="")
        self.detail_name_lbl = ttk.Label(
            self._detail_panel, textvariable=self.detail_name_var,
            font=name_font, anchor="w")
        self.detail_name_lbl.pack(fill="x")
        self.detail_id_lbl = ttk.Label(
            self._detail_panel, textvariable=self.detail_id_var,
            font=mono_font, anchor="w")
        self.detail_id_lbl.pack(fill="x")
        self.detail_status_lbl = ttk.Label(
            self._detail_panel, textvariable=self.detail_status_var,
            anchor="w")
        self.detail_status_lbl.pack(fill="x")
        self.detail_summary_text = tk.Text(
            self._detail_panel, height=2, wrap="word", state="disabled",
            relief="flat", highlightthickness=0)
        self.detail_summary_text.pack(fill="x")
        # Start hidden
        self._detail_panel.pack_forget()

        # Log area with toggle
        log_toggle_bar = ttk.Frame(right_pane)
        log_toggle_bar.pack(fill="x", padx=(4, 0), pady=(2, 0))
        ttk.Label(log_toggle_bar, text="Log").pack(side="left")
        self._log_visible = True
        self._log_toggle_btn = ttk.Button(log_toggle_bar, text="Hide",
                                          command=self._toggle_log)
        self._log_toggle_btn.pack(side="left", padx=(6, 0))

        self.log = tk.Text(right_pane, height=7, wrap="word",
                           state="disabled")
        self.log.pack(fill="x", padx=(4, 0), pady=(0, 4))

        # Per-app install progress panel (initially hidden)
        self.progress_panel = ttk.Frame(right_pane, padding=(4, 2, 0, 2))
        self.progress_panel.pack(fill="x", padx=(4, 0))
        self.progress_panel.pack_forget()

        progress_columns = ("app_id", "install_status")
        self._progress_tree = ttk.Treeview(
            self.progress_panel, columns=progress_columns,
            show="headings", height=5)
        self._progress_tree.heading("app_id", text="App ID")
        self._progress_tree.heading("install_status", text="Status")
        self._progress_tree.column("app_id", width=320, anchor="w")
        self._progress_tree.column("install_status", width=120, anchor="w")
        self._progress_tree.pack(fill="x")
        # Tags for status colors
        self._progress_tree.tag_configure("queued", foreground="")
        self._progress_tree.tag_configure("installing", foreground="#0b5ed7")
        self._progress_tree.tag_configure("done", foreground="#198754")
        self._progress_tree.tag_configure("failed", foreground="#dc3545")

        # ── Persistent 4-segment status bar ────────────────────────────────
        statusbar = ttk.Frame(self, padding=(6, 2, 6, 3))
        statusbar.pack(fill="x", side="bottom")

        ttk.Label(statusbar, textvariable=self.total_var,
                  anchor="w").pack(side="left")
        ttk.Separator(statusbar, orient="vertical").pack(
            side="left", fill="y", padx=6)
        ttk.Label(statusbar, textvariable=self.selected_count,
                  anchor="w").pack(side="left")
        ttk.Separator(statusbar, orient="vertical").pack(
            side="left", fill="y", padx=6)
        ttk.Label(statusbar, textvariable=self.scope_badge_var,
                  anchor="w").pack(side="left")
        ttk.Separator(statusbar, orient="vertical").pack(
            side="left", fill="y", padx=6)
        ttk.Label(statusbar, textvariable=self.busy_label_var).pack(
            side="right")
        self.progress = ttk.Progressbar(statusbar, mode="indeterminate",
                                        length=100)
        self.progress.pack(side="right", padx=(0, 4))
        ttk.Label(statusbar, textvariable=self.status, anchor="w",
                  wraplength=700).pack(side="left", fill="x", expand=True)

        # ── Tab 2: Installed Apps ───────────────────────────────────────────
        installed_tab = ttk.Frame(self.notebook)
        self.notebook.add(installed_tab, text="Installed Apps")
        self._build_installed_tab(installed_tab)

    # -- add tooltip helper -------------------------------------------------
    def _add_tooltip(self, widget, text: str):
        self._tooltip_widgets.append(_ToolTip(widget, text))

    # -- log toggle ---------------------------------------------------------
    def _toggle_log(self):
        if self._log_visible:
            self.log.pack_forget()
            self._log_toggle_btn.configure(text="Show Log")
            self._log_visible = False
        else:
            self.log.pack(fill="x", padx=(4, 0), pady=(0, 4))
            self._log_toggle_btn.configure(text="Hide")
            self._log_visible = True

    # -- Installed Apps tab ------------------------------------------------
    def _build_installed_tab(self, parent: ttk.Frame):
        """Build all widgets inside the Installed Apps tab."""
        # Toolbar row
        toolbar = ttk.Frame(parent, padding=(4, 4, 4, 2))
        toolbar.pack(fill="x")

        refresh_inst_btn = ttk.Button(toolbar, text="Refresh Installed",
                                      command=self._load_installed_tab)
        refresh_inst_btn.pack(side="left", padx=(0, 4))
        self._add_tooltip(refresh_inst_btn, "Reload the list of installed apps")

        uninstall_btn = ttk.Button(toolbar, text="Uninstall Selected",
                                   style="Danger.TButton",
                                   command=self._uninstall_selected)
        uninstall_btn.pack(side="left", padx=(0, 8))
        self._add_tooltip(uninstall_btn,
                          "Uninstall the checked apps (asks for confirmation)")

        # Scope radios (shared self.scope_var)
        ttk.Radiobutton(toolbar, text="User", variable=self.scope_var,
                        value="user",
                        command=self._on_scope_change).pack(side="left")
        ttk.Radiobutton(toolbar, text="System", variable=self.scope_var,
                        value="system",
                        command=self._on_scope_change).pack(side="left",
                                                             padx=(4, 0))

        self._installed_count_var = tk.StringVar(value="Selected: 0")
        ttk.Label(toolbar, textvariable=self._installed_count_var).pack(
            side="left", padx=(12, 0))

        # Treeview
        columns = ("sel", "app_id", "name", "version", "origin")
        self._installed_tree = ttk.Treeview(parent, columns=columns,
                                             show="headings",
                                             selectmode="extended")
        self._installed_tree.heading("sel", text="✓")
        self._installed_tree.heading("app_id", text="App ID")
        self._installed_tree.heading("name", text="Name")
        self._installed_tree.heading("version", text="Version")
        self._installed_tree.heading("origin", text="Origin")
        self._installed_tree.column("sel", width=36, anchor="center",
                                     stretch=False)
        self._installed_tree.column("app_id", width=280, anchor="w")
        self._installed_tree.column("name", width=200, anchor="w")
        self._installed_tree.column("version", width=100, anchor="w")
        self._installed_tree.column("origin", width=120, anchor="w")
        inst_scroll = ttk.Scrollbar(parent,
                                    command=self._installed_tree.yview)
        self._installed_tree.configure(
            yscrollcommand=inst_scroll.set)
        self._installed_tree.pack(fill="both", expand=True,
                                   side="left", padx=(4, 0), pady=(0, 4))
        inst_scroll.pack(fill="y", side="right", pady=(0, 4))

        self._installed_tree.tag_configure("even", background="")
        self._installed_tree.tag_configure("odd", background="")
        self._installed_tree.bind("<Button-1>", self._on_installed_click)

        # Footer label
        self._installed_status_var = tk.StringVar(
            value="Switch to this tab to load installed apps.")
        ttk.Label(parent, textvariable=self._installed_status_var,
                  anchor="w").pack(fill="x", side="bottom",
                                    padx=4, pady=(0, 2))

    def _on_tab_changed(self, event=None):
        """Lazy-load the Installed Apps tab on first switch."""
        try:
            idx = self.notebook.index(self.notebook.select())
        except tk.TclError:
            return
        if idx == 1 and not self._installed_tab_loaded:
            self._load_installed_tab()

    def _load_installed_tab(self):
        """Load installed apps from both scopes in a background thread."""
        if self.busy:
            return
        self.set_busy(True)
        self._installed_status_var.set("Loading installed apps…")

        def worker():
            all_rows: list[dict] = []
            for s in ("user", "system"):
                rows, err = get_installed_details(s)
                if err:
                    self.log_queue.put(
                        f"Note: could not list {s} installed apps: {err}")
                else:
                    # Tag each row with the scope it came from
                    for r in rows:
                        r = dict(r)
                        r["scope"] = s
                        all_rows.append(r)
            self.installed_rows = all_rows

            def finish():
                if not self._alive:
                    return
                self.set_busy(False)
                self._installed_tab_loaded = True
                self._installed_row_by_iid.clear()
                self.installed_tab_selected.clear()
                for child in self._installed_tree.get_children():
                    self._installed_tree.delete(child)
                for index, row in enumerate(all_rows):
                    iid = self._installed_tree.insert(
                        "", "end",
                        values=(
                            UNCHECKED,
                            row.get("app_id", ""),
                            row.get("name", ""),
                            row.get("version", ""),
                            row.get("origin", ""),
                        ),
                        tags=("even" if index % 2 == 0 else "odd",),
                    )
                    self._installed_row_by_iid[iid] = row.get("app_id", "")
                self._installed_status_var.set(
                    f"Showing {len(all_rows)} installed app(s).")
                self._update_installed_count()
                # Keep the browse-tab installed set in sync
                self.installed = {r["app_id"] for r in all_rows
                                  if r.get("app_id")}
                self.apply_filter()

            if not self._alive:
                return
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _on_installed_click(self, event):
        """Toggle checkbox column click in the installed Treeview."""
        row = self._installed_tree.identify_row(event.y)
        col = self._installed_tree.identify_column(event.x)
        if not row or row not in self._installed_row_by_iid:
            return
        if col == "#1":
            app_id = self._installed_row_by_iid[row]
            if app_id in self.installed_tab_selected:
                self.installed_tab_selected.discard(app_id)
            else:
                self.installed_tab_selected.add(app_id)
            # Update checkbox value
            vals = list(self._installed_tree.item(row, "values"))
            vals[0] = (CHECKED if app_id in self.installed_tab_selected
                       else UNCHECKED)
            self._installed_tree.item(row, values=tuple(vals))
            self._update_installed_count()
            return "break"

    def _update_installed_count(self):
        n = len(self.installed_tab_selected)
        self._installed_count_var.set(f"Selected: {n}")

    def _uninstall_selected(self):
        """Uninstall the apps checked in the Installed tab."""
        if self.busy:
            messagebox.showinfo("Please wait", "Another operation is running.")
            return
        ids = sorted(self.installed_tab_selected)
        if not ids:
            messagebox.showinfo("Nothing selected",
                                "Check at least one app in the list.")
            return
        scope = self.scope_var.get()
        preview = "\n".join(ids)
        if not messagebox.askyesno(
                "Confirm uninstall",
                f"Uninstall {len(ids)} app(s) with scope '{scope}'?\n\n"
                f"{preview[:2000]}"
                + ("\n..." if len(preview) > 2000 else "")):
            return
        cmd = build_uninstall_cmd(scope, ids)
        self.set_busy(True)
        self.status.set(f"Uninstalling {len(ids)} app(s)…")
        self.log_queue.put("Running: " + " ".join(cmd))

        def worker():
            from .installer import stream_command
            exit_code = stream_command(cmd, self.log_queue.put, timeout=300)
            self.log_queue.put(f"Uninstall finished with exit code {exit_code}")

            def finish():
                if not self._alive:
                    return
                self.set_busy(False)
                self.installed_tab_selected.clear()
                self._installed_tab_loaded = False  # force reload
                self._load_installed_tab()
                if exit_code == 0:
                    self.status.set(
                        f"Uninstalled {len(ids)} app(s) successfully.")
                else:
                    self.status.set("Uninstall command failed. See log.")

            if not self._alive:
                return
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _update_all(self):
        """Update all installed Flatpak apps (streaming)."""
        if self.busy:
            messagebox.showinfo("Please wait", "Another operation is running.")
            return
        scope = self.scope_var.get()
        if not messagebox.askyesno(
                "Confirm update",
                f"Update all installed Flatpak apps for scope '{scope}'?\n"
                "This may take several minutes."):
            return
        self.set_busy(True)
        self.status.set(f"Updating all installed apps (scope: {scope})…")
        self.log_queue.put(
            f"Running: flatpak --{scope} update --noninteractive --assumeyes")

        def worker():
            exit_code = run_update_all(scope, self.log_queue.put)
            self.log_queue.put(f"Update finished with exit code {exit_code}")
            # Refresh installed set
            installed, _ = get_installed_union()

            def finish():
                if not self._alive:
                    return
                self.set_busy(False)
                self.installed = installed
                self._installed_tab_loaded = False
                self._load_installed_tab()
                if exit_code == 0:
                    self.status.set("All apps updated successfully.")
                else:
                    self.status.set("Update command failed. See log.")

            if not self._alive:
                return
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    # -- select by category -------------------------------------------------
    def _select_by_category(self):
        """Add all apps in the current category to selected_ids."""
        cat = self.category_var.get()
        if cat == "All":
            messagebox.showinfo("Select by category",
                                "Choose a specific category first.")
            return
        matches = filter_rows(self.all_rows, "", self.installed, "all",
                              category=cat)
        for app in matches:
            self.selected_ids.add(app.app_id)
        self.refresh_marks()
        self.update_count()

    # -- window close -------------------------------------------------------
    def _on_close(self):
        self._alive = False
        self.destroy()

    # -- scope change -------------------------------------------------------
    def _on_scope_change(self):
        self.scope_badge_var.set(f"Scope: {self.scope_var.get()}")
        self.load_catalog()

    # -- logging / status --------------------------------------------------
    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def poll_log(self):
        try:
            while True:
                try:
                    self.append_log(self.log_queue.get_nowait())
                except tk.TclError:
                    return
        except queue.Empty:
            pass
        if self._alive:
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
        # Larger row height for the modern look
        self.style.configure("Treeview", rowheight=44)
        try:
            self.tree.tag_configure("even", background=stripes[0])
            self.tree.tag_configure("odd", background=stripes[1])
            # Muted foreground tag for summary column effect
            muted_fg = (DARK_COLORS["fg_dim"] if dark else "#6c757d")
            self.tree.tag_configure("summary_muted", foreground=muted_fg)
            if self._shortcut_tree is not None \
                    and self._shortcut_tree.winfo_exists():
                self._shortcut_tree.tag_configure("even",
                                                  background=stripes[0])
                self._shortcut_tree.tag_configure("odd",
                                                  background=stripes[1])
            # Also stripe the installed apps tree
            try:
                self._installed_tree.tag_configure("even",
                                                   background=stripes[0])
                self._installed_tree.tag_configure("odd",
                                                   background=stripes[1])
            except (AttributeError, tk.TclError):
                pass
        except tk.TclError:
            pass
        self._recolor_sidebar(dark)

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
        # Also recolor the detail summary text widget
        try:
            self.detail_summary_text.configure(
                background=colors["background"],
                foreground=colors["foreground"],
                insertbackground=colors["insertbackground"],
                selectbackground=colors["selectbackground"],
                selectforeground=colors["selectforeground"])
        except tk.TclError:
            pass
        self.option_add("*TCombobox*Listbox.background", colors["listbox_bg"])
        self.option_add("*TCombobox*Listbox.foreground", colors["listbox_fg"])
        self.option_add("*TCombobox*Listbox.selectBackground",
                        colors["listbox_select_bg"])
        self.option_add("*TCombobox*Listbox.selectForeground",
                        colors["listbox_select_fg"])

    def _recolor_sidebar(self, on):
        """Re-apply background/foreground to sidebar widgets after theme switch."""
        # Only needed for plain ttk (bootstrap handles it natively)
        if self._bootstrap:
            return
        colors = self._text_colors(on)
        bg = colors["root_bg"]
        fg = colors["foreground"]
        try:
            for widget in self._sidebar_frame.winfo_children():
                cls = widget.winfo_class()
                if cls in ("TFrame", "Frame"):
                    widget.configure(style="TFrame")
                elif cls in ("TLabel", "Label"):
                    try:
                        widget.configure(background=bg, foreground=fg)
                    except tk.TclError:
                        pass
        except tk.TclError:
            pass

    # -- catalog -----------------------------------------------------------
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
                if not self._alive:
                    return
                self.after(0, lambda: [
                    self.set_busy(False),
                    self.status.set("Failed to load catalog. See log for details."),
                ])
                return
            installed, inst_errors = get_installed_union()
            for scope_name, scope_err in inst_errors.items():
                self.log_queue.put(
                    f"Note: could not list {scope_name} apps: {scope_err}")
            nameless = sum(1 for app in rows if not app.name and not app.summary)
            self.all_rows = rows
            self.installed = installed

            def finish():
                self.set_busy(False)
                self.page = 0
                # Populate category combobox
                cats = ["All"] + sorted(
                    {app.category for app in self.all_rows} - {""})
                self.category_cb.configure(values=cats)
                self.category_var.set("All")
                self.apply_filter()
                msg = (f"Loaded {len(rows)} apps (scope: {scope}); "
                       f"{len(installed)} installed detected. "
                       f"Browse with Prev/Next "
                       f"({self.page_size_value} rows/page).")
                if nameless > len(rows) // 2:
                    msg += (" Names/summaries mostly empty — click "
                            "'Update All' to fetch AppStream data.")
                self.status.set(msg)
                self.log_queue.put(
                    f"Catalog loaded: {len(rows)} apps; "
                    f"{len(installed)} installed known.")

            if not self._alive:
                return
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def update_metadata(self):
        if self.busy:
            return
        scope = self.scope_var.get()
        self.set_busy(True)
        update_args = [*scope_args(scope), "update", "--appstream", REMOTE]
        self.status.set("Updating AppStream metadata...")
        self.log_queue.put("Running: flatpak " + " ".join(update_args))

        def worker():
            result = run_flatpak(update_args, timeout=300)
            if result.stdout.strip():
                self.log_queue.put(result.stdout.strip())
            if result.returncode != 0:
                self.log_queue.put(
                    "Metadata update failed: " +
                    (result.stderr.strip() or "unknown error"))
                if not self._alive:
                    return
                self.after(0, lambda: [
                    self.set_busy(False),
                    self.status.set("Metadata update failed. See log."),
                ])
                return
            self.log_queue.put("Metadata update finished. Reloading catalog...")
            if not self._alive:
                return
            self.after(0, lambda: [self.set_busy(False), self.load_catalog()])

        threading.Thread(target=worker, daemon=True).start()

    # -- filtering / selection / pagination --------------------------------
    def schedule_filter(self):
        if self._filter_job:
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
        cat_val = self.category_var.get()
        cat = None if cat_val == "All" else cat_val
        matches = filter_rows(self.all_rows, q, self.installed, filt,
                              self.selected_ids, category=cat)
        page_items, total_pages, self.page = paginate(
            matches, self.page, self.page_size_value)
        self.tree.delete(*self.tree.get_children())
        self.row_by_iid.clear()

        if not self.all_rows:
            # Empty state: no catalog loaded
            iid = self.tree.insert("", "end",
                                   values=("", "", "No catalog loaded",
                                           "Click Refresh to load", ""),
                                   tags=("placeholder",))
            self.tree.tag_configure("placeholder", foreground="#9a9a9a")
        elif not page_items:
            # Empty state: no matches
            if not matches:
                iid = self.tree.insert(
                    "", "end",
                    values=("", "", "No results",
                            "Try a different search term or filter", ""),
                    tags=("placeholder",))
                self.tree.tag_configure("placeholder", foreground="#9a9a9a")
        else:
            for index, app in enumerate(page_items):
                mark = CHECKED if app.app_id in self.selected_ids else UNCHECKED
                state = "Installed" if app.app_id in self.installed else ""
                iid = self.tree.insert("", "end", values=(
                    mark, state, app.name, app.app_id, app.summary),
                    tags=("even" if index % 2 == 0 else "odd",))
                self.row_by_iid[iid] = app.app_id

        # Update search history
        term = q.strip()
        if term and matches and term not in self._search_history:
            self._search_history.insert(0, term)
            self._search_history = self._search_history[:5]
            self.filter_entry.configure(values=self._search_history)

        # Update total count
        self.total_var.set(f"Total: {len(self.all_rows)} apps")

        self.update_count()
        self.update_pager(len(matches), total_pages)

        if not self.all_rows:
            self.status.set("Catalog is empty. Click Refresh.")
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
        n = len(self.selected_ids)
        self.selected_count.set(f"Selected: {n} apps")
        self._update_install_btn_label()

    def _update_install_btn_label(self):
        n = len(self.selected_ids)
        self.install_btn.configure(
            text=f"Install ({n})" if n > 0 else "Install")

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
        app_name = vals[2] or "(unknown)"
        app_id = vals[3]
        status_txt = vals[1] or "Not installed"
        summary_txt = vals[4] or ""

        self.detail_name_var.set(app_name)
        self.detail_id_var.set(app_id)
        self.detail_status_var.set(f"Status: {status_txt}")
        self.detail_summary_text.configure(state="normal")
        self.detail_summary_text.delete("1.0", "end")
        self.detail_summary_text.insert("1.0", summary_txt)
        self.detail_summary_text.configure(state="disabled")

        if not self._detail_panel_visible:
            self._detail_panel.pack(fill="x", before=self.log.master
                                    if False else self._detail_panel)
            self._detail_panel.pack(fill="x")
            self._detail_panel_visible = True

    def select_all_visible(self):
        """Select every app on the current page."""
        for app_id in self.row_by_iid.values():
            self.selected_ids.add(app_id)
        self.refresh_marks()
        self.update_count()

    def clear_selection(self):
        self.selected_ids.clear()
        self.refresh_marks()
        self.update_count()

    # -- keyboard shortcuts ------------------------------------------------
    def _build_shortcuts(self):
        self.bind("<F1>", lambda e: self.show_help())
        self.bind("<F5>", lambda e: self.load_catalog())
        self.bind("<Control-f>", lambda e: self.focus_filter())
        self.bind("<Control-s>", lambda e: self.save_selection_dialog())
        self.bind("<Control-o>", lambda e: self.load_selection_dialog())
        self.bind("<Control-Return>", lambda e: self.install_selected())
        self.bind("<Control-k>", lambda e: self.show_shortcuts())
        self.bind("<Control-d>", lambda e: self.clear_selection())
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

    # -- save / load -------------------------------------------------------
    def save_selection_dialog(self):
        if not self.selected_ids:
            messagebox.showinfo("Nothing to save", "No apps are selected.")
            return
        path = filedialog.asksaveasfilename(
            title="Save selected app IDs",
            initialfile="selected-apps.txt",
            defaultextension=".txt",
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"),
                       ("All files", "*.*")])
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
            filetypes=[("JSON files", "*.json"), ("Text files", "*.txt"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            ids, skipped = load_selection(path)
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
        if skipped > 0:
            msg += f" {skipped} invalid ID(s) skipped."
        if unknown:
            msg += f" {len(unknown)} not in current catalog view."
            self.log_queue.put("Unknown IDs from file: " + ", ".join(unknown[:20]))
        self.status.set(msg)

    # -- help, about, window icon -----------------------------------------
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
        self._dialog_texts.pop(key, None)
        dlg.bind("<Destroy>", lambda e: self._dialog_texts.pop(key, None))
        return dlg

    def _title_font(self, delta=6):
        try:
            font = tkfont.nametofont("TkDefaultFont").copy()
            font.configure(size=font["size"] + delta, weight="bold")
        except tk.TclError:
            font = "TkDefaultFont"
        return font

    def _accent_color(self):
        if self._bootstrap:
            return self.style.colors.primary
        if self._is_dark_mode():
            return DARK_COLORS["accent"]
        return LIGHT_ACCENT

    def _style_dialog_text(self, widget):
        self._style_text_widget(widget)
        widget.tag_configure("h2", font=self._title_font(2),
                             foreground=self._accent_color())
        try:
            widget.tag_configure("code",
                                 font=tkfont.nametofont("TkFixedFont"))
        except tk.TclError:
            pass

    def _tag_guide_markup(self, text):
        for lineno, line in enumerate(
                text.get("1.0", "end").splitlines(), start=1):
            stripped = line.strip()
            if len(stripped) > 8 and stripped.isupper():
                text.tag_add("h2", f"{lineno}.0", f"{lineno}.end")
        start = "1.0"
        while True:
            opening = text.search("`", start, stopindex="end")
            if not opening:
                break
            closing = text.search("`", f"{opening}+1c", stopindex="end")
            if not closing:
                break
            text.tag_add("code", opening, f"{closing}+1c")
            start = f"{closing}+1c"

    def show_help(self):
        dlg = self._single_dialog("help", "How to use", "780x600")
        if dlg is None:
            self._style_dialog_text(self._dialog_texts["help"])
            return
        header = ttk.Frame(dlg, padding=(14, 12, 14, 0))
        header.pack(fill="x")
        ttk.Label(header, text="How to use",
                  font=self._title_font()).pack(anchor="w")
        ttk.Label(header,
                  text="The full guide lives here — press F1 anytime.").pack(
                      anchor="w", pady=(0, 6))
        frame = ttk.Frame(dlg, padding=(14, 0, 14, 10))
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", relief="flat",
                       highlightthickness=0,
                       font=tkfont.nametofont("TkTextFont"))
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        # the guide title lives in the header above; skip it in the body
        text.insert("1.0", "\n".join(USAGE_GUIDE.splitlines()[2:]))
        self._tag_guide_markup(text)
        text.configure(state="disabled")
        self._style_dialog_text(text)
        self._dialog_texts["help"] = text
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Button(dlg, text="Close",
                   command=dlg.destroy).pack(pady=(0, 10))

    def show_shortcuts(self):
        dlg = self._single_dialog("shortcuts", "Keyboard shortcuts",
                                  "600x420")
        if dlg is None:
            return
        frame = ttk.Frame(dlg, padding=(14, 12, 14, 10))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Keyboard shortcuts",
                  font=self._title_font()).pack(anchor="w")
        ttk.Label(frame,
                  text="These work anywhere in the app window.").pack(
                      anchor="w", pady=(0, 8))
        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True)
        tree = ttk.Treeview(table, columns=("keys", "action"),
                            show="headings", height=9)
        tree.heading("keys", text="Keys")
        tree.heading("action", text="Action")
        tree.column("keys", width=150, stretch=False)
        tree.column("action", width=380)
        stripes = stripe_colors(self._is_dark_mode())
        tree.tag_configure("even", background=stripes[0])
        tree.tag_configure("odd", background=stripes[1])
        for index, (keys, action) in enumerate(SHORTCUTS):
            tree.insert("", "end", values=(keys, action),
                        tags=("even" if index % 2 == 0 else "odd",))
        self._shortcut_tree = tree
        scroll = ttk.Scrollbar(table, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        ttk.Button(frame, text="Close",
                   command=dlg.destroy).pack(pady=(8, 0))

    def show_about(self):
        dlg = self._single_dialog("about", "About", "480x440")
        if dlg is None:
            self._style_dialog_text(self._dialog_texts["about"])
            return
        frame = ttk.Frame(dlg, padding=16)
        frame.pack(fill="both", expand=True)
        icon = load_icon(subsample=4)  # 64px
        if icon is not None:
            self._icon_refs.append(icon)
            ttk.Label(frame, image=icon).pack(pady=(4, 8))
        ttk.Label(frame, text="Flatpak Batch Installer",
                  font=self._title_font(4)).pack()
        ttk.Label(frame, text=f"Version {__version__}").pack(pady=(0, 8))
        body = tk.Text(frame, wrap="word", height=9, relief="flat",
                       highlightthickness=0,
                       font=tkfont.nametofont("TkTextFont"))
        body.insert("1.0", about_text(__version__).split("\n", 2)[2])
        body.configure(state="disabled")
        self._style_dialog_text(body)
        self._dialog_texts["about"] = body
        body.pack(fill="both", expand=True)
        ttk.Button(frame, text="Close",
                   command=dlg.destroy).pack(pady=(8, 0))

    # -- install -----------------------------------------------------------
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

        # Show per-app progress panel and populate rows
        self._progress_iids: dict[str, str] = {}
        for child in self._progress_tree.get_children():
            self._progress_tree.delete(child)
        for app_id in ids:
            iid = self._progress_tree.insert(
                "", "end", values=(app_id, "Queued"),
                tags=("queued",))
            self._progress_iids[app_id] = iid
        self.progress_panel.pack(fill="x", padx=(4, 0))

        def _update_progress(app_id: str, status_text: str, tag: str):
            """Safely update a progress row from the background thread."""
            if not self._alive:
                return
            iid = self._progress_iids.get(app_id)
            if iid:
                try:
                    self._progress_tree.item(
                        iid,
                        values=(app_id, status_text),
                        tags=(tag,))
                except tk.TclError:
                    pass

        def on_line(line: str):
            self.log_queue.put(line)
            # Parse line to detect per-app status changes
            lower = line.lower()
            for app_id in ids:
                app_lower = app_id.lower()
                if app_lower in lower:
                    if "installing" in lower or "install" in lower:
                        self.after(0, lambda a=app_id: _update_progress(
                            a, "Installing…", "installing"))
                    elif "error" in lower or "failed" in lower:
                        self.after(0, lambda a=app_id: _update_progress(
                            a, "Failed", "failed"))

        def worker():
            exit_code = stream_command(cmd, on_line)
            # Mark remaining queued/installing as done or failed
            final_tag = "done" if exit_code == 0 else "failed"
            final_text = "Done" if exit_code == 0 else "Failed"
            for app_id, iid in self._progress_iids.items():
                if not self._alive:
                    return
                try:
                    current = self._progress_tree.item(iid, "values")
                    if current and current[1] in ("Queued", "Installing…"):
                        self.after(0, lambda a=app_id: _update_progress(
                            a, final_text, final_tag))
                except tk.TclError:
                    pass
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
            if not self._alive:
                return
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()


__all__ = ["FlathubBrowser"]
