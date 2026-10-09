"""Runtime access to bundled data files (app icon).

Degrades gracefully: every function returns ``None`` instead of raising
when the artwork is missing (e.g. a source checkout without generated
assets — run ``python3 assets/make_assets.py`` to regenerate).
"""

import os


def icon_path():
    """Filesystem path of the bundled app icon, or ``None``."""
    try:
        from importlib import resources
        ref = resources.files("flatpak_batch_installer.data").joinpath("icon.png")
        if ref.is_file():
            return str(ref)
    except Exception:
        pass
    fallback = os.path.join(os.path.dirname(__file__), "data", "icon.png")
    return fallback if os.path.isfile(fallback) else None


def load_icon(subsample=1):
    """Load the app icon as a Tk ``PhotoImage`` (or ``None``).

    ``subsample`` shrinks the 256px master (e.g. 4 → 64px for dialogs).
    """
    import tkinter as tk
    path = icon_path()
    if not path:
        return None
    try:
        img = tk.PhotoImage(file=path)
        if subsample > 1:
            img = img.subsample(subsample, subsample)
        return img
    except tk.TclError:
        return None


__all__ = ["icon_path", "load_icon"]
