# Flatpak Batch Installer — Audit Report & Implementation Plan

---

## AUDIT REPORT

### CRITICAL

**C-1 — Race condition: GUI widget access after window destruction (ui.py)**
In `install_selected()`, the background worker thread calls `self.after(0, finish)` and
`self.installed = installed` after the install completes. If the user closes the window
mid-install, `self.after()` is called on a destroyed Tk root, raising `TclError` and
silently killing the thread. Worse, `self.installed = install` writes to a Python object
on a destroyed root — non-atomic cross-thread write with no guard.
`poll_log` also calls `self.after(100, self.poll_log)` forever; it never stops when the
window is closed, meaning it will fire on a dead root. Same issue in `load_catalog` and
`update_metadata` workers.
Fix: track `self._alive` flag (set to `False` in `WM_DELETE_WINDOW`); guard every
`self.after(0, …)` call inside threads with `if self._alive`.

**C-2 — Uncaught exception in `poll_log` crashes the event loop (ui.py)**
`poll_log` catches only `queue.Empty`. If `self.append_log` raises any exception
(e.g. widget destroyed), the exception propagates to the Tk event loop and silently
kills the recurring `after` callback — no more log messages appear but no error is
shown to the user.

**C-3 — Thread never joined on close (ui.py)**
Daemon threads are used (good), but there's no `WM_DELETE_WINDOW` handler. If the user
closes the window while an install is running, the thread may have written to
`self.installed` and called `self.after(0, finish)` on a dead interpreter. The app
may also hang if the Flatpak subprocess doesn't terminate.
Fix: register `protocol("WM_DELETE_WINDOW", self._on_close)` which sets `self._alive`
and calls `self.destroy()`.

**C-4 — `save_selection` writes duplicates (catalog.py)**
`save_selection` writes every ID in the list without deduplication. The existing test
(`test_round_trip_dedupes`) even asserts this buggy behaviour: saving `["b","a","a"]`
writes `b\na\na\n`. The function is documented to save unique IDs but doesn't. The
deduplication only happens in `load_selection`. Downstream risk: loading a file
produces more IDs than saved, confusing users.

---

### HIGH

**H-1 — User-provided search string reaches `App.matches()` without validation (models.py)**
`matches()` lower-cases and embeds the raw query string in an f-string comparison —
no special characters in the query can execute code, but a pathologically long query
(100 000 chars) causes a slow O(n·m) scan over the entire catalog on every keystroke.
The debounce in `schedule_filter` (250 ms) is the only protection. This is a
correctness/DoS concern in a GUI context.
Fix: truncate/strip query in `filter_rows` before passing to `matches()`.

**H-2 — `update_metadata` builds a command with `cmd[1:]` slicing incorrectly (ui.py)**
```python
cmd = ["flatpak", *scope_args(scope), "update", "--appstream", REMOTE]
…
result = run_flatpak(cmd[1:], timeout=300)
```
`run_flatpak` prepends `"flatpak"` itself, so `cmd[1:]` is correct. But the log
displays `cmd` (the full list), while the actual call uses `cmd[1:]`. This is
inconsistent and confusing, and is a latent bug: if `scope_args()` ever returns more
items the slice will be wrong. The correct pattern is to build args without `"flatpak"`
upfront and pass them to `run_flatpak`.

**H-3 — `stream_command` has no timeout (installer.py)**
`stream_command` calls `subprocess.Popen` with no timeout. A hung `flatpak install`
(network stall, interactive prompt) blocks the worker thread forever, leaving the GUI
permanently in "Working…" state with no way to cancel.
Fix: add a `timeout` parameter (default 600 s) and kill the process on timeout.

**H-4 — No `WM_DELETE_WINDOW` handler — abrupt close during install (ui.py)**
See C-3. No `protocol("WM_DELETE_WINDOW", …)` means Tkinter destroys widgets
immediately while the install thread is running. This is both a crash risk and a data-
loss risk (partial install with no feedback).

**H-5 — `catalog.py save_selection` writes duplicates (same as C-4 — re-listed at High because it can corrupt round-trips)**

**H-6 — Theme `polish_active_theme` references undefined `c` in light mode (theme.py)**
```python
style.map("Accent.TButton",
          background=[("active", active), ("pressed", active),
                      ("disabled", c["bg_btn"] if dark else "#e9ecef")],
          foreground=[("disabled", c["fg_dim"] if dark else "#6c757d")])
```
`c` is only defined when `dark=True`. In light mode `c` is never assigned and
accessing `c["bg_btn"]` raises `NameError`. The `if dark else …` short-circuits, so
this doesn't crash in practice, but it is fragile and will break if Python's
evaluation order ever changes or if a refactor adds a non-dark branch that uses `c`.
Fix: always assign `c = DARK_COLORS` before the `if dark` branch.

**H-7 — `load_catalog` in background thread; `finish()` lambda captures mutable vars (ui.py)**
The lambda `lambda: [self.set_busy(False), self.status.set(msg)]` captures `msg` by
reference at define-time. This is fine currently but is a fragile pattern — if `msg`
were reassigned before `self.after(0, finish)` runs, stale text would be shown. Use
a `def finish():` closure (already done in `load_catalog` — good pattern) but verify
everywhere.

---

### MEDIUM

**M-1 — `flathub-gui.py` deprecated shim emits `DeprecationWarning` at import time**
The `warnings.warn` is called at module level before `if __name__ == "__main__"`, so
importing the module in tests would also emit the warning.

**M-2 — `on_row_focus` accesses `vals[3]`, `vals[2]`, `vals[1]`, `vals[4]` by index (ui.py)**
Column order is defined in `_build_widgets` but hardcoded by index in `on_row_focus`.
A future column reorder will silently show wrong data in the detail bar.
Fix: use named column accessors or a constant.

**M-3 — Missing type hints on key public APIs**
`filter_rows`, `parse_remote_ls`, `paginate`, `save_selection`, `load_selection` in
`catalog.py` use `list` without element type. `load_catalog` and `get_installed` in
`flatpak.py` return `tuple` without annotation. Inconsistent with `models.py` which
is fully typed.

**M-4 — `schedule_filter` stores debounce handle in `_filter_job` but attribute is never initialized in `__init__`**
`getattr(self, "_filter_job", None)` works around the missing init, but it's a
fragile pattern — if `_filter_job` is accidentally referenced elsewhere it raises
`AttributeError`. Fix: initialize `self._filter_job = None` in `__init__`.

**M-5 — `_dialog_texts` dict is never cleared when dialogs are destroyed**
`dlg.destroy()` removes the Toplevel from `_dialogs` only implicitly (via
`winfo_exists()` check on next open). But `_dialog_texts[key]` is never removed, so
a stale `tk.Text` widget reference accumulates after each dialog open/close cycle.
Not a memory leak (the widget is destroyed), but could cause `TclError` if
`_style_dialog_text` is called on a dead widget reference via the `_dialog_texts`
dict.

**M-6 — No validation of app IDs loaded from file (catalog.py / ui.py)**
`load_selection` returns arbitrary strings from user files. These IDs are later passed
to `build_install_cmd` and appended to a subprocess list. While this is safe (list-of-
args, no shell=True), a malformed ID like `--assumeyes` or `; rm -rf ~` passed as a
list element could affect flatpak's argument parsing.
Fix: validate loaded IDs against a pattern like `r'^[a-zA-Z0-9._-]+$'` before use.

**M-7 — `install_selected` shows the first 2000 chars of the preview but truncation marker is wrong**
```python
f"{preview[:2000]}" + ("\n..." if len(preview) > 2000 else "")
```
`preview` is `"\n".join(ids)` — this is fine. But for large selections, the dialog
may overflow. Low severity.

**M-8 — No empty-state message in the tree when catalog hasn't been loaded**
The status bar message says "Click 'Load catalog' first" but the tree is just blank.
A friendly empty-state placeholder would improve UX.

---

### LOW

**L-1 — `helptext.py` test: `test_documents_every_control` checks for "Working" in USAGE_GUIDE**
The guide says "Working…" (with ellipsis). The test checks for "Working" (without). This
passes today but is fragile.

**L-2 — `app.py` CLI `--install` mode: `subprocess.run(cmd)` has no timeout**
The CLI install path calls `subprocess.run(cmd)` with no timeout. This is consistent
with typical CLI usage (user controls their terminal) but could hang indefinitely.

**L-3 — `resources.py load_icon` silently swallows all `TclError` — expected, but missing docstring note**

**L-4 — Dead import: `tkinter.font` imported in `ui.py` as `tkfont` — used correctly, fine**

**L-5 — `selected_count` StringVar format ("Selected: 0 apps") is hardcoded in two places**
Both `__init__` and `update_count` set the format independently.

**L-6 — GUI keyboard shortcut Ctrl+D (deselect all) specified in task requirement but not yet implemented**
The plan requests it; current code only has "Clear" via button.

**L-7 — No tooltips on any interactive element**

**L-8 — No "Enter" shortcut for "Install selected" (Ctrl+Return exists but plain Enter doesn't)**
Minor UX issue.

---

## IMPLEMENTATION PLAN

---

### Phase 2 — Bug fixes and security hardening

- [ ] 1. Fix `WM_DELETE_WINDOW` handler + `_alive` guard in `ui.py`.
      Add `self._alive = True` in `__init__`; register
      `self.protocol("WM_DELETE_WINDOW", self._on_close)`. Implement `_on_close`:
      sets `self._alive = False`, then calls `self.destroy()`. Wrap every
      `self.after(0, …)` inside worker threads with `if not self._alive: return`.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v` — all tests pass; manually
      close window during a simulated busy state (mock the thread) and confirm no
      TclError in stderr.

- [ ] 2. Fix `poll_log` to guard against widget-destroyed TclError (ui.py).
      Wrap the `self.append_log` call in a try/except TclError; on error, stop
      rescheduling. Guard the `self.after(100, self.poll_log)` tail with
      `if self._alive`.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v`

- [ ] 3. Fix `save_selection` to deduplicate IDs before writing (catalog.py).
      Use seen-set deduplication identical to `load_selection`. Update the test in
      `test_catalog.py` (`test_round_trip_dedupes`) to assert the file contains
      `b\na\n` not `b\na\na\n`.
      Files: `flatpak_batch_installer/catalog.py`, `tests/test_catalog.py`
      Verify: `python3 -m unittest tests.test_catalog -v`

- [ ] 4. Fix `NameError` risk in `polish_active_theme` light mode (theme.py).
      Assign `c = DARK_COLORS` unconditionally before the `if dark` branch so both
      branches can reference `c` safely.
      Files: `flatpak_batch_installer/theme.py`
      Verify: `python3 -m unittest tests.test_ui -v` (exercises both dark=True and
      dark=False in `test_options_menu`).

- [ ] 5. Fix `update_metadata` command construction (ui.py).
      Build `update_args` as `[*scope_args(scope), "update", "--appstream", REMOTE]`
      (no leading `"flatpak"`), then call `run_flatpak(update_args, timeout=300)` and
      log `"Running: flatpak " + " ".join(update_args)`. Eliminates the fragile
      `cmd[1:]` slice.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v`

- [ ] 6. Add timeout and cancellation to `stream_command` (installer.py).
      Add `timeout: int = 600` parameter. Use `proc.communicate(timeout=timeout)` or
      loop with a `threading.Event` to allow cooperative cancellation. On timeout,
      call `proc.kill()`, call `on_line("ERROR: install timed out after N seconds.")`
      and return exit code 124.
      Files: `flatpak_batch_installer/installer.py`
      Verify: `python3 -m unittest tests -v` (no breakage; installer has no
      dedicated unit test, add one that passes a mock proc).

- [ ] 7. Validate app IDs loaded from selection files (catalog.py, ui.py).
      In `load_selection`, after stripping, check each ID against
      `re.match(r'^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$', app_id)`.
      Drop IDs that fail (log a warning count). In `load_selection_dialog` in ui.py,
      surface any skipped count in the status bar.
      Files: `flatpak_batch_installer/catalog.py`, `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_catalog -v` — add test case with
      malformed IDs like `--assumeyes` and confirm they're dropped.

- [ ] 8. Initialize `_filter_job` in `__init__` (ui.py).
      Add `self._filter_job = None` alongside the other instance attributes.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v`

- [ ] 9. Fix stale `_dialog_texts` references (ui.py).
      In `_single_dialog`, if a new dialog is created (not re-used), remove any
      existing `_dialog_texts[key]` entry. Bind `<Destroy>` on the dialog to pop
      `self._dialog_texts.pop(key, None)`.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v`

- [ ] 10. Truncate over-long search queries (catalog.py / models.py).
      In `filter_rows`, truncate `query` to 200 characters before passing to
      `app.matches()`. Add `if len(q) > 200: q = q[:200]` in `App.matches()` as
      belt-and-suspenders.
      Files: `flatpak_batch_installer/catalog.py`, `flatpak_batch_installer/models.py`
      Verify: `python3 -m unittest tests.test_catalog -v`

- [ ] 11. Add type hints to `catalog.py` public API.
      Annotate `parse_remote_ls`, `filter_rows`, `paginate`, `save_selection`,
      `load_selection` with `list[App]`, `list[str]`, return types.
      Files: `flatpak_batch_installer/catalog.py`
      Verify: `python3 -m compileall -q flatpak_batch_installer` — no errors.

---

### Phase 3 — Modern GUI redesign

- [ ] 12. Sidebar layout: split main area into left filter panel + right app list (ui.py).
      Replace the single vertical stack with a `ttk.PanedWindow` (horizontal).
      Left pane (min 200 px): search entry (prominent), status filter combobox with
      label, category filter (if available), scope radio buttons, action buttons
      (Install Selected, Update All). Right pane: the existing `ttk.Treeview` +
      pager. The top `ttk.Frame` toolbar becomes a header bar with just the title,
      scope badge, and Options/Help menubuttons.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v` — all existing tests pass.

- [ ] 13. App cards/rich rows: bold name + muted summary in the list (ui.py, theme.py).
      Configure the Treeview with two lines per row (rowheight=44). Column layout:
      `sel` (36 px), `status` badge (90 px), `name` (bold tag, 200 px),
      `appid` (220 px), `summary` (muted color via tag, remaining width).
      Add `name_bold` and `summary_muted` Treeview tags in `apply_filter`.
      Files: `flatpak_batch_installer/ui.py`, `flatpak_batch_installer/theme.py`
      Verify: `python3 -m unittest tests.test_ui -v`

- [ ] 14. Search bar improvements: clear (✕) button, real-time debounced local filter (ui.py).
      Next to the filter entry, add a small `ttk.Button` with text "✕" that calls
      `clear_filter()`. The button is only visible when the filter is non-empty
      (trace on `filter_var`). The existing `schedule_filter` debounce (250 ms) is
      already correct — keep it. Do NOT trigger any flatpak call on keystroke.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v`; manually verify ✕ appears only
      when filter is non-empty.

- [ ] 15. Persistent status bar with totals, selected count, scope, last-action (ui.py).
      Redesign the bottom status bar to show four segments:
      `[Total: N apps loaded]  [Selected: N]  [Scope: user]  [last-action message]`
      Use `ttk.Label` widgets in a `ttk.Frame` with separators. Keep `self.status` for
      last-action text. Add `self.total_var`, `self.scope_badge_var`.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v`

- [ ] 16. Per-app install progress: queued → installing → done/failed (ui.py, installer.py).
      Replace the raw log dump during install with a per-app status panel.
      Add `InstallerProgressPanel` frame (or reuse log area) that shows each app ID as
      a row with a `StringVar` status label. The `stream_command` `on_line` callback
      parses flatpak's output for app-ID lines ("Installing …/APP_ID") and updates the
      matching row. Keep the raw log in a collapsible `tk.Text` below.
      Files: `flatpak_batch_installer/ui.py`, `flatpak_batch_installer/installer.py`
      Verify: `python3 -m unittest tests.test_ui -v`

- [ ] 17. Toolbar/header redesign: title/icon, scope toggle, action buttons (ui.py).
      Top `ttk.Frame` header shows: app icon (32 px), title label ("Flatpak Batch
      Installer"), scope toggle (two `ttk.Radiobutton` styled as a button-group),
      right-aligned: Install Selected (accent), Refresh (F5), Export, Import,
      Options dropdown, Help dropdown.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v` — `test_modern_chrome` and
      `test_options_menu` still pass (update assertions for new layout).

- [ ] 18. Category filter sidebar/tag filter (ui.py, catalog.py, models.py).
      Extract unique category tokens from app IDs (e.g. `org.gnome.*` → "GNOME",
      or a static category mapping). Add `App.category: str = ""` field to models.py
      and populate it in `parse_remote_ls` via a lookup dict in `catalog.py`.
      In the left sidebar add a `ttk.Combobox` (or scrollable `tk.Listbox`) for
      category filter; `filter_rows` gains a `category` parameter.
      Files: `flatpak_batch_installer/models.py`, `flatpak_batch_installer/catalog.py`,
             `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_catalog -v tests.test_ui -v`

- [ ] 19. Keyboard shortcuts: Ctrl+D (deselect all), Enter (install), F5 already present (ui.py).
      Add `self.bind("<Control-d>", lambda e: self.clear_selection())`.
      Add `self.bind("<Return>", lambda e: self.install_selected())` (only fires when
      tree has focus, not entry, to avoid conflict).
      Update `SHORTCUTS` in `helptext.py` and `USAGE_GUIDE` to document Ctrl+D.
      Files: `flatpak_batch_installer/ui.py`, `flatpak_batch_installer/helptext.py`
      Verify: `python3 -m unittest tests -v` — `test_shortcuts_registered` updated.

- [ ] 20. Tooltips on all buttons and interactive elements (ui.py).
      Implement a `_add_tooltip(widget, text)` helper (create `tk.Toplevel` on
      `<Enter>`, destroy on `<Leave>`) or use a `ToolTip` class. Add tooltips to:
      Load catalog, Install selected, Select page, Clear, ✕ filter, all toolbar
      buttons, Prev/Next, page-size dropdown, scope radio buttons, status filter.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v` (tooltips are hard to test
      automatically; add a smoke test that `_tooltip_widgets` contains ≥ 8 entries).

- [ ] 21. Empty states: friendly messages when no results, nothing selected, catalog not loaded (ui.py).
      When `apply_filter` produces zero results, insert a single centered "no results"
      row in the Treeview (disabled, non-selectable). When no catalog is loaded, show
      a centered "Load catalog to get started" row. When nothing is selected and
      Install is clicked, show a friendly inline hint (already partly done, improve
      the wording to match design).
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v`

- [ ] 22. Dark/light mode: ensure theme switching is clean and complete (ui.py, theme.py).
      After the `c = DARK_COLORS` fix (item 4), verify the sidebar panel, status bar
      segments, new progress panel, and tooltip windows all respond to
      `toggle_theme()`. Add a `_recolor_all()` method called from `_set_dark()` that
      walks `self.winfo_children()` and reapplies Text/Frame/Label backgrounds.
      Files: `flatpak_batch_installer/ui.py`, `flatpak_batch_installer/theme.py`
      Verify: `python3 -m unittest tests.test_ui -v` — `test_theme_toggle_round_trip`
      and `test_bootstrap_themes` still pass.

---

### Phase 3 — New Features

- [ ] 23. Export/Import selection as JSON (ui.py, catalog.py).
      Extend `save_selection` / `load_selection` to support `.json` format (list of
      strings) in addition to plain text. Detect format by file extension in
      `load_selection`. In `save_selection_dialog` / `load_selection_dialog`, add
      `("JSON files", "*.json")` to the filetypes list. Use `json.dumps` /
      `json.loads`; no new dependencies.
      Files: `flatpak_batch_installer/catalog.py`, `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_catalog -v` — add JSON round-trip test.

- [ ] 24. Installed apps tab: view, filter, and uninstall (ui.py, flatpak.py).
      Add a `ttk.Notebook` with two tabs: "Browse" (existing view) and "Installed".
      The Installed tab shows a `ttk.Treeview` of `flatpak list --app` output
      (columns: app_id, name, version, scope). Add an "Uninstall selected" button
      that calls `flatpak [--user|--system] uninstall --assumeyes APP_ID` after a
      confirmation dialog. Add `get_installed_details(scope)` to `flatpak.py` that
      parses `--columns=application,name,version`. Uninstall runs in a background
      thread (rule: GUI never freezes). Reload installed set after uninstall.
      Files: `flatpak_batch_installer/ui.py`, `flatpak_batch_installer/flatpak.py`
      Verify: `python3 -m unittest tests.test_ui -v tests.test_flatpak -v`

- [ ] 25. App detail side panel (ui.py).
      In the right pane, add a collapsible detail panel below the Treeview.
      When a row is focused (`on_row_focus`), expand the panel and show: app name
      (bold, large), app ID, version (from installed data if available), installed
      status (badge), summary (full text). Panel collapses when no row is selected.
      Replace the current plain-text `self.detail` Label.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v`

- [ ] 26. "Update All" button — batch flatpak update (ui.py, flatpak.py).
      Add `run_update_all(scope, on_line) -> int` to `flatpak.py` which calls
      `stream_command(["flatpak", *scope_args(scope), "update",
      "--noninteractive", "--assumeyes"], on_line)`.
      In ui.py add an "Update All" button in the toolbar (or Options menu). On click:
      show confirmation dialog ("Update all installed Flatpak apps?"), then run in
      background thread, stream output to log area. Disable button while running.
      Files: `flatpak_batch_installer/ui.py`, `flatpak_batch_installer/flatpak.py`
      Verify: `python3 -m unittest tests.test_flatpak -v` — add test for
      `run_update_all` command construction.

- [ ] 27. Search history / recent searches dropdown (ui.py).
      Keep a `self._search_history: list[str]` (max 5, session-only, not persisted).
      After a search that returns ≥ 1 result, append the query to history if not
      already present. Replace the plain `ttk.Entry` for search with a `ttk.Combobox`
      in `"normal"` state (so the user can type freely). Populate its `values` from
      `self._search_history`. Selecting a history item applies the filter immediately.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v` — add test: run 3 searches,
      confirm history has 3 entries capped at 5.

- [ ] 28. Select by category — tag filter bulk-select (ui.py, catalog.py).
      In the left sidebar, once a category is selected, add a "Select all in
      category" button. Calls `filter_rows` with the category filter, then adds all
      matching `app_id` values to `self.selected_ids`. Refreshes marks and count.
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v` — add test.

- [ ] 29. Install button count badge — "Install (N apps)" label (ui.py).
      Bind `self.selected_count` changes (or call a `_update_install_btn_label()`
      helper from `update_count()`) to update the Install button text to
      `f"Install ({n} app{'s' if n != 1 else ''})"`. When 0 selected: "Install".
      Files: `flatpak_batch_installer/ui.py`
      Verify: `python3 -m unittest tests.test_ui -v` — add assertion.

---

### Phase 4 — Docs and tests

- [ ] 30. Update `CHANGELOG.md` under `[Unreleased]` with all changes from phases 2–3.
      Document: bug fixes (C-1 through H-7), security hardening (M-6), new features
      (Export/Import JSON, Installed tab, Detail panel, Update All, Search history,
      Category filter, Install count badge, tooltips, empty states, sidebar layout).
      Files: `CHANGELOG.md`
      Verify: `python3 -m compileall -q .` — no errors.

- [ ] 31. Update `README.md` feature list and Troubleshooting table.
      Add new features to "Other GUI features" section: Installed tab, Update All,
      App detail panel, search history, category filter, Export JSON.
      Update keyboard shortcuts table to include Ctrl+D.
      Files: `README.md`
      Verify: `python3 -m compileall -q .` — no errors (markdown doesn't compile,
      just confirm file is valid UTF-8 and renders).

- [ ] 32. Fix all test failures and add new tests.
      After phases 2–3:
      - `test_catalog.py`: update `test_round_trip_dedupes`; add JSON round-trip,
        malformed-ID validation, category-filter tests.
      - `test_ui.py`: update `test_modern_chrome`, `test_options_menu`,
        `test_shortcuts_registered` for new layout; add tests for Install count badge,
        Update All button presence, Installed tab existence, search history cap.
      - `test_flatpak.py`: add tests for `get_installed_details` and `run_update_all`.
      - `tests/test_installer.py` (new file): test `stream_command` timeout behaviour
        using `unittest.mock`.
      Files: `tests/test_catalog.py`, `tests/test_ui.py`, `tests/test_flatpak.py`,
             `tests/test_installer.py` (new)
      Verify: `python3 -m unittest discover -s tests -v` — all pass.

- [ ] 33. Smoke-test app launch (headless via xvfb or mocked TclError skip).
      Run `xvfb-run -a python3 -m unittest discover -s tests -v` and confirm zero
      failures and zero errors (SkipTest is acceptable for display-requiring tests
      without xvfb).
      Files: no source changes — CI verification step only.
      Verify: `python3 -m unittest discover -s tests -v` passes; or
      `xvfb-run -a python3 -m unittest discover -s tests -v` passes.

---

## Constraints cross-check

| Constraint | Respected in this plan |
|---|---|
| Runtime deps: ttkbootstrap ONLY | All new code uses stdlib (json, re, threading, tkinter). No new deps. |
| GUI never freezes | Items 16, 24, 26 all use background threads. |
| Explicit --user/--system on every flatpak call | Items 24, 26 use `scope_args()` consistently. |
| catalog.py / flatpak.py stay GUI-free | Items 18, 23, 24, 26 add helpers to those modules with no tkinter imports. |
| Theme works with and without ttkbootstrap | Items 4, 13, 22 are tested in both modes. |
| GUI tests SkipTest on TclError | Existing pattern preserved; all new test_ui additions follow the same pattern. |
| No destructive ops without confirmation | Items 24 (Uninstall) and 26 (Update All) both require confirmation dialogs. |
