# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.7.0] - 2026-10-11

### Fixed

- **WM\_DELETE\_WINDOW race** — closing the window during a background
  operation no longer raises `TclError`; `_on_close()` sets `self._alive =
  False` before destroying the window and every background callback guards on
  it.
- **`poll_log` crash** — `append_log` calls are now wrapped in
  `try/except tk.TclError`; the recurring `after` call stops when
  `self._alive` is False.
- **`save_selection` deduplication** — duplicate app IDs are silently
  removed (first-occurrence order preserved) before writing the file.
- **`NameError` in `polish_active_theme` light mode** — `c` is now assigned
  unconditionally before the `if dark` branch.
- **`update_metadata` command construction** — the command is built as
  `[*scope_args(scope), 'update', '--appstream', REMOTE]` and passed
  directly to `run_flatpak()`; the old off-by-one `cmd[1:]` slice is gone.
- **`stream_command` timeout** — `stream_command` now accepts a `timeout`
  parameter (default 600 s); on `TimeoutExpired` it kills the process,
  calls `on_line` with an error message, and returns 124.
- **App-ID validation in `load_selection`** — entries that do not match
  `^[A-Za-z0-9][A-Za-z0-9._-]*$` (e.g. `--assumeyes`, `; rm -rf ~`) are
  dropped; the caller receives a `(ids, skipped_count)` tuple.
- **`_filter_job` init** — `self._filter_job = None` is now set in
  `__init__`; the `getattr` fallback in `schedule_filter` is removed.
- **Stale `_dialog_texts` references** — `_single_dialog()` pops the stale
  text-widget reference on creation and binds `<Destroy>` to auto-pop.
- **Query truncation** — `filter_rows()` truncates `query` to 200 chars;
  `App.matches()` applies the same cap as belt-and-suspenders.

### Added

- **Sidebar layout** — the browser now has a persistent left sidebar
  (~224 px) containing search, status filter, category filter, scope
  radio buttons, and selection actions.
- **App detail panel** — a collapsible panel below the Treeview shows name,
  app ID, status badge, and a 3-line summary for the focused row.
- **Per-app install progress panel** — a dedicated `ttk.Treeview` tracks
  each app's install status (Queued → Installing… → Done / Failed) with
  tag-based colour coding.
- **Search history dropdown** — the search box remembers the last 5
  non-empty searches for the session.
- **Category filter** — a "Category" combobox in the sidebar filters the
  catalog by detected app category (GNOME, KDE, Graphics, Gaming, …).
- **Install count badge** — the Install button label updates to
  `Install (N)` when N apps are selected.
- **Ctrl+D shortcut** — deselects all apps (also in the Help → Keyboard
  shortcuts list).
- **Tooltips** — at least 13 interactive controls carry hover tooltips.
- **Empty states** — the Treeview shows a friendly placeholder row when no
  catalog is loaded or no search matches are found.
- **Installed Apps tab** — a second Notebook tab lists all installed
  Flatpak apps (user + system) with an Uninstall Selected action
  (confirmation required).
- **Update All button** — updates all installed Flatpak apps for the
  selected scope via a streamed log; requires confirmation.
- **Export / Import JSON** — `save_selection()` and `load_selection()` now
  support `.json` files in addition to plain-text `.txt` files; the same
  ID-validation rules apply to JSON entries.
- **Select all in category** — a "Select all in category" button adds every
  app in the current category filter to the selection in one click.

### Changed

- **Modern GUI redesign** — the classic single-column layout is replaced by
  a sidebar + right-pane `PanedWindow`; the header bar holds the app icon,
  title, Install, Update All, Refresh, Options, and Help controls; the
  status bar has 4 persistent segments (Total / Selected / Scope / Status).
- **Rich Treeview rows** — row height increased to 44 px; a `summary_muted`
  tag dims the summary text for better visual hierarchy.
- **Header toolbar** — scope radio buttons moved to the sidebar; the old
  "Load catalog" button is replaced by Refresh (F5); the toolbar is now a
  true header bar with the app branding on the left.

## [0.6.1] - 2026-10-09

### Added

- `.deb` packaging (`make deb`): officially supported install path for
  Debian 12+, Ubuntu 22.04+ and derivatives, with man page, DEP-5
  copyright, changelogs and lintian-clean metadata. Released artifacts
  now include the `.deb` alongside the AppImage and Python packages.

### Fixed

- Release AppImage actually contained no app code (old distro pip built
  an empty `UNKNOWN-0.0.0` package; checks masked it via the source
  tree). The build now upgrades pip, verifies the bundle from a neutral
  directory, and the AppRun no longer resolves modules from the
  caller's cwd.

### Changed

- Single-row toolbar: Filter, Select page and Clear moved up; Save/Load
  buttons removed (they live in Options); selection counter moved to the
  statusbar.
- Help refreshed: modern proportional body with highlighted section
  headers and commands, header blocks, and a separate Keyboard
  shortcuts window (Help menu, Ctrl+K) backed by one data list.

### Changed

- Toolbar decluttered: Scope, Update metadata, Save/Load selection and
  Dark mode moved into an `Options` dropdown (Help menu stays help-only).
  Top row now holds Load catalog, Status filter, Install and the two
  dropdowns.

## [0.6.0] - 2026-10-09

### Added

- Keyboard shortcuts: F1 help, F5 reload catalog, Ctrl+F filter,
  Ctrl+S / Ctrl+O save/load selection, Ctrl+Enter install,
  Ctrl+A tick page, Space tick rows, Esc clear filter (all in Help).

### Changed

- License switched from MIT to GNU GPLv3 or later (sole authorship,
  all dependencies GPL-compatible). App tells when ttkbootstrap is
  missing and falls back to built-in themes.

## [0.5.0] - 2026-10-09

### Added

- Modern Bootstrap-style light/dark themes via ttkbootstrap (pure Python,
  declared dependency, verified working with 1.x and 2.x theme names).
  The app still runs fully without it via the built-in theme fallback;
  CI now runs the suite both ways.

### Changed

- Theme internals unified: one color source drives root background, log,
  dialogs and combobox popups in every mode.

## [0.4.0] - 2026-10-09

### Changed

- Renamed to **Flatpak Batch Installer**: package `flathub_gui` →
  `flatpak_batch_installer`, launcher `flatpak-gui.py`, console script
  `flatpak-batch-installer`, APP_ID `io.github.flatpak-batch-installer`.
  Old `flathub-gui.py` is now the deprecated shim. The new name states
  the key feature (batch installs) instead of the vague "catalog".
- Single-item menubar removed: Help now lives in a toolbar `Help`
  dropdown (How to use / About), F1 still works.
- Visual polish with stdlib ttk only: accent style on the Install button,
  roomier controls, bold table headers, alternating row stripes in both
  light and dark modes.

## [0.3.0] - 2026-10-09

### Added

- In-app Help (usage guide + About dialog, also F1) documenting every
  control, and an About dialog showing icon, version and license.
- `--help-guide` CLI flag printing the same usage guide.
- App icon + generated artwork (`assets/`: transparent master PNG, hicolor
  icon set, README banner) with a reproducible `assets/make_assets.py`
  pipeline; window and About-dialog icons at runtime.
- Distribution: per-user desktop install (`make install-user`), AppImage
  build script, experimental Flatpak manifest, AppStream metainfo,
  `docs/DISTRIBUTION.md` comparing AppImage / pipx / native / Flatpak / Snap.
- Repo automation: release workflow (sdist + wheel + AppImage attached to
  GitHub Releases on `v*` tags), CodeQL scanning, Dependabot for actions.
- Community files: `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.editorconfig`,
  `.gitattributes`.

## [0.2.0] - 2026-10-07

### Added

- Package layout: `flatpak_batch_installer/` (`app`, `catalog`, `config`, `flatpak`,
  `installer`, `models`, `theme`, `ui`) with `flatpak-gui.py` launcher.
- Pagination: full catalog browsable via Prev/Next pages, rows/page selector;
  the old 1000-row display cap is removed.
- Dark mode toggle (stdlib `ttk.Style` only) with system-preference autodetect.
- Installed-app detection across user + system scopes, status filter.
- User/system install-scope switch (defaults to user).
- Save/load selection files; install confirmation dialog; CLI mode
  (`--list`, `--installed`, `--install`).
- Repo scaffolding: tests, CI, `pyproject.toml`, `Makefile`, issue/PR
  templates, `CONTRIBUTING.md`, `AGENT.md`, MIT license.

### Changed

- Old single-file `flatpak-gui.py` is now a deprecated shim of
  `flatpak-gui.py`.

## [0.1.0] - 2026-10-07

- Initial single-file Tkinter prototype: load catalog via
  `flatpak remote-ls`, local filter, extended multi-select, batch install,
  log view.
