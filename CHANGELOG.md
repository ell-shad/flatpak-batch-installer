# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.3.0] - 2026-10-09

### Added

- In-app Help (`?` button, Help menu, F1) documenting every control, and an
  About dialog showing the app icon, version and license.
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

- Package layout: `flathub_gui/` (`app`, `catalog`, `config`, `flatpak`,
  `installer`, `models`, `theme`, `ui`) with `flathub-gui.py` launcher.
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
  `flathub-gui.py`.

## [0.1.0] - 2026-10-07

- Initial single-file Tkinter prototype: load catalog via
  `flatpak remote-ls`, local filter, extended multi-select, batch install,
  log view.
