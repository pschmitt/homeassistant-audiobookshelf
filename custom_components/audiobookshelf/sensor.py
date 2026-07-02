"""Sensors for Audiobookshelf."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_UPDATED

SENSORS = (
    SensorEntityDescription(key="server_status", translation_key="server_status", icon="mdi:server", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="server_version", translation_key="server_version", icon="mdi:tag-outline", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="ereader_devices", translation_key="ereader_devices", icon="mdi:tablet-cellphone"),
    SensorEntityDescription(key="default_ereader_device", translation_key="default_ereader_device", icon="mdi:star-cog"),
    SensorEntityDescription(key="last_library_item", translation_key="last_library_item", icon="mdi:book-open-page-variant"),
    SensorEntityDescription(key="last_refresh", translation_key="last_refresh", device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="sent_count", translation_key="sent_count", icon="mdi:book-check", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="skipped_count", translation_key="skipped_count", icon="mdi:book-cancel", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="failed_count", translation_key="failed_count", icon="mdi:book-alert", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="last_result", translation_key="last_result", icon="mdi:book-sync", entity_category=EntityCategory.DIAGNOSTIC),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    manager = hass.data[DOMAIN][entry.entry_id]["manager"]
    async_add_entities(AudiobookshelfSensor(entry, manager, desc) for desc in SENSORS)
    library_entities: dict[tuple[str, str], AudiobookshelfLibrarySensor] = {}

    async def async_sync_library_entities() -> None:
        """Add and remove per-library sensors as ABS libraries change."""
        wanted = {
            (library_id, key)
            for library_id in manager.book_libraries
            for key in ("recently_added_book", "library_items")
        }
        for entity_key in set(library_entities) - wanted:
            await library_entities.pop(entity_key).async_remove()
        new_entities = []
        for library_id, key in wanted - set(library_entities):
            entity = AudiobookshelfLibrarySensor(entry, manager, library_id, key)
            library_entities[(library_id, key)] = entity
            new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

    await async_sync_library_entities()

    @callback
    def handle_manager_update() -> None:
        hass.async_create_task(async_sync_library_entities())

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{SIGNAL_UPDATED}_{entry.entry_id}",
            handle_manager_update,
        )
    )


class AudiobookshelfSensor(SensorEntity):
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
            "model": "Audiobookshelf server",
        }

    @property
    def native_value(self):
        """Return sensor value."""
        if self.entity_description.key == "server_status":
            return _server_status(self._manager.server_status)
        if self.entity_description.key == "server_version":
            return _server_version(self._manager.server_status)
        if self.entity_description.key == "ereader_devices":
            return len(self._manager.ereader_device_names)
        if self.entity_description.key == "default_ereader_device":
            return self._manager.default_device_name or "not_configured"
        if self.entity_description.key == "last_library_item":
            if self._manager.last_event is None:
                return "none"
            return self._manager.last_event.get("title") or self._manager.last_event.get("item_id") or "unknown"
        if self.entity_description.key == "last_refresh":
            return self._manager.last_refresh
        if self.entity_description.key == "sent_count":
            return self._manager.sent_count
        if self.entity_description.key == "skipped_count":
            return self._manager.skipped_count
        if self.entity_description.key == "failed_count":
            return self._manager.failed_count
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
        if self.entity_description.key == "server_status":
            return dict(self._manager.server_status)
        if self.entity_description.key == "ereader_devices":
            return {
                "devices": self._manager.ereader_device_names,
                "default_device": self._manager.default_device_name,
            }
        if self.entity_description.key == "last_library_item":
            return self._manager.last_event
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


class AudiobookshelfLibrarySensor(SensorEntity):
    """A per-library diagnostic sensor."""

    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, manager, library_id: str, key: str) -> None:
        """Initialize the per-library sensor."""
        self._entry = entry
        self._manager = manager
        self._library_id = library_id
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}_{library_id}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Audiobookshelf",
            "model": "Audiobookshelf server",
        }
        self._attr_icon = "mdi:book-plus" if key == "recently_added_book" else "mdi:bookshelf"

    @property
    def name(self) -> str:
        """Return the sensor name."""
        library_name = self._library_name()
        if self._key == "recently_added_book":
            return f"Recently added book {library_name}"
        return f"Library items {library_name}"

    @property
    def native_value(self):
        """Return sensor value."""
        book = self._manager.recently_added_books_by_library.get(self._library_id) or {}
        if self._key == "recently_added_book":
            return book.get("title") or book.get("item_id") or "none"
        return book.get("item_count")

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        book = self._manager.recently_added_books_by_library.get(self._library_id) or {}
        return {
            **book,
            "library_id": self._library_id,
            "library_name": self._library_name(),
        }

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

    def _library_name(self) -> str:
        """Return the current library name."""
        library = self._manager.book_libraries.get(self._library_id, {})
        return str(library.get("name") or self._library_id)


def _server_status(status: dict) -> str:
    """Return a compact server status string."""
    if not status:
        return "unknown"
    if isinstance(status.get("status"), str):
        return status["status"]
    if status.get("isInit") is False:
        return "not_initialized"
    return "online"


def _server_version(status: dict) -> str:
    """Return the server version from known ABS status shapes."""
    for key in ("serverVersion", "version", "appVersion"):
        if status.get(key):
            return str(status[key])
    return "unknown"
