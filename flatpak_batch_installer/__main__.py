"""Run the app as ``python -m flatpak_batch_installer`` (used by the AppImage AppRun too)."""

from .app import main

if __name__ == "__main__":
    raise SystemExit(main())
