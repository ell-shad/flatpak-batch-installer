"""In-app documentation: usage guide (Help) and About text.

Kept as plain data so it is unit-testable without a display and reusable
from the CLI (``flatpak-batch-installer --help-guide`` prints the guide).
"""

USAGE_GUIDE = """\
Flatpak Batch Installer — How to use
======================================

WHAT THIS APP DOES
  Browse the Flathub application catalog, tick the apps you want, and
  install them all with one Flatpak command. Handy after a fresh Linux
  install or when setting up several machines the same way. Everything the
  app does is a standard `flatpak` command — the exact command is always
  shown in the log area before it runs.

WORKFLOW IN 5 STEPS
  1. Pick Scope: "user" (recommended, needs no root) or "system".
  2. Click "Load catalog". First load takes a few seconds.
  3. Type in Filter to narrow the list; flip through pages with < Prev
     and Next >. Your ticks are kept when you change pages.
  4. Tick apps in the checkbox column (click it, or focus a row and press
     Space). The "Selected: N apps" counter tracks your picks.
  5. Click "Install selected", review the confirmation list, confirm.
     Watch progress in the log area at the bottom.

WHAT IS WHAT
  Load catalog .... Load the Flathub app list for the chosen scope.
  Update .......... Refresh Flatpak's AppStream metadata
                    (`flatpak update --appstream flathub`), then reload.
                    Use it when names/summaries show up empty.
  Scope ........... user = install for you only (no root);
                    system = install for all users (may need root).
  Status .......... View filter: all / installed / not-installed apps,
                    or only the ones you ticked (selected).
  Install selected  Install everything ticked, in ONE flatpak call.
                    Always asks for confirmation first.
  Dark mode ....... Switch the light/dark theme — modern Bootstrap-style
                    themes when ttkbootstrap is installed, built-in
                    themes otherwise (auto-detects yours).
  Help ............ This guide (How to use / About) — or press F1.
  Filter .......... Live search across app name, app ID and summary.
  Select page ..... Tick every app on the current page.
  Clear ........... Untick everything.
  Save… / Load… ... Save your ticked app IDs to a text file (one per
                    line) and load them back later — great for cloning
                    a setup onto another machine.
  Table columns ... [✓] your ticks · Status (Installed or blank) ·
                    Name · App ID · Summary.
  < Prev / Next > . Flip through catalog pages. Rows/page sets the
                    page size (100/200/500).
  Details line .... Shows ID, name, status and summary of the focused row.
  Log area ........ Every flatpak command plus its full output.
                    The spinner + "Working…" (top right) only means a
                    background job is running — it is not a progress %.

KEYBOARD SHORTCUTS
  F1 ............ Open this guide.
  F5 ............ Reload the catalog.
  Ctrl+F ........ Jump to the Filter box.
  Ctrl+S / Ctrl+O  Save / load the selection file.
  Ctrl+Enter .... Install selected (asks first, as always).
  Ctrl+A ........ Tick the whole current page (in the table).
  Space ......... Tick/untick the focused rows (in the table).
  Esc ........... Clear the filter (in the Filter box).

TYPICAL FIXES
  Names/summaries empty ... Click Update (fetches AppStream metadata).
  "Remote not found" ...... Add Flathub, then Update:
      flatpak --user remote-add --if-not-exists flathub \\
          https://dl.flathub.org/repo/flathub.flatpakrepo
  "Permission denied" ..... Switch Scope to "user".
  Already installed? ...... The Status column says "Installed"; filter
                            Status to "not-installed" to hide those.
"""

HOMEPAGE = "https://github.com/example/flatpak-batch-installer"
ISSUES = "https://github.com/example/flatpak-batch-installer/issues"


def about_text(version: str) -> str:
    """Short About text with the running version filled in."""
    return (
        "Flatpak Batch Installer\n"
        f"Version {version}\n"
        "\n"
        "Browse the Flathub catalog, select many apps,\n"
        "install them all with one Flatpak command.\n"
        "\n"
        "GNU GPLv3 or later — Flatpak Batch Installer contributors.\n"
        "Built with Python + Tkinter (standard library only).\n"
        "\n"
        f"{HOMEPAGE}\n"
        f"{ISSUES}"
    )


__all__ = ["HOMEPAGE", "ISSUES", "USAGE_GUIDE", "about_text"]
