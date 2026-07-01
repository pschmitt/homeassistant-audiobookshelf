"""Sensors for Audiobookshelf Kindle."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_WEBHOOK_ID, DOMAIN, SIGNAL_UPDATED

SENSORS = (
    SensorEntityDescription(key="sent_count", translation_key="sent_count", icon="mdi:book-check"),
    SensorEntityDescription(key="skipped_count", translation_key="skipped_count", icon="mdi:book-cancel"),
    SensorEntityDescription(key="failed_count", translation_key="failed_count", icon="mdi:book-alert"),
    SensorEntityDescription(key="last_result", translation_key="last_result", icon="mdi:book-sync"),
    SensorEntityDescription(key="webhook_path", translation_key="webhook_path", icon="mdi:webhook"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    manager = hass.data[DOMAIN][entry.entry_id]["manager"]
    async_add_entities(AudiobookshelfKindleSensor(entry, manager, desc) for desc in SENSORS)


class AudiobookshelfKindleSensor(SensorEntity):
    """A diagnostic integration sensor."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, manager, description: SensorEntityDescription) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._entry = entry
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Audiobookshelf",
            "model": "Send to Kindle bridge",
        }

    @property
    def native_value(self):
        """Return sensor value."""
        if self.entity_description.key == "sent_count":
            return self._manager.sent_count
        if self.entity_description.key == "skipped_count":
            return self._manager.skipped_count
        if self.entity_description.key == "failed_count":
            return self._manager.failed_count
        if self.entity_description.key == "webhook_path":
            return f"/api/webhook/{self._entry.data[CONF_WEBHOOK_ID]}"
        if self._manager.last_result is None:
            return "idle"
        result = self._manager.last_result
        if result.sent:
            return "sent"
        if result.skipped:
            return f"skipped:{result.reason}"
        return result.reason or "failed"

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.entity_description.key == "webhook_path":
            path = f"/api/webhook/{self._entry.data[CONF_WEBHOOK_ID]}"
            external_url = self.hass.config.external_url
            internal_url = self.hass.config.internal_url
            return {
                "path": path,
                "external_url": None if external_url is None else f"{external_url.rstrip('/')}{path}",
                "internal_url": None if internal_url is None else f"{internal_url.rstrip('/')}{path}",
            }
        if self.entity_description.key != "last_result" or self._manager.last_result is None:
            return None
        return self._manager.last_result.__dict__

    async def async_added_to_hass(self) -> None:
        """Subscribe to manager updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_UPDATED}_{self._entry.entry_id}",
                self._handle_coordinator_update,
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write state when manager data changes."""
        self.async_write_ha_state()
