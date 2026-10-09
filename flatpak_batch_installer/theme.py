"""Dark-mode support using stdlib ``ttk.Style`` only.

No external theme libraries, no images, no extra processes: just one
registered ttk theme variant plus plain color strings. Memory impact is a
few kilobytes of style definitions.
"""

import os
import subprocess

from .config import (
    ACCENT_FG,
    DARK_COLORS,
    DARK_STRIPES,
    LIGHT_ACCENT,
    LIGHT_ACCENT_ACTIVE,
    LIGHT_STRIPES,
)

try:
    import ttkbootstrap
    BOOTSTRAP_AVAILABLE = True
except ImportError:
    ttkbootstrap = None
    BOOTSTRAP_AVAILABLE = False

#: ttkbootstrap theme pair (2.x family names; 1.x legacy names as fallback).
BOOTSTRAP_THEMES = {"light": "bootstrap-light", "dark": "bootstrap-dark"}
BOOTSTRAP_THEMES_LEGACY = {"light": "flatly", "dark": "darkly"}


def create_style(root):
    """Prefer a ttkbootstrap style; fall back to plain ttk.

    The app works fully without ttkbootstrap installed (built-in
    clam-based light/dark themes); with it, every ttk widget —
    including the table — gets a modern Bootstrap-style theme.

    Note: ttkbootstrap.Style is a documented process-wide singleton
    bound to the first Tk root. The app (and the test-suite) therefore
    uses exactly one root per process, which is the normal pattern.
    """
    if BOOTSTRAP_AVAILABLE:
        return ttkbootstrap.Style()
    import tkinter.ttk as ttk
    return ttk.Style(root)


def is_bootstrap(style) -> bool:
    return BOOTSTRAP_AVAILABLE and isinstance(style, ttkbootstrap.Style)


def bootstrap_theme_name(style, dark: bool) -> str:
    """Theme name for the mode, tolerating ttkbootstrap 1.x and 2.x names."""
    names = style.theme_names()
    pair = BOOTSTRAP_THEMES if BOOTSTRAP_THEMES["light"] in names \
        else BOOTSTRAP_THEMES_LEGACY
    return pair["dark" if dark else "light"]


def system_prefers_dark() -> bool:
    """Best-effort dark-mode detection. Never raises, never blocks long."""
    try:
        if "dark" in os.environ.get("GTK_THEME", "").lower():
            return True
    except Exception:
        pass
    for key in ("color-scheme", "gtk-theme"):
        try:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", key],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0 and "dark" in (result.stdout or "").lower():
                return True
        except Exception:
            continue
    return False


def dark_theme_settings() -> dict:
    """ttk settings dict for ``style.theme_create(DARK_THEME_NAME, ...)``."""
    c = DARK_COLORS
    return {
        ".": {"configure": {"background": c["bg"], "foreground": c["fg"]}},
        "TFrame": {"configure": {"background": c["bg"]}},
        "TLabel": {"configure": {"background": c["bg"], "foreground": c["fg"]}},
        "TButton": {
            "configure": {"background": c["bg_btn"], "foreground": c["fg"],
                          "bordercolor": c["border"]},
            "map": {"background": [("active", c["bg_hover"]),
                                   ("pressed", c["bg_hover"]),
                                   ("disabled", c["bg"])],
                    "foreground": [("disabled", c["fg_dim"])]},
        },
        "TCheckbutton": {
            "configure": {"background": c["bg"], "foreground": c["fg"]},
            "map": {"foreground": [("disabled", c["fg_dim"])]},
        },
        "TEntry": {"configure": {"fieldbackground": c["bg_alt"],
                                 "foreground": c["fg"],
                                 "insertcolor": c["fg"]}},
        "TCombobox": {
            "configure": {"fieldbackground": c["bg_alt"],
                          "background": c["bg_btn"],
                          "foreground": c["fg"],
                          "arrowcolor": c["fg"]},
            "map": {"fieldbackground": [("readonly", c["bg_alt"])],
                    "foreground": [("disabled", c["fg_dim"])]},
        },
        "Treeview": {
            "configure": {"background": c["bg_alt"],
                          "fieldbackground": c["bg_alt"],
                          "foreground": c["fg"],
                          "bordercolor": c["border"]},
            "map": {"background": [("selected", c["accent"])],
                    "foreground": [("selected", c["accent_fg"])]},
        },
        "Treeview.Heading": {
            "configure": {"background": c["bg_btn"],
                          "foreground": c["accent_fg"]},
            "map": {"background": [("active", c["bg_hover"])]},
        },
        "TProgressbar": {"configure": {"background": c["accent"]}},
    }


def polish_active_theme(style, dark: bool, heading_font=None):
    """Refine the *currently active* ttk theme (call after every switch).

    Safe on any base theme (clam, default, ...): plain configure/map calls
    only. Gives the app a flatter, more modern look without new deps:
    roomier buttons, an accent style for the primary action, taller table
    rows with a bold header. Returns the (even, odd) stripe colors so the
    table can tag its rows to match the active mode.
    """
    style.configure("TButton", padding=(10, 6))
    style.configure("TCheckbutton", padding=(4, 4))
    style.configure("TEntry", padding=(6, 4))
    style.configure("Treeview", rowheight=26)
    if heading_font is not None:
        style.configure("Treeview.Heading", font=heading_font)
    if dark:
        c = DARK_COLORS
        accent, active = c["accent"], c["bg_hover"]
    else:
        accent, active = LIGHT_ACCENT, LIGHT_ACCENT_ACTIVE
    style.configure("Accent.TButton", background=accent,
                    foreground=ACCENT_FG, padding=(12, 6))
    style.map("Accent.TButton",
              background=[("active", active), ("pressed", active),
                          ("disabled", c["bg_btn"] if dark else "#e9ecef")],
              foreground=[("disabled", c["fg_dim"] if dark else "#6c757d")])
    return DARK_STRIPES if dark else LIGHT_STRIPES


__all__ = [
    "BOOTSTRAP_AVAILABLE",
    "BOOTSTRAP_THEMES",
    "bootstrap_theme_name",
    "create_style",
    "dark_theme_settings",
    "is_bootstrap",
    "polish_active_theme",
    "system_prefers_dark",
]
