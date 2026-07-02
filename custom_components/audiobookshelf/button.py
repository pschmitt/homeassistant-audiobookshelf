"""Buttons for Audiobookshelf."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .exceptions import AudiobookshelfError

BUTTONS = (
    ButtonEntityDescription(key="refresh_data", translation_key="refresh_data", icon="mdi:refresh", entity_category=EntityCategory.DIAGNOSTIC),
    ButtonEntityDescription(key="send_last_ebook_to_device", translation_key="send_last_ebook_to_device", icon="mdi:book-arrow-right"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up buttons."""
    manager = hass.data[DOMAIN][entry.entry_id]["manager"]
    async_add_entities(AudiobookshelfButton(entry, manager, desc) for desc in BUTTONS)


class AudiobookshelfButton(ButtonEntity):
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
            "model": "Audiobookshelf server",
        }

    async def async_press(self) -> None:
        """Press the button."""
        try:
            if self.entity_description.key == "refresh_data":
                await self._manager.async_refresh()
                return
            if self.entity_description.key == "send_last_ebook_to_device":
                await self._manager.async_send_last_ebook_to_device()
                return
        except AudiobookshelfError as err:
            raise HomeAssistantError(str(err)) from err
