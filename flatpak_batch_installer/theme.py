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


__all__ = ["dark_theme_settings", "polish_active_theme", "system_prefers_dark"]
