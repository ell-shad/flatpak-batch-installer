"""Dark-mode support using stdlib ``ttk.Style`` only.

No external theme libraries, no images, no extra processes: just one
registered ttk theme variant plus plain color strings. Memory impact is a
few kilobytes of style definitions.
"""

import os
import subprocess

from .config import DARK_COLORS


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


__all__ = ["dark_theme_settings", "system_prefers_dark"]
