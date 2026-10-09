# Contributing to Flatpak Batch Installer

Thanks for helping out. The project is intentionally small and dependency-free;
please keep it that way.

## Setup

One lightweight runtime dependency: ttkbootstrap (pure Python, MIT).
`pip`/`pipx` install it automatically from `pyproject.toml`; running from a
bare checkout without it works too (built-in theme fallback).

- Python 3.10+
- Tkinter (`sudo apt install python3-tk` on Debian/Ubuntu)
- Flatpak with the Flathub remote (for live testing)

```bash
python3 flatpak-gui.py          # run the GUI
make test                       # run the test suite
make lint                       # byte-compile everything
make assets                     # regenerate artwork from assets/icon-source.jpg
```

## Conventions

1. **Almost no dependencies.** Runtime deps are limited to ttkbootstrap
   (pure Python, optional at runtime with a built-in fallback). Do not add
   heavy dependencies (no GTK/Qt bindings, no web frameworks) without
   explicit user approval. New stdlib modules are fine.
2. **Never block the UI thread.** Flatpak calls go in background threads and
   stream output to the log area (see `flatpak_batch_installer/installer.py`).
3. **Prefer official Flatpak commands** over scraping flathub.org.
4. **No destructive surprises.** Never uninstall anything unless the user
   explicitly requested it; install only after the confirmation dialog.
5. **Test the helpers.** Pure logic in `catalog.py` / `flatpak.py` gets unit
   tests under `tests/`. GUI tests live in `tests/test_ui.py` and must skip
   cleanly when no display is available.
6. **Update docs.** User-facing changes need a README note and a CHANGELOG
   entry under `Unreleased`.

## Pull requests

- Small, focused PRs. One feature/fix per PR.
- `make test` must pass (CI runs it under `xvfb` on Python 3.10–3.13).
- Use the PR template; link any related issue.
- Packaging changes: see [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md);
  validate with `desktop-file-validate` and
  `appstreamcli validate --no-net`.

## Reporting bugs

Use the bug-report issue template and include: distro, Python/Tk versions
(`python3 --version`, `apt list --installed | grep python3-tk`), scope
(user/system), and the relevant log output from the app.
