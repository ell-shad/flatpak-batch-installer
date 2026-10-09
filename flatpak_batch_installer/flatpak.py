"""Safe wrappers around the ``flatpak`` CLI.

All Flatpak interaction goes through this module so output parsing and
error diagnosis live in one place. Nothing here depends on the GUI, which
keeps these helpers usable from the CLI and unit-testable headless.
"""

import subprocess

from .catalog import parse_remote_ls
from .config import REMOTE
from .models import App


def scope_args(scope: str) -> list:
    """Return the flatpak scope flag list for ``"user"`` or ``"system"``.

    An explicit scope is required: when Flathub exists in both
    installations a bare ``flatpak remote-ls flathub`` prompts
    interactively instead of listing.
    """
    if scope == "user":
        return ["--user"]
    if scope == "system":
        return ["--system"]
    raise ValueError(f"unknown scope: {scope!r} (expected 'user' or 'system')")


def run_flatpak(args: list, timeout: int = 120):
    """Run a flatpak command, returning a CompletedProcess-like result.

    Never raises FileNotFoundError: a missing executable is reported as
    returncode 127 with an explanatory stderr.
    """
    try:
        return subprocess.run(
            ["flatpak", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            args=["flatpak", *args],
            returncode=127,
            stdout="",
            stderr="flatpak executable not found. Install Flatpak first.",
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=["flatpak", *args],
            returncode=124,
            stdout="",
            stderr="flatpak command timed out.",
        )


def diagnose_catalog_error(stderr: str, scope: str, remote: str = REMOTE) -> str:
    """Map a failed ``remote-ls`` stderr to a user-friendly message."""
    err = (stderr or "").strip()
    low = err.lower()
    scope_flag = "--user " if scope == "user" else ""
    update_hint = f"flatpak {scope_flag}update --appstream {remote}".replace("  ", " ")
    if "not found" in low and "remote" in low:
        return (
            f"Remote '{remote}' not found for scope '{scope}'.\n"
            f"Add it with:\n  flatpak {scope_flag}remote-add --if-not-exists "
            f"{remote} https://dl.flathub.org/repo/flathub.flatpakrepo\n"
            f"Then refresh metadata:\n  {update_hint}\n"
            f"Details: {err}"
        )
    if "multiple installations" in low or "found in multiple" in low:
        return (
            "Flatpak found the remote in multiple installations.\n"
            "Pick an explicit scope (User or System) and reload.\n"
            f"Details: {err}"
        )
    if "no such" in low or "no remote" in low:
        return f"Remote error: {err}\nHint: run `{update_hint}` first."
    if "network" in low or "couldn't resolve" in low or "connection" in low:
        return f"Network error while loading catalog: {err}"
    if "permission" in low or "denied" in low:
        return (
            f"Permission denied: {err}\n"
            "Hint: switch Install scope to 'User' to avoid needing root."
        )
    base = err or "flatpak remote-ls failed with no error message."
    return (
        f"{base}\n"
        f"Hint: run `{update_hint}` first.\n"
        "For system metadata the update may need root/sudo."
    )


def load_catalog(scope: str, remote: str = REMOTE, timeout: int = 180):
    """Load catalog entries. Returns ``(list[App], error_message | None)``."""
    try:
        sargs = scope_args(scope)
    except ValueError as exc:
        return [], str(exc)
    result = run_flatpak(
        [*sargs, "remote-ls", remote, "--app",
         "--columns=application,name,description"],
        timeout=timeout,
    )
    if result.returncode != 0:
        return [], diagnose_catalog_error(result.stderr, scope, remote)
    rows = parse_remote_ls(result.stdout)
    if not rows:
        err = (result.stderr.strip() if result.stderr else "") or \
            "Catalog is empty. AppStream metadata may be missing.\n" \
            f"Try: flatpak {'--user ' if scope == 'user' else ''}" \
            f"update --appstream {remote}"
        return [], err
    return rows, None


def get_installed(scope: str, timeout: int = 60):
    """Return ``(set_of_app_ids, error | None)`` for one scope."""
    try:
        sargs = scope_args(scope)
    except ValueError as exc:
        return set(), str(exc)
    result = run_flatpak(
        [*sargs, "list", "--app", "--columns=application"], timeout=timeout)
    if result.returncode != 0:
        return set(), (result.stderr.strip() or "flatpak list failed.")
    ids = {ln.strip() for ln in result.stdout.splitlines() if ln.strip()}
    return ids, None


def get_installed_union(timeout: int = 60):
    """Installed apps across both scopes. Returns ``(set, {scope: error})``."""
    installed = set()
    errors = {}
    for scope in ("user", "system"):
        ids, err = get_installed(scope, timeout=timeout)
        installed |= ids
        if err:
            errors[scope] = err
    return installed, errors


def build_install_cmd(scope: str, remote: str, app_ids: list) -> list:
    """Build a single batch ``flatpak install`` command.

    Duplicates are removed (order kept); empty IDs are dropped.
    """
    seen = set()
    unique = []
    for app_id in app_ids:
        if app_id and app_id not in seen:
            seen.add(app_id)
            unique.append(app_id)
    return [
        "flatpak", *scope_args(scope), "install",
        "--assumeyes", "--noninteractive", remote, *unique,
    ]


__all__ = [
    "App",
    "build_install_cmd",
    "diagnose_catalog_error",
    "get_installed",
    "get_installed_union",
    "load_catalog",
    "run_flatpak",
    "scope_args",
]
