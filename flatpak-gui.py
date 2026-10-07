#!/usr/bin/env python3
"""Deprecated alias of flathub-gui.py (kept for backward compatibility)."""

import sys
import warnings

warnings.warn(
    "flatpak-gui.py is deprecated, use flathub-gui.py instead.",
    DeprecationWarning,
    stacklevel=2,
)

from flathub_gui.app import main

if __name__ == "__main__":
    sys.exit(main())
