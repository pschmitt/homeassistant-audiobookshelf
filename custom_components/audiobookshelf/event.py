"""Event entities for Audiobookshelf."""

from __future__ import annotations

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    EVENT_LIBRARY_ITEM_RECEIVED,
    EVENT_LIBRARY_ITEM_UNKNOWN,
    EVENT_LIBRARY_ITEM_UPDATED,
    SIGNAL_UPDATED,
)

EVENTS = (
    EventEntityDescription(
        key="library_item",
        translation_key="library_item",
        event_types=[
            EVENT_LIBRARY_ITEM_RECEIVED,
            EVENT_LIBRARY_ITEM_UPDATED,
            EVENT_LIBRARY_ITEM_UNKNOWN,
        ],
        icon="mdi:book-sync",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up event entities."""
    manager = hass.data[DOMAIN][entry.entry_id]["manager"]
    async_add_entities(AudiobookshelfEvent(entry, manager, desc) for desc in EVENTS)


class AudiobookshelfEvent(EventEntity):
    """Audiobookshelf event entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, manager, description: EventEntityDescription) -> None:
        """Initialize the event entity."""
        self.entity_description = description
        self._entry = entry
        self._manager = manager
        self._last_event_id: int | None = None
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Audiobookshelf",
            "model": "Audiobookshelf server",
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to manager updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_UPDATED}_{self._entry.entry_id}",
                self._handle_manager_update,
            )
        )

    @callback
    def _handle_manager_update(self) -> None:
        """Publish the latest normalized library item event."""
        if self._manager.last_event is None:
            return
        event = dict(self._manager.last_event)
        event_id = event.get("event_id")
        if event_id == self._last_event_id:
            return
        self._last_event_id = event_id
        event_type = event.pop("event_type")
        self._trigger_event(event_type, event)
        self.async_write_ha_state()
