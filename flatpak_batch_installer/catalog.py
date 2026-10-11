"""Catalog parsing, filtering, pagination and selection persistence."""

import math
import re

from .models import App

# Valid Flatpak app-ID pattern: starts with an alphanumeric character, then
# allows alphanumeric, dot, underscore, or hyphen characters.
_APP_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')


def parse_remote_ls(output: str) -> list[App]:
    """Parse ``flatpak remote-ls --columns=application,name,description``."""
    rows = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        app_id = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 else ""
        summary = parts[2].strip() if len(parts) > 2 else ""
        if app_id:
            rows.append(App(app_id=app_id, name=name, summary=summary))
    return rows


def filter_rows(
    rows: list[App],
    query: str,
    installed: set[str] | None = None,
    status_filter: str = "all",
    selected: set[str] | None = None,
) -> list[App]:
    """Filter catalog rows.

    ``status_filter`` is one of ``all`` | ``installed`` | ``not-installed``
    | ``selected``. ``installed``/``selected`` are sets of app IDs.
    """
    query = (query or "")[:200]
    out = []
    for app in rows:
        if status_filter == "installed" and (
                installed is None or app.app_id not in installed):
            continue
        if status_filter == "not-installed" and (
                installed is not None and app.app_id in installed):
            continue
        if status_filter == "selected" and (
                selected is None or app.app_id not in selected):
            continue
        if not app.matches(query):
            continue
        out.append(app)
    return out


def paginate(
    items: list,
    page: int,
    page_size: int,
) -> tuple[list, int, int]:
    """Slice items into pages. Returns ``(page_items, total_pages, page)``.

    Out-of-range pages are clamped to the nearest valid page.
    """
    size = max(1, int(page_size or 1))
    items = list(items)
    if not items:
        return [], 0, 0
    total_pages = math.ceil(len(items) / size)
    clamped = max(0, min(int(page), total_pages - 1))
    start = clamped * size
    return items[start:start + size], total_pages, clamped


def save_selection(app_ids: list[str], path: str) -> None:
    """Save app IDs to a plain-text file, one per line.

    Blank/whitespace-only entries and duplicates are silently skipped.
    Order of first occurrence is preserved.
    """
    seen: set[str] = set()
    with open(path, "w", encoding="utf-8") as fh:
        for app_id in app_ids:
            stripped = app_id.strip()
            if stripped and stripped not in seen:
                seen.add(stripped)
                fh.write(stripped + "\n")


def load_selection(path: str) -> tuple[list[str], int]:
    """Load app IDs from a file. Blank lines and ``#`` comments ignored.

    Duplicates are removed, order is kept.  Entries that do not look like
    valid Flatpak app IDs are silently dropped (e.g. shell-injection
    attempts such as ``--assumeyes`` or ``; rm -rf ~``).

    Returns a ``(ids, skipped_count)`` tuple where ``skipped_count`` is
    the number of lines that were dropped due to invalid app-ID format.
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw = [ln.strip() for ln in fh
               if ln.strip() and not ln.startswith("#")]
    seen: set[str] = set()
    unique: list[str] = []
    skipped = 0
    for app_id in raw:
        if not _APP_ID_RE.match(app_id):
            skipped += 1
            continue
        if app_id not in seen:
            seen.add(app_id)
            unique.append(app_id)
    return unique, skipped


__all__ = [
    "filter_rows",
    "load_selection",
    "paginate",
    "parse_remote_ls",
    "save_selection",
]
