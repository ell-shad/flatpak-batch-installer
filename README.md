![Flathub Catalog Installer](assets/banner.png)

[![CI](../../actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)
[![Release](../../actions/workflows/release.yml/badge.svg)](../../actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](pyproject.toml)

Browse/search the Flathub catalog, select multiple apps, install them in one
Flatpak operation. GUI first, CLI capable, **stdlib only** (Python + Tkinter).

## Install

| Method | Command | Notes |
|---|---|---|
| **AppImage** (recommended) | Download `Flathub-Catalog-Installer-*.AppImage` from [Releases](../../releases), `chmod +x`, run | Works on any distro; bundles Python + Tk |
| **pipx** | `pipx install git+https://github.com/example/flathub-catalog-installer` | Needs Python 3.10+, Tk, Flatpak on host |
| **From source** | `python3 flathub-gui.py` | Developers; same host requirements |
| **Desktop shortcut** | `make install-user` | Adds launcher + icon, no root |

See [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md) for the full comparison
(AppImage vs pipx vs native packages vs Flatpak vs Snap) and build
instructions.

## Requirements

- Python 3.10+
- Tkinter (`sudo apt install python3-tk` on Debian/Ubuntu)
- Flatpak with the Flathub remote configured

## Quick start

```bash
python3 flathub-gui.py
```

(`flatpak-gui.py` still works but is deprecated.)

1. Pick **Scope**: `user` (safe default, no root needed) or `system`.
2. Click **Load catalog**.
3. Type in **Filter** to search name, app ID, or summary.
4. Click the **✓ column** to check/uncheck apps (Space toggles focused rows).
   Selection is kept when you change pages.
5. Browse pages with **< Prev / Next >** (rows/page: 100/200/500).
6. Click **Install selected**, review the confirmation list, confirm.
7. Stuck? Press **F1** or the **?** button — the full guide is built in
   (also: `python3 flathub-gui.py --help-guide`).

Long operations (catalog load, metadata update, install) run in background
threads. The **progress bar + "Working…" label** is only a busy spinner: it
animates while such an operation runs and stops when it finishes. The exact
Flatpak output streams into the log area below the table.

## Other GUI features

- **Status** filter: `all` / `installed` / `not-installed` / `selected`.
- **Status column** shows `Installed` (detected across user + system scopes).
- **Select page / Clear**, live **Selected: N apps** counter.
- **Details line** for the focused row (ID, name, status, summary).
- **Dark mode** checkbox (stdlib `ttk.Style` only; auto-detects a system dark
  preference, falls back to light).
- **Save/Load selection** (one app ID per line) for repeatable setup across
  machines.
- **Update** button runs `flatpak [--user|--system] update --appstream
  flathub`, then reloads.
- Install confirmation dialog; duplicates removed; one batch command:
  `flatpak [--user] install --assumeyes --noninteractive flathub <ids...>`.

## CLI mode (optional, headless)

```bash
python3 flathub-gui.py --list --scope user --search gimp
python3 flathub-gui.py --installed --scope system
python3 flathub-gui.py --install org.gimp.GIMP org.videolan.VLC --scope user
python3 flathub-gui.py --help-guide
python3 flathub-gui.py --version
```

Or, after `pip install .`, use the `flathub-gui` command directly.

## Project structure

```text
flathub-gui.py      thin launcher
flatpak-gui.py      deprecated alias (warns, delegates)
flathub_gui/
  __init__.py       version
  __main__.py       `python -m flathub_gui`
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
packaging/          desktop file, AppStream metainfo, AppImage + Flatpak builds
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
| GUI won't start (no display) | Use CLI mode: `python3 flathub-gui.py --list --search TEXT` |
| Tkinter missing | Debian/Ubuntu: `sudo apt install python3-tk`; Fedora: `sudo dnf install python3-tkinter`; Arch: `sudo pacman -S tk` |

## License

MIT — see [LICENSE](LICENSE). Security reports: [SECURITY.md](SECURITY.md).
