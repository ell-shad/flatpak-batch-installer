"""Shared configuration constants for the Flathub Catalog Installer."""

#: Flatpak remote to browse and install from.
REMOTE = "flathub"

#: Default install scope. ``"user"`` is the safe default: it avoids
#: system-wide permission problems. The GUI offers a user/system switch.
DEFAULT_SCOPE = "user"

#: Rows shown per table page in the GUI (changeable at runtime).
PAGE_SIZE = 200

#: Checkbox glyphs used in the GUI table's selection column.
CHECKED = "☑"
UNCHECKED = "☐"

#: Name of the ttk theme registered for dark mode.
DARK_THEME_NAME = "flathub-dark"

#: Dark-mode palette (plain color strings; no external theme dependency).
DARK_COLORS = {
    "bg": "#2b2b2b",        # windows, frames, labels
    "bg_alt": "#1e1e1e",    # entries, table body, log
    "bg_btn": "#3d3d3d",    # buttons, table headers
    "bg_hover": "#4d4d4d",
    "fg": "#e8e8e8",
    "fg_dim": "#9a9a9a",
    "accent": "#0d47a1",    # selected row
    "accent_fg": "#ffffff",
    "border": "#555555",
}

#: Accent color for the primary action button in light mode
#: (dark mode reuses DARK_COLORS["accent"]).
LIGHT_ACCENT = "#0b5ed7"
LIGHT_ACCENT_ACTIVE = "#0a58c4"
ACCENT_FG = "#ffffff"

#: Alternating table-row backgrounds per mode (even, odd).
LIGHT_STRIPES = ("#ffffff", "#eef3f9")
DARK_STRIPES = ("#1e1e1e", "#272c34")
