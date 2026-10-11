"""Catalog parsing, filtering, pagination and selection persistence."""

import json
import math
import re

from .models import App

# Valid Flatpak app-ID pattern: starts with an alphanumeric character, then
# allows alphanumeric, dot, underscore, or hyphen characters.
_APP_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')

#: Map of app-ID prefixes to human-readable category names.
CATEGORY_MAP: dict[str, str] = {
    "org.gnome.": "GNOME",
    "org.kde.": "KDE",
    "com.valvesoftware.": "Gaming",
    "org.libreoffice.": "Office",
    "org.mozilla.": "Internet",
    "com.google.": "Internet",
    "org.gimp.": "Graphics",
    "org.inkscape.": "Graphics",
    "org.audacityteam.": "Audio",
    "net.lutris.": "Gaming",
}


def _categorize(app_id: str) -> str:
    """Return a category name for an app ID, or 'Other'."""
    for prefix, category in CATEGORY_MAP.items():
        if app_id.startswith(prefix):
            return category
    return "Other"


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
            rows.append(App(app_id=app_id, name=name, summary=summary,
                            category=_categorize(app_id)))
    return rows


def filter_rows(
    rows: list[App],
    query: str,
    installed: set[str] | None = None,
    status_filter: str = "all",
    selected: set[str] | None = None,
    category: str | None = None,
) -> list[App]:
    """Filter catalog rows.

    ``status_filter`` is one of ``all`` | ``installed`` | ``not-installed``
    | ``selected``. ``installed``/``selected`` are sets of app IDs.
    ``category`` when set to a non-None string filters to that category only.
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
        if category is not None and app.category != category:
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
    """Save app IDs to a file, one per line (plain text) or as JSON.

    If *path* ends with ``.json``, writes a JSON array.  Otherwise writes
    plain text (one ID per line).

    Blank/whitespace-only entries and duplicates are silently skipped.
    Order of first occurrence is preserved.
    """
    seen: set[str] = set()
    unique: list[str] = []
    for app_id in app_ids:
        stripped = app_id.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            unique.append(stripped)

    if path.lower().endswith(".json"):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(unique, indent=2))
            fh.write("\n")
    else:
        with open(path, "w", encoding="utf-8") as fh:
            for app_id in unique:
                fh.write(app_id + "\n")


def load_selection(path: str) -> tuple[list[str], int]:
    """Load app IDs from a file (plain text or JSON).

    For JSON files (*path* ends with ``.json``) the file must contain a
    JSON array of strings; each entry is validated as a Flatpak app ID.

    For plain-text files blank lines and ``#`` comments are ignored.

    Duplicates are removed, order is kept.  Entries that do not look like
    valid Flatpak app IDs are silently dropped (e.g. shell-injection
    attempts such as ``--assumeyes`` or ``; rm -rf ~``).

    Returns a ``(ids, skipped_count)`` tuple where ``skipped_count`` is
    the number of lines that were dropped due to invalid app-ID format.
    """
    if path.lower().endswith(".json"):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.loads(fh.read())
        if not isinstance(data, list):
            raise ValueError("JSON selection file must contain a JSON array.")
        raw = [item for item in data if isinstance(item, str) and item]
    else:
        with open(path, "r", encoding="utf-8") as fh:
            raw = [ln.strip() for ln in fh
                   if ln.strip() and not ln.startswith("#")]

    seen: set[str] = set()
    unique: list[str] = []
    skipped = 0
    for app_id in raw:
        app_id = app_id.strip()
        if not app_id:
            skipped += 1
            continue
        if not _APP_ID_RE.match(app_id):
            skipped += 1
            continue
        if app_id not in seen:
            seen.add(app_id)
            unique.append(app_id)
    return unique, skipped


__all__ = [
    "CATEGORY_MAP",
    "filter_rows",
    "load_selection",
    "paginate",
    "parse_remote_ls",
    "save_selection",
]
