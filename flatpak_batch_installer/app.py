"""Application entry point: CLI mode and GUI launcher."""

import argparse
import subprocess
import sys
import tkinter as tk

from . import __version__
from .config import DEFAULT_SCOPE, REMOTE
from .catalog import filter_rows
from .flatpak import (
    build_install_cmd,
    get_installed,
    get_installed_union,
    load_catalog,
)


def run_cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="flatpak-batch-installer",
        description=f"Flatpak Batch Installer v{__version__} "
                    "(GUI by default; --list/--installed/--install for CLI use)")
    parser.add_argument("--scope", choices=["user", "system"],
                        default=DEFAULT_SCOPE,
                        help="flatpak installation scope (default: %(default)s)")
    parser.add_argument("--list", action="store_true",
                        help="list catalog apps (one per line: ID, name, summary)")
    parser.add_argument("--search", default="",
                        help="filter text for --list")
    parser.add_argument("--installed", action="store_true",
                        help="list installed app IDs for the given scope")
    parser.add_argument("--install", nargs="*", default=None, metavar="APP_ID",
                        help="install given app IDs (batch, one flatpak call)")
    parser.add_argument("-V", "--version", action="version",
                        version=f"%(prog)s {__version__}")
    parser.add_argument("--help-guide", action="store_true",
                        help="print the in-app usage guide and exit")
    args = parser.parse_args(argv)

    if args.help_guide:
        from .helptext import USAGE_GUIDE
        print(USAGE_GUIDE)
        return 0

    if args.installed:
        ids, err = get_installed(args.scope)
        if err:
            print(f"Error: {err}", file=sys.stderr)
            return 1
        for app_id in sorted(ids):
            print(app_id)
        return 0

    if args.install is not None:
        if not args.install:
            print("Error: --install needs at least one app ID.", file=sys.stderr)
            return 2
        cmd = build_install_cmd(args.scope, REMOTE, args.install)
        print("Running: " + " ".join(cmd))
        proc = subprocess.run(cmd)
        return proc.returncode

    if args.list:
        rows, err = load_catalog(args.scope)
        if err:
            print(f"Error: {err}", file=sys.stderr)
            return 1
        installed, _ = get_installed_union()
        for app in filter_rows(rows, args.search, installed):
            print(f"{app.app_id}\t{app.name}\t{app.summary}")
        return 0

    parser.print_help()
    return 0


def run_gui() -> int:
    from .ui import FlathubBrowser
    try:
        FlathubBrowser().mainloop()
    except tk.TclError as exc:
        print(f"Cannot start GUI (no display?): {exc}", file=sys.stderr)
        print("Headless alternative: flatpak-batch-installer --list --search TEXT", file=sys.stderr)
        return 1
    return 0


def main(argv=None) -> int:
    cli_args = argv if argv is not None else sys.argv[1:]
    if cli_args and cli_args[0].startswith("-"):
        return run_cli(cli_args)
    return run_gui()


__all__ = ["main", "run_cli", "run_gui"]
