"""Models for Audiobookshelf Kindle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class EbookFile:
    """Normalized ebook file metadata."""

    item_id: str
    title: str
    authors: list[str]
    format: str
    filename: str
    path: str | None
    size: int | None

    @property
    def display_title(self) -> str:
        """Return a human-friendly title."""
        if self.authors:
            return f"{self.title} - {', '.join(self.authors)}"
        return self.title


@dataclass(slots=True)
class SendResult:
    """Result of a Kindle send attempt."""

    item_id: str
    title: str
    sent: bool
    skipped: bool
    reason: str | None = None
    filename: str | None = None


def normalize_ebook(item: dict[str, Any]) -> EbookFile:
    """Extract ebook metadata from an Audiobookshelf library item."""
    media = item.get("media") or {}
    metadata = media.get("metadata") or {}
    ebook = media.get("ebookFile") or item.get("ebookFile")
    if not ebook:
        from .exceptions import MissingEbook

        raise MissingEbook("Audiobookshelf item has no ebookFile")

    file_meta = ebook.get("metadata") or {}
    title = metadata.get("title") or item.get("title") or item.get("id") or "Unknown book"
    authors_value = metadata.get("authors") or metadata.get("authorName") or []
    if isinstance(authors_value, str):
        authors = [authors_value]
    elif isinstance(authors_value, list):
        authors = [str(author.get("name", author)) for author in authors_value]
    else:
        authors = []

    file_path = file_meta.get("path")
    filename = file_meta.get("filename") or (Path(file_path).name if file_path else f"{title}.epub")
    ebook_format = ebook.get("ebookFormat") or file_meta.get("ext", "").lstrip(".") or Path(filename).suffix.lstrip(".")

    return EbookFile(
        item_id=str(item["id"]),
        title=str(title),
        authors=authors,
        format=str(ebook_format).lower(),
        filename=str(filename),
        path=str(file_path) if file_path else None,
        size=int(file_meta["size"]) if file_meta.get("size") is not None else None,
    )
