"""Models for Audiobookshelf."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class EbookFile:
    """Normalized ebook file metadata."""

    item_id: str
    title: str
    authors: list[str]

    @property
    def display_title(self) -> str:
        """Return a human-friendly title."""
        if self.authors:
            return f"{self.title} - {', '.join(self.authors)}"
        return self.title


@dataclass(slots=True)
class SendResult:
    """Result of an Audiobookshelf e-reader send attempt."""

    item_id: str
    title: str
    device_name: str | None
    sent: bool
    skipped: bool
    reason: str | None = None


def normalize_ebook(item: dict[str, Any]) -> EbookFile:
    """Extract ebook metadata from an Audiobookshelf library item."""
    media = item.get("media") or {}
    metadata = media.get("metadata") or {}
    if not (media.get("ebookFile") or item.get("ebookFile")):
        from .exceptions import MissingEbook

        raise MissingEbook("Audiobookshelf item has no ebookFile")

    title = metadata.get("title") or item.get("title") or item.get("id") or "Unknown book"
    authors_value = metadata.get("authors") or metadata.get("authorName") or []
    if isinstance(authors_value, str):
        authors = [authors_value]
    elif isinstance(authors_value, list):
        authors = [str(author.get("name", author)) for author in authors_value]
    else:
        authors = []

    return EbookFile(
        item_id=str(item["id"]),
        title=str(title),
        authors=authors,
    )
