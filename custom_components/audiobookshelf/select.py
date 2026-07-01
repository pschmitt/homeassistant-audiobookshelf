"""Select entities for Audiobookshelf."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_UPDATED

SELECTS = (
    SelectEntityDescription(
        key="default_ereader_device",
        translation_key="default_ereader_device",
        icon="mdi:tablet-cellphone",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    manager = hass.data[DOMAIN][entry.entry_id]["manager"]
    async_add_entities(AudiobookshelfSelect(entry, manager, desc) for desc in SELECTS)


class AudiobookshelfSelect(SelectEntity):
    """Audiobookshelf select entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, manager, description: SelectEntityDescription) -> None:
        """Initialize the select entity."""
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

    @property
    def options(self) -> list[str]:
        """Return selectable e-reader devices."""
        return self._manager.ereader_device_names

    @property
    def current_option(self) -> str | None:
        """Return the selected default e-reader device."""
        return self._manager.default_device_name

    async def async_select_option(self, option: str) -> None:
        """Select the default e-reader device."""
        await self._manager.async_set_default_device(option)

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
        """Write state when manager data changes."""
        self.async_write_ha_state()
