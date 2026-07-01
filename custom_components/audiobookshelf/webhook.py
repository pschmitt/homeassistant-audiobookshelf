"""Webhook support for Audiobookshelf."""

from __future__ import annotations

import logging

from aiohttp import web

from homeassistant.components.webhook import (
    async_register as async_register_ha_webhook,
    async_unregister as async_unregister_ha_webhook,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_WEBHOOK_ID, DOMAIN
from .manager import AudiobookshelfManager

_LOGGER = logging.getLogger(__name__)


def async_register_webhook(
    hass: HomeAssistant,
    entry: ConfigEntry,
    manager: AudiobookshelfManager,
) -> None:
    """Register the ABS notification webhook."""

    async def _handle_webhook(
        hass: HomeAssistant,
        webhook_id: str,
        request: web.Request,
    ) -> web.Response:
        del hass, webhook_id
        payload = await request.json()
        try:
            result = await manager.async_handle_webhook(payload)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to process Audiobookshelf webhook")
            return web.json_response({"ok": False}, status=500)
        return web.json_response({"ok": True, "result": None if result is None else result.__dict__})

    async_register_ha_webhook(
        hass,
        DOMAIN,
        "Audiobookshelf",
        entry.data[CONF_WEBHOOK_ID],
        _handle_webhook,
        local_only=False,
    )
    entry.async_on_unload(
        lambda: async_unregister_ha_webhook(hass, entry.data[CONF_WEBHOOK_ID])
    )
