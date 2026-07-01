"""Runtime manager for Audiobookshelf."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from .api import AudiobookshelfClient
from .const import (
    CONF_AUTO_SEND,
    CONF_DEVICE_NAME,
    DOMAIN,
    EVENT_LIBRARY_ITEM_RECEIVED,
    EVENT_LIBRARY_ITEM_UNKNOWN,
    EVENT_LIBRARY_ITEM_UPDATED,
    EVENT_ITEM_RECEIVED,
    ISSUE_MISSING_EBOOK,
    ISSUE_MISSING_DEVICE,
    ISSUE_SEND_FAILED,
    STORAGE_KEY,
    STORAGE_VERSION,
    SIGNAL_UPDATED,
)
from .exceptions import (
    AudiobookshelfError,
    CannotConnect,
    MissingDevice,
    MissingEbook,
    SendFailed,
)
from .models import SendResult, normalize_ebook

_LOGGER = logging.getLogger(__name__)


class AudiobookshelfManager:
    """Coordinate ABS polling, library item events, and e-reader device sends."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AudiobookshelfClient,
    ) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.entry = entry
        self.client = client
        self.last_result: SendResult | None = None
        self.last_event: dict[str, Any] | None = None
        self.server_status: dict[str, Any] = {}
        self.ereader_devices: list[dict[str, Any]] = []
        self.book_libraries: dict[str, dict[str, Any]] = {}
        self.recently_added_books_by_library: dict[str, dict[str, Any] | None] = {}
        self.last_refresh = None
        self._recent_item_ids: dict[str, str] = {}
        self._event_id = 0
        self.sent_count = 0
        self.skipped_count = 0
        self.failed_count = 0
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._sent_items: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        """Load persisted sent item state."""
        stored = await self._store.async_load()
        self._sent_items = dict((stored or {}).get(self.entry.entry_id, {}))
        self.sent_count = len(self._sent_items)

    async def async_refresh(self) -> None:
        """Refresh server status, e-reader devices, and library contents.

        Newly added books are detected by comparing each library's most recently
        added item against the previous poll; ABS has no library-item webhook.
        """
        try:
            self.server_status = await self.client.async_get_status()
        except CannotConnect:
            _LOGGER.debug("Could not refresh Audiobookshelf server status", exc_info=True)
            self.server_status = {}
        self.ereader_devices = await self.client.async_get_ereader_devices()
        libraries = await self.client.async_get_libraries()
        self.book_libraries = {
            str(library["id"]): library
            for library in libraries
            if isinstance(library, dict) and library.get("id") and library.get("mediaType") == "book"
        }
        recently_added: dict[str, dict[str, Any] | None] = {}
        for library_id, library in self.book_libraries.items():
            library_name = library.get("name")
            try:
                item = await self.client.async_get_recently_added_book_for_library(library_id, library_name)
            except CannotConnect:
                _LOGGER.debug("Could not refresh Audiobookshelf recently added book for %s", library_id, exc_info=True)
                item = None
            recently_added[library_id] = _normalize_recently_added_book(item, library)
        self.recently_added_books_by_library = recently_added
        self.last_refresh = dt_util.utcnow()
        await self._async_detect_new_books(recently_added)
        self._async_write_state()

    async def _async_detect_new_books(
        self,
        recently_added: dict[str, dict[str, Any] | None],
    ) -> None:
        """Fire an event (and optionally auto-send) for newly added books.

        The first observation of a library only seeds the baseline, so an
        integration restart never re-fires or re-sends existing items.
        """
        for library_id, book in recently_added.items():
            item_id = (book or {}).get("item_id")
            if not item_id:
                continue
            item_id = str(item_id)
            previous = self._recent_item_ids.get(library_id)
            self._recent_item_ids[library_id] = item_id
            if previous is None or item_id == previous:
                continue
            await self._async_handle_new_book(item_id)

    async def _async_handle_new_book(self, item_id: str) -> None:
        """Publish a library item event and auto-send when enabled."""
        self._event_id += 1
        item_detail = await self._async_fetch_item_detail(item_id)
        event = _normalize_event(
            self.entry.entry_id,
            self._event_id,
            item_id,
            {},
            item_detail=item_detail,
            libraries=self.book_libraries,
            base_url=self.client.base_url,
            source_event="library_item_added",
        )
        self.last_event = event
        self.hass.bus.async_fire(EVENT_ITEM_RECEIVED, event)
        if not self.entry.options.get(CONF_AUTO_SEND, False):
            return
        try:
            await self.async_send_ebook_to_device(item_id, source="poll")
        except AudiobookshelfError:
            _LOGGER.debug("Auto-send failed for Audiobookshelf item %s", item_id, exc_info=True)

    async def async_save(self) -> None:
        """Persist sent item state."""
        stored = await self._store.async_load() or {}
        stored[self.entry.entry_id] = self._sent_items
        await self._store.async_save(stored)

    async def async_reset_sent_item(self, item_id: str, device_name: str | None = None) -> bool:
        """Remove a sent marker so an item can be resent."""
        key = self._sent_key(item_id, device_name)
        existed = self._sent_items.pop(key, None) is not None
        if existed:
            self.sent_count = len(self._sent_items)
            await self.async_save()
        return existed

    async def _async_fetch_item_detail(self, item_id: str) -> dict[str, Any] | None:
        """Best-effort fetch of full item metadata to enrich library item events.

        Any failure is non-fatal: the event still fires with whatever data the
        poll already gathered.
        """
        try:
            item = await self.client.async_get_item(item_id)
        except AudiobookshelfError:
            _LOGGER.debug(
                "Could not fetch Audiobookshelf item %s for event enrichment",
                item_id,
                exc_info=True,
            )
            return None
        return item if isinstance(item, dict) else None

    async def async_send_ebook_to_device(
        self,
        item_id: str,
        *,
        device_name: str | None = None,
        force: bool = False,
        source: str = "service",
    ) -> SendResult:
        """Ask Audiobookshelf to send an item to an e-reader device."""
        resolved_device_name = device_name or self.entry.options.get(CONF_DEVICE_NAME)
        if not resolved_device_name:
            err = MissingDevice("No Audiobookshelf e-reader device is configured")
            self.failed_count += 1
            self._create_issue(ISSUE_MISSING_DEVICE, str(err))
            raise err

        sent_key = self._sent_key(item_id, resolved_device_name)
        if not force and sent_key in self._sent_items:
            result = SendResult(
                item_id=item_id,
                title=self._sent_items[sent_key].get("title", item_id),
                device_name=resolved_device_name,
                sent=False,
                skipped=True,
                reason="already_sent",
            )
            self.last_result = result
            self.skipped_count += 1
            self._async_write_state()
            return result

        try:
            item = await self.client.async_get_item(item_id)
            ebook = normalize_ebook(item)
            await self.client.async_send_ebook_to_device(item_id, resolved_device_name)
        except MissingEbook as err:
            self.failed_count += 1
            self._create_issue(ISSUE_MISSING_EBOOK, str(err))
            raise
        except SendFailed as err:
            self.failed_count += 1
            self._create_issue(ISSUE_SEND_FAILED, str(err))
            raise

        self._sent_items[sent_key] = {
            "title": ebook.display_title,
            "device_name": resolved_device_name,
            "source": source,
        }
        self.sent_count = len(self._sent_items)
        await self.async_save()
        self._delete_send_issues()
        result = SendResult(
            item_id=item_id,
            title=ebook.display_title,
            device_name=resolved_device_name,
            sent=True,
            skipped=False,
        )
        self.last_result = result
        self._async_write_state()
        return result

    async def async_send_item(self, item_id: str, *, force: bool = False, source: str = "service") -> SendResult:
        """Backward-compatible wrapper for older service callers."""
        return await self.async_send_ebook_to_device(item_id, force=force, source=source)

    async def async_send_last_ebook_to_device(self) -> SendResult:
        """Send the latest ebook to the default e-reader device.

        Prefers the most recently detected event item; otherwise falls back to
        the newest recently added book across libraries, so the button works even
        before any new-book event has fired.
        """
        item_id: str | None = None
        if self.last_event and self.last_event.get("item_id"):
            item_id = str(self.last_event["item_id"])
        else:
            item_id = self._most_recently_added_item_id()
        if not item_id:
            raise SendFailed("No Audiobookshelf library item is available yet")
        return await self.async_send_ebook_to_device(item_id, force=True, source="button")

    def _most_recently_added_item_id(self) -> str | None:
        """Return the newest recently added book id, preferring items with an ebook."""
        candidates = [
            book
            for book in self.recently_added_books_by_library.values()
            if book and book.get("item_id")
        ]
        if not candidates:
            return None
        pool = [book for book in candidates if book.get("has_ebook")] or candidates
        newest = max(pool, key=lambda book: book.get("added_at") or 0)
        return str(newest["item_id"])

    async def async_set_default_device(self, device_name: str) -> None:
        """Persist the default e-reader device selected from the entity."""
        options = dict(self.entry.options)
        options[CONF_DEVICE_NAME] = device_name
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self._async_write_state()

    @property
    def default_device_name(self) -> str | None:
        """Return the configured default e-reader device."""
        return self.entry.options.get(CONF_DEVICE_NAME)

    @property
    def ereader_device_names(self) -> list[str]:
        """Return configured e-reader device names."""
        return [
            str(device["name"])
            for device in self.ereader_devices
            if isinstance(device, dict) and device.get("name")
        ]

    def _async_write_state(self) -> None:
        """Notify entities that manager state changed."""
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

    @staticmethod
    def _sent_key(item_id: str, device_name: str | None = None) -> str:
        """Return a per-device sent marker key."""
        return item_id if not device_name else f"{item_id}:{device_name}"

    def _create_issue(self, issue_id: str, detail: str) -> None:
        """Create a repair issue for send failures."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"{self.entry.entry_id}_{issue_id}",
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=issue_id,
            translation_placeholders={"detail": detail},
        )

    def _delete_send_issues(self) -> None:
        """Clear transient send issues after a successful send."""
        for issue_id in (ISSUE_MISSING_EBOOK, ISSUE_MISSING_DEVICE, ISSUE_SEND_FAILED):
            ir.async_delete_issue(self.hass, DOMAIN, f"{self.entry.entry_id}_{issue_id}")


def _normalize_event(
    entry_id: str,
    event_id: int,
    item_id: str,
    payload: dict[str, Any],
    *,
    item_detail: dict[str, Any] | None = None,
    libraries: dict[str, dict[str, Any]] | None = None,
    base_url: str | None = None,
    source_event: str | None = None,
) -> dict[str, Any]:
    """Normalize an ABS library item into stable HA event attributes.

    ``item_detail`` (fetched from ``/api/items/{id}``) is preferred over the raw
    ``payload`` when available, so automations get consistent metadata. Pass
    ``source_event`` to label the event origin explicitly.
    """
    item = item_detail if isinstance(item_detail, dict) and item_detail else _extract_item(payload)
    media = item.get("media") if isinstance(item.get("media"), dict) else {}
    metadata = media.get("metadata") if isinstance(media.get("metadata"), dict) else {}
    source_event = source_event or _extract_source_event(payload)
    event_type = _event_type_from_source(source_event)

    library_id = (
        item.get("libraryId")
        or payload.get("libraryId")
        or payload.get("library_id")
    )
    library_name = _resolve_library_name(library_id, libraries)
    ebook_file = media.get("ebookFile") or item.get("ebookFile")

    return {
        "entry_id": entry_id,
        "event_id": event_id,
        "event_type": event_type,
        "source_event": source_event,
        "item_id": item_id,
        "library_id": library_id,
        "library_name": library_name,
        "title": metadata.get("title") or item.get("title"),
        "subtitle": metadata.get("subtitle"),
        "authors": _extract_authors(metadata),
        "narrators": _extract_str_list(metadata.get("narrators")),
        "series": _extract_series(metadata),
        "genres": _extract_str_list(metadata.get("genres")),
        "published_year": metadata.get("publishedYear"),
        "publisher": metadata.get("publisher"),
        "description": metadata.get("description"),
        "media_type": media.get("mediaType") or item.get("mediaType"),
        "has_ebook": bool(ebook_file),
        "ebook_format": _extract_ebook_format(ebook_file, media),
        "duration": media.get("duration"),
        "added_at": item.get("addedAt") or item.get("createdAt"),
        "updated_at": item.get("updatedAt"),
        "cover_url": _build_item_url(base_url, item_id, cover=True),
        "item_url": _build_item_url(base_url, item_id),
    }


def _resolve_library_name(
    library_id: Any,
    libraries: dict[str, dict[str, Any]] | None,
) -> str | None:
    """Resolve a human-friendly library name from cached libraries."""
    if not library_id or not libraries:
        return None
    library = libraries.get(str(library_id))
    if isinstance(library, dict):
        name = library.get("name")
        return str(name) if name else None
    return None


def _extract_str_list(value: Any) -> list[str]:
    """Normalize a list of names/strings from ABS metadata."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result = []
        for entry in value:
            if isinstance(entry, dict):
                name = entry.get("name")
                if name:
                    result.append(str(name))
            elif entry:
                result.append(str(entry))
        return result
    return []


def _extract_series(metadata: dict[str, Any]) -> list[str]:
    """Return series descriptors ("Name #Sequence") from ABS metadata."""
    series = metadata.get("series")
    if isinstance(series, list):
        result = []
        for entry in series:
            if isinstance(entry, dict):
                name = entry.get("name")
                if not name:
                    continue
                sequence = entry.get("sequence")
                result.append(f"{name} #{sequence}" if sequence else str(name))
            elif entry:
                result.append(str(entry))
        return result
    name = metadata.get("seriesName")
    if isinstance(name, str) and name:
        return [name]
    return []


def _extract_ebook_format(ebook_file: Any, media: dict[str, Any]) -> str | None:
    """Return the ebook file format when available."""
    if isinstance(ebook_file, dict):
        fmt = ebook_file.get("ebookFormat") or ebook_file.get("format")
        if fmt:
            return str(fmt)
    fmt = media.get("ebookFormat")
    return str(fmt) if fmt else None


def _build_item_url(base_url: str | None, item_id: str, *, cover: bool = False) -> str | None:
    """Build a deep link to an ABS item (or its cover)."""
    if not base_url or not item_id:
        return None
    base = base_url.rstrip("/")
    if cover:
        return f"{base}/api/items/{item_id}/cover"
    return f"{base}/item/{item_id}"


def _extract_item(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract an item object from common payload shapes."""
    for key in ("item", "libraryItem", "library_item"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    data = payload.get("data") or payload.get("payload")
    if isinstance(data, dict):
        return _extract_item(data)
    return {}


def _extract_source_event(payload: dict[str, Any]) -> str | None:
    """Extract the source event name when the payload includes one."""
    for key in ("event", "eventName", "type", "action"):
        if payload.get(key):
            return str(payload[key])
    data = payload.get("data") or payload.get("payload")
    if isinstance(data, dict):
        return _extract_source_event(data)
    return None


def _event_type_from_source(source_event: str | None) -> str:
    """Map source event labels to integration event types."""
    if not source_event:
        return EVENT_LIBRARY_ITEM_RECEIVED
    normalized = source_event.lower().replace("-", "_").replace(" ", "_")
    if "update" in normalized or "scan" in normalized:
        return EVENT_LIBRARY_ITEM_UPDATED
    if "add" in normalized or "create" in normalized or "new" in normalized:
        return EVENT_LIBRARY_ITEM_RECEIVED
    return EVENT_LIBRARY_ITEM_UNKNOWN


def _extract_authors(metadata: dict[str, Any]) -> list[str]:
    """Return author names from ABS metadata."""
    authors_value = metadata.get("authors") or metadata.get("authorName") or []
    if isinstance(authors_value, str):
        return [authors_value]
    if isinstance(authors_value, list):
        return [str(author.get("name", author)) for author in authors_value]
    return []


def _normalize_recently_added_book(item: dict[str, Any] | None, library: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize an ABS library item for the recently added book sensor."""
    if not item:
        return {
            "library_id": library.get("id"),
            "library_name": library.get("name"),
            "title": None,
            "item_id": None,
            "item_count": None,
        }
    media = item.get("media") if isinstance(item.get("media"), dict) else {}
    metadata = media.get("metadata") if isinstance(media.get("metadata"), dict) else {}
    return {
        "item_id": item.get("id"),
        "library_id": item.get("_libraryId") or item.get("libraryId") or library.get("id"),
        "library_name": item.get("_libraryName") or library.get("name"),
        "title": metadata.get("title") or item.get("title") or item.get("id"),
        "authors": _extract_authors(metadata),
        "media_type": media.get("mediaType") or item.get("mediaType"),
        "added_at": item.get("addedAt") or item.get("createdAt"),
        "item_count": item.get("_libraryTotal"),
        "has_ebook": bool(media.get("ebookFile") or item.get("ebookFile")),
    }
