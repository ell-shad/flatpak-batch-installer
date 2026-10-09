"""Domain models (stdlib only)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class App:
    """One Flathub application entry from the local catalog metadata."""

    app_id: str
    name: str = ""
    summary: str = ""

    @property
    def display_name(self) -> str:
        return self.name or self.app_id

    def matches(self, query: str) -> bool:
        """Case-insensitive match against app ID, name and summary."""
        q = (query or "").strip().lower()
        if not q:
            return True
        return q in f"{self.app_id} {self.name} {self.summary}".lower()
