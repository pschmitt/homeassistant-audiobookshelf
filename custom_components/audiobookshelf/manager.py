"""Runtime manager for Audiobookshelf Kindle."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from .api import AudiobookshelfClient
from .const import (
    CONF_ACCEPTED_FORMATS,
    CONF_AUTO_SEND,
    CONF_HA_LOCAL_ROOT,
    CONF_LOCAL_ABS_ROOT,
    CONF_MAX_ATTACHMENT_MB,
    DOMAIN,
    EVENT_ITEM_RECEIVED,
    ISSUE_MISSING_EBOOK,
    ISSUE_SEND_FAILED,
    ISSUE_SIZE_LIMIT,
    ISSUE_UNSUPPORTED_FORMAT,
    STORAGE_KEY,
    STORAGE_VERSION,
    SIGNAL_UPDATED,
)
from .exceptions import AttachmentTooLarge, MissingEbook, SendFailed, UnsupportedFormat
from .mailer import KindleMailer
from .models import SendResult, normalize_ebook

_LOGGER = logging.getLogger(__name__)


class AudiobookshelfKindleManager:
    """Coordinate webhook events, ABS metadata, and Kindle sends."""

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
        self.mailer = KindleMailer(hass, entry.data)
        self.last_result: SendResult | None = None
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

    async def async_reset_sent_item(self, item_id: str) -> bool:
        """Remove a sent marker so an item can be resent."""
        existed = self._sent_items.pop(item_id, None) is not None
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
        self.hass.bus.async_fire(
            EVENT_ITEM_RECEIVED,
            {
                "entry_id": self.entry.entry_id,
                "item_id": item_id,
                "payload": payload,
            },
        )
        if not self.entry.options.get(CONF_AUTO_SEND, False):
            result = SendResult(item_id=item_id, title=item_id, sent=False, skipped=True, reason="auto_send_disabled")
            self.last_result = result
            self.skipped_count += 1
            self._async_write_state()
            return result
        return await self.async_send_item(item_id, source="webhook")

    async def async_send_item(self, item_id: str, *, force: bool = False, source: str = "service") -> SendResult:
        """Send an ABS item to Kindle."""
        if not force and item_id in self._sent_items:
            result = SendResult(item_id=item_id, title=self._sent_items[item_id].get("title", item_id), sent=False, skipped=True, reason="already_sent")
            self.last_result = result
            self.skipped_count += 1
            self._async_write_state()
            return result

        try:
            item = await self.client.async_get_item(item_id)
            ebook = normalize_ebook(item)
            accepted = [fmt.lower().lstrip(".") for fmt in self.entry.options.get(CONF_ACCEPTED_FORMATS, [])]
            if ebook.format not in accepted:
                raise UnsupportedFormat(f"{ebook.format} is not in {accepted}")
            max_bytes = int(self.entry.options.get(CONF_MAX_ATTACHMENT_MB, 45)) * 1024 * 1024
            if ebook.size is not None and ebook.size > max_bytes:
                raise AttachmentTooLarge(f"{ebook.filename} exceeds configured attachment size limit")
            content = await self._async_get_ebook_content(ebook)
            if len(content) > max_bytes:
                raise AttachmentTooLarge(f"{ebook.filename} exceeds configured attachment size limit")
            await self.mailer.async_send(ebook, content)
        except MissingEbook as err:
            self.failed_count += 1
            self._create_issue(ISSUE_MISSING_EBOOK, str(err))
            raise
        except UnsupportedFormat as err:
            self.failed_count += 1
            self._create_issue(ISSUE_UNSUPPORTED_FORMAT, str(err))
            raise
        except AttachmentTooLarge as err:
            self.failed_count += 1
            self._create_issue(ISSUE_SIZE_LIMIT, str(err))
            raise
        except SendFailed as err:
            self.failed_count += 1
            self._create_issue(ISSUE_SEND_FAILED, str(err))
            raise

        self._sent_items[item_id] = {
            "title": ebook.display_title,
            "filename": ebook.filename,
            "source": source,
        }
        self.sent_count = len(self._sent_items)
        await self.async_save()
        self._delete_send_issues()
        result = SendResult(item_id=item_id, title=ebook.display_title, sent=True, skipped=False, filename=ebook.filename)
        self.last_result = result
        self._async_write_state()
        return result

    def _async_write_state(self) -> None:
        """Notify entities that manager state changed."""
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATED}_{self.entry.entry_id}")

    async def _async_get_ebook_content(self, ebook) -> bytes:
        """Return ebook bytes from local mapped path or ABS download endpoints."""
        local = self._local_path_for(ebook.path)
        if local is not None:
            return await self.hass.async_add_executor_job(local.read_bytes)

        payloads = await self.client.async_download_candidates(ebook.item_id)
        if payloads:
            return payloads[0]
        raise SendFailed("Could not read ebook locally and no ABS download endpoint returned bytes")

    def _local_path_for(self, abs_path: str | None) -> Path | None:
        """Map an ABS server path to a HA-local path if configured."""
        if not abs_path:
            return None
        abs_root = self.entry.options.get(CONF_LOCAL_ABS_ROOT)
        ha_root = self.entry.options.get(CONF_HA_LOCAL_ROOT)
        if not abs_root or not ha_root:
            return None
        try:
            rel = Path(abs_path).relative_to(Path(abs_root))
        except ValueError:
            return None
        local = Path(ha_root) / rel
        return local if local.is_file() else None

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
        for issue_id in (ISSUE_MISSING_EBOOK, ISSUE_SEND_FAILED, ISSUE_SIZE_LIMIT, ISSUE_UNSUPPORTED_FORMAT):
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
