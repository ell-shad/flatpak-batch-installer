![Flatpak Batch Installer](assets/banner.png)

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)
[![Release](../../actions/workflows/release.yml/badge.svg)](../../actions/workflows/release.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](pyproject.toml)

Browse/search the Flathub catalog, select multiple apps, install them in one
Flatpak operation. GUI first, CLI capable. Python + Tkinter with one
lightweight pure-Python theme library (ttkbootstrap — declared dependency,
graceful built-in fallback when absent).

## Install

| Method | Command | Notes |
|---|---|---|
| **.deb** (recommended, Debian-based) | Download `flatpak-batch-installer_*_all.deb` from [Releases](../../releases), `sudo apt install ./flatpak-batch-installer_*_all.deb` | Officially supported on Debian 12+, Ubuntu 22.04+ and derivatives (Mint, Pop!_OS…); pulls Tk/Pillow/Flatpak from the distro |
| **AppImage** (universal) | Download `Flatpak-Batch-Installer-*.AppImage`, `chmod +x`, run | Any distro; bundles Python + Tk. Needs FUSE (`sudo apt install libfuse2`) or run with `--appimage-extract` |
| **pipx** | `pipx install git+https://github.com/ell-shad/flatpak-batch-installer` | Needs Python 3.10+, Tk, Flatpak on host |
| **From source** | `pip install ttkbootstrap` then `python3 flatpak-gui.py` | Developers; same host requirements |
| **Desktop shortcut** | `make install-user` | Adds launcher + icon, no root |

> **Support statement:** Debian-based systems (via `.deb`) are officially
> supported and tested in CI. Other distros work through the AppImage or
> pipx on a best-effort basis — bug reports welcome.

See [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md) for the full comparison
(AppImage vs pipx vs native packages vs Flatpak vs Snap) and build
instructions.

## Requirements

- Python 3.10+
- Tkinter (`sudo apt install python3-tk` on Debian/Ubuntu)
- Flatpak with the Flathub remote configured
- ttkbootstrap for the modern Bootstrap-style themes
  (`pip install ttkbootstrap`; without it the app falls back to its
  built-in light/dark themes — installed automatically via pip/pipx)

## Quick start

```bash
python3 flatpak-gui.py
```

(`flathub-gui.py` still works but is deprecated.)

1. Pick install **Scope** in the **Options** menu: `user` (safe default,
   no root needed) or `system`.
2. Click **Load catalog**.
3. Type in **Filter** to search name, app ID, or summary.
4. Click the **✓ column** to check/uncheck apps (Space toggles focused rows).
   Selection is kept when you change pages.
5. Browse pages with **< Prev / Next >** (rows/page: 100/200/500).
6. Click **Install selected**, review the confirmation list, confirm.
7. Stuck? Press **F1** (guide) or **Ctrl+K** (shortcuts), or open the
   **Help** menu — everything is documented in-app
   (also: `python3 flatpak-gui.py --help-guide`).

Long operations (catalog load, metadata update, install) run in background
threads. The **progress bar + "Working…" label** is only a busy spinner: it
animates while such an operation runs and stops when it finishes. The exact
Flatpak output streams into the log area below the table.

## Other GUI features

- **Status** filter: `all` / `installed` / `not-installed` / `selected`.
- **Status column** shows `Installed` (detected across user + system scopes).
- **Select page / Clear**, live **Selected: N apps** counter.
- **Details line** for the focused row (ID, name, status, summary).
- **Dark mode** checkbox: modern Bootstrap-style light/dark themes via
  ttkbootstrap when installed (built-in fallback otherwise);
  auto-detects a system dark preference.
- **Save/Load selection** (one app ID per line) for repeatable setup across
  machines.
- **Update** button runs `flatpak [--user|--system] update --appstream
  flathub`, then reloads.
- Install confirmation dialog; duplicates removed; one batch command:
  `flatpak [--user] install --assumeyes --noninteractive flathub <ids...>`.

## CLI mode (optional, headless)

```bash
python3 flatpak-gui.py --list --scope user --search gimp
python3 flatpak-gui.py --installed --scope system
python3 flatpak-gui.py --install org.gimp.GIMP org.videolan.VLC --scope user
python3 flatpak-gui.py --help-guide
python3 flatpak-gui.py --version
```

Or, after `pip install .`, use the `flatpak-batch-installer` command directly.

## Project structure

```text
flatpak-gui.py      thin launcher
flatpak-gui.py      deprecated alias (warns, delegates)
flatpak_batch_installer/
  __init__.py       version
  __main__.py       `python -m flatpak_batch_installer`
  app.py            CLI parsing + GUI entry point
  catalog.py        parse/filter/paginate catalog, save/load selections
  config.py         constants (remote, scope, page size, palette)
  flatpak.py        flatpak CLI wrappers + error diagnosis
  helptext.py       usage guide + About text (used by GUI and CLI)
  installer.py      streaming batch-install runner
  models.py         App dataclass
  resources.py      bundled icon access
  theme.py          dark-mode ttk theme + detection
  ui.py             FlathubBrowser GUI
assets/             icon source + generated PNGs, hicolor set, banner
packaging/          desktop file, AppStream metainfo, AppImage + .deb + Flatpak builds
docs/               DISTRIBUTION.md (packaging research + how-tos)
tests/              unittest suite (run with `make test`)
```

See [AGENT.md](AGENT.md) for contributor/agent notes,
[CONTRIBUTING.md](CONTRIBUTING.md) for workflow, and
[CHANGELOG.md](CHANGELOG.md) for history.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Remote not found | `flatpak --user remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo` |
| Empty names/summaries | Click **Update**, or run `flatpak --user update --appstream flathub` |
| Permission denied (system) | Switch Scope to **user** |
| "multiple installations" prompt | Pick an explicit scope; bare `flatpak remote-ls flathub` is ambiguous when both scopes exist |
| GUI won't start (no display) | Use CLI mode: `python3 flatpak-gui.py --list --search TEXT` |
| Tkinter missing | Debian/Ubuntu: `sudo apt install python3-tk`; Fedora: `sudo dnf install python3-tkinter`; Arch: `sudo pacman -S tk` |
| Old/classic look despite ttkbootstrap installed | ttkbootstrap needs Pillow *with Tk support*: Debian/Ubuntu split it out, so source runners need `sudo apt install python3-pil.imagetk`. pipx installs and the AppImage bundle full Pillow, so they are unaffected. |

## License

GNU GPLv3 or later — see [LICENSE](LICENSE). Security reports: [SECURITY.md](SECURITY.md).
