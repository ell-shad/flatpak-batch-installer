#!/usr/bin/env python3
"""Flatpak Batch Installer launcher.

GUI:  python3 flatpak-gui.py
CLI:  python3 flatpak-gui.py --list [--scope user|system] [--search TEXT]
      python3 flatpak-gui.py --installed [--scope user|system]
      python3 flatpak-gui.py --install APP_ID [APP_ID ...] [--scope user|system]
"""

import sys

from flatpak_batch_installer.app import main

if __name__ == "__main__":
    sys.exit(main())
