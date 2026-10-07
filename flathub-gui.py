#!/usr/bin/env python3
"""Flathub Catalog Installer launcher.

GUI:  python3 flathub-gui.py
CLI:  python3 flathub-gui.py --list [--scope user|system] [--search TEXT]
      python3 flathub-gui.py --installed [--scope user|system]
      python3 flathub-gui.py --install APP_ID [APP_ID ...] [--scope user|system]
"""

import sys

from flathub_gui.app import main

if __name__ == "__main__":
    sys.exit(main())
