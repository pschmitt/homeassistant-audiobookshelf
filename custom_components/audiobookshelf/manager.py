"""Runtime manager for Audiobookshelf."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
from .exceptions import MissingDevice, MissingEbook, SendFailed
from .models import SendResult, normalize_ebook

_LOGGER = logging.getLogger(__name__)


class AudiobookshelfManager:
    """Coordinate webhook events, ABS metadata, and e-reader device sends."""

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

    async def async_handle_webhook(self, payload: dict[str, Any]) -> SendResult | None:
        """Handle an ABS webhook payload."""
        item_id = _extract_item_id(payload)
        if not item_id:
            _LOGGER.debug("Ignoring Audiobookshelf webhook without item id: %s", payload)
            return None
        self._event_id += 1
        event = _normalize_event(self.entry.entry_id, self._event_id, item_id, payload)
        self.last_event = event
        self.hass.bus.async_fire(
            EVENT_ITEM_RECEIVED,
            event,
        )
        self._async_write_state()
        if not self.entry.options.get(CONF_AUTO_SEND, False):
            result = SendResult(item_id=item_id, title=item_id, device_name=None, sent=False, skipped=True, reason="auto_send_disabled")
            self.last_result = result
            self.skipped_count += 1
            self._async_write_state()
            return result
        return await self.async_send_ebook_to_device(item_id, source="webhook")

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
def _extract_item_id(payload: dict[str, Any]) -> str | None:
    """Extract a library item id from common ABS notification shapes."""
    for key in ("libraryItemId", "library_item_id", "itemId", "item_id", "id"):
        if payload.get(key):
            return str(payload[key])
    item = payload.get("item") or payload.get("libraryItem") or payload.get("library_item")
    if isinstance(item, dict) and item.get("id"):
        return str(item["id"])
    data = payload.get("data") or payload.get("payload")
    if isinstance(data, dict):
        return _extract_item_id(data)
    return None


def _normalize_event(entry_id: str, event_id: int, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize common ABS webhook payloads into stable HA event attributes."""
    item = _extract_item(payload)
    media = item.get("media") if isinstance(item.get("media"), dict) else {}
    metadata = media.get("metadata") if isinstance(media.get("metadata"), dict) else {}
    source_event = _extract_source_event(payload)
    event_type = _event_type_from_source(source_event)
    return {
        "entry_id": entry_id,
        "event_id": event_id,
        "event_type": event_type,
        "source_event": source_event,
        "item_id": item_id,
        "library_id": payload.get("libraryId") or payload.get("library_id") or item.get("libraryId"),
        "title": metadata.get("title") or item.get("title"),
        "authors": _extract_authors(metadata),
        "media_type": media.get("mediaType") or item.get("mediaType"),
        "has_ebook": bool(media.get("ebookFile") or item.get("ebookFile")),
    }


def _extract_item(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract an item object from common webhook payload shapes."""
    for key in ("item", "libraryItem", "library_item"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    data = payload.get("data") or payload.get("payload")
    if isinstance(data, dict):
        return _extract_item(data)
    return {}


def _extract_source_event(payload: dict[str, Any]) -> str | None:
    """Extract the source webhook event name when ABS includes one."""
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
