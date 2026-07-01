"""Services for Audiobookshelf Kindle."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SERVICE_RESET_SENT_ITEM, SERVICE_SEND_ITEM
from .exceptions import AudiobookshelfKindleError

SEND_ITEM_SCHEMA = vol.Schema(
    {
        vol.Required("item_id"): cv.string,
        vol.Optional("force", default=False): cv.boolean,
    }
)
RESET_SENT_ITEM_SCHEMA = vol.Schema({vol.Required("item_id"): cv.string})


async def async_register_services(hass: HomeAssistant) -> None:
    """Register services."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_ITEM):
        return

    async def _handle_send_item(call: ServiceCall) -> ServiceResponse:
        item_id = call.data["item_id"]
        force = call.data["force"]
        results: list[dict[str, Any]] = []
        for data in hass.data.get(DOMAIN, {}).values():
            manager = data.get("manager") if isinstance(data, dict) else None
            if manager is None:
                continue
            try:
                result = await manager.async_send_item(item_id, force=force)
            except AudiobookshelfKindleError as err:
                raise HomeAssistantError(str(err)) from err
            results.append(result.__dict__)
        return {"results": results}

    async def _handle_reset_sent_item(call: ServiceCall) -> ServiceResponse:
        item_id = call.data["item_id"]
        reset = []
        for entry_id, data in hass.data.get(DOMAIN, {}).items():
            manager = data.get("manager") if isinstance(data, dict) else None
            if manager is None:
                continue
            reset.append({"entry_id": entry_id, "reset": await manager.async_reset_sent_item(item_id)})
        return {"results": reset}

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_ITEM,
        _handle_send_item,
        schema=SEND_ITEM_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_SENT_ITEM,
        _handle_reset_sent_item,
        schema=RESET_SENT_ITEM_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services when no entries remain."""
    if hass.data.get(DOMAIN):
        return
    for service in (SERVICE_SEND_ITEM, SERVICE_RESET_SENT_ITEM):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
