# AGENT.md — instructions for coding agents working on this repo

## What this is

Flathub Catalog Installer: browse/search the Flathub catalog, multi-select
apps, batch-install via Flatpak. GUI-first (Tkinter), CLI-capable, **stdlib
only** — never add third-party runtime dependencies without explicit user
approval.

## Layout

```text
flathub-gui.py      thin launcher (imports flathub_gui.app:main)
flatpak-gui.py      deprecated shim, warns and delegates
flathub_gui/
  __init__.py       version
  app.py            CLI parsing (run_cli), GUI entry (run_gui), main()
  catalog.py        parse/filter/paginate catalog + save/load selection files
  config.py         constants (REMOTE, DEFAULT_SCOPE, PAGE_SIZE, palette)
  flatpak.py        flatpak CLI wrappers + error diagnosis (no GUI imports)
  installer.py      stream_command() batch-install runner (GUI worker uses it)
  models.py         App dataclass
  helptext.py       USAGE_GUIDE + about_text() (GUI Help/About + --help-guide)
  resources.py      icon_path()/load_icon() — never raise, return None
  theme.py          dark-mode ttk theme + system-preference detection
  ui.py             FlathubBrowser GUI (only module importing tkinter)
assets/             icon-source.jpg + make_assets.py pipeline + generated PNGs
packaging/          desktop file, metainfo, AppImage + Flatpak builds
docs/               DISTRIBUTION.md (packaging research + build how-tos)
tests/              unittest suite (catalog, flatpak, ui, help)
```

## Commands

```bash
make test                         # full suite (needs a display or xvfb)
python3 -m unittest discover -s tests -v
xvfb-run -a python3 -m unittest discover -s tests   # headless GUI tests
python3 flathub-gui.py            # GUI
python3 flathub-gui.py --list --scope user --search gimp   # CLI
make assets                       # regenerate icon/banner from assets/icon-source.jpg
bash packaging/appimage/build-appimage.sh  # AppImage (oldest supported base)
```

## Rules (from project history — respect them)

1. GUI must never freeze: Flatpak calls run in background threads.
2. Explicit `--user`/`--system` scope on every flatpak call (bare remote-ls
   prompts interactively when both installations exist).
3. Helpers in `catalog.py`/`flatpak.py` stay GUI-free and headless-testable.
4. GUI tests must `SkipTest` when `tk.Tk()` raises `TclError`.
5. No destructive commands without explicit user confirmation in the UI.
6. Update `README.md` + `CHANGELOG.md` (Unreleased) for user-facing changes.

## Definition of done (stable GUI)

Loads catalog reliably · search by name/ID/summary · clear multi-select with
count · installed status shown · user/system scope switch · batch install with
visible output and clear success/failure · helpful errors · no UI freezes ·
no source edits needed for common options.
