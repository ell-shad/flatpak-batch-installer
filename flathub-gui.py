#!/usr/bin/env python3
"""Deprecated alias of flatpak-gui.py (kept for backward compatibility)."""

import sys
import warnings

warnings.warn(
    "flathub-gui.py is deprecated, use flatpak-gui.py instead.",
    DeprecationWarning,
    stacklevel=2,
)

from flatpak_batch_installer.app import main

if __name__ == "__main__":
    sys.exit(main())
