"""Diagnostics for Audiobookshelf."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ABS_TOKEN,
    DOMAIN,
)

TO_REDACT = {CONF_ABS_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict:
    """Return diagnostics."""
    manager = hass.data[DOMAIN][config_entry.entry_id]["manager"]
    return {
        "entry": async_redact_data(dict(config_entry.data), TO_REDACT),
        "options": dict(config_entry.options),
        "sent_count": manager.sent_count,
        "skipped_count": manager.skipped_count,
        "failed_count": manager.failed_count,
        "last_result": None if manager.last_result is None else manager.last_result.__dict__,
        "last_event": manager.last_event,
        "server_status": manager.server_status,
        "ereader_devices": manager.ereader_device_names,
    }
