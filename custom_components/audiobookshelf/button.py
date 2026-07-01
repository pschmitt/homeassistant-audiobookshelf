"""Buttons for Audiobookshelf Kindle."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

BUTTONS = (
    ButtonEntityDescription(key="test_connection", translation_key="test_connection", icon="mdi:connection"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons."""
    manager = hass.data[DOMAIN][entry.entry_id]["manager"]
    async_add_entities(AudiobookshelfKindleButton(entry, manager, desc) for desc in BUTTONS)


class AudiobookshelfKindleButton(ButtonEntity):
    """Integration button."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, manager, description: ButtonEntityDescription) -> None:
        """Initialize the button."""
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

    async def async_press(self) -> None:
        """Press the button."""
        await self._manager.client.async_validate()
