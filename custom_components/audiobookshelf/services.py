"""Services for Audiobookshelf."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_set_service_schema

from .const import DOMAIN, SERVICE_RESET_SENT_ITEM, SERVICE_SEND_EBOOK_TO_DEVICE, SERVICE_SEND_ITEM
from .exceptions import AudiobookshelfError

SEND_ITEM_SCHEMA = vol.Schema(
    {
        vol.Required("item_id"): cv.string,
        vol.Optional("device_name"): cv.string,
        vol.Optional("force", default=False): cv.boolean,
    }
)
RESET_SENT_ITEM_SCHEMA = vol.Schema(
    {
        vol.Required("item_id"): cv.string,
        vol.Optional("device_name"): cv.string,
    }
)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register services."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_EBOOK_TO_DEVICE):
        return

    async def _handle_send_ebook_to_device(call: ServiceCall) -> ServiceResponse:
        item_id = call.data["item_id"]
        device_name = call.data.get("device_name")
        force = call.data["force"]
        results: list[dict[str, Any]] = []
        for data in hass.data.get(DOMAIN, {}).values():
            manager = data.get("manager") if isinstance(data, dict) else None
            if manager is None:
                continue
            try:
                result = await manager.async_send_ebook_to_device(
                    item_id,
                    device_name=device_name,
                    force=force,
                )
            except AudiobookshelfError as err:
                raise HomeAssistantError(str(err)) from err
            results.append(result.__dict__)
        return {"results": results}

    async def _handle_send_item(call: ServiceCall) -> ServiceResponse:
        return await _handle_send_ebook_to_device(call)

    async def _handle_reset_sent_item(call: ServiceCall) -> ServiceResponse:
        item_id = call.data["item_id"]
        reset = []
        for entry_id, data in hass.data.get(DOMAIN, {}).items():
            manager = data.get("manager") if isinstance(data, dict) else None
            if manager is None:
                continue
            reset.append(
                {
                    "entry_id": entry_id,
                    "reset": await manager.async_reset_sent_item(
                        item_id,
                        call.data.get("device_name"),
                    ),
                }
            )
        return {"results": reset}

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_EBOOK_TO_DEVICE,
        _handle_send_ebook_to_device,
        schema=SEND_ITEM_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
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


def _aggregate_choices(hass: HomeAssistant) -> tuple[list[dict[str, str]], list[str]]:
    """Collect ebook choices and e-reader device names across all entries."""
    item_choices: list[dict[str, str]] = []
    device_names: list[str] = []
    seen_items: set[str] = set()
    seen_devices: set[str] = set()
    for data in hass.data.get(DOMAIN, {}).values():
        manager = data.get("manager") if isinstance(data, dict) else None
        if manager is None:
            continue
        for choice in manager.ebook_choices:
            value = choice["value"]
            if value in seen_items:
                continue
            seen_items.add(value)
            item_choices.append(choice)
        for name in manager.ereader_device_names:
            if name in seen_devices:
                continue
            seen_devices.add(name)
            device_names.append(name)
    return item_choices, device_names


def _dropdown_selector(options: list[Any]) -> dict[str, Any]:
    """Build a searchable dropdown selector, or free text when no options.

    ``custom_value`` keeps raw values (a pasted item ID or device name) valid,
    so existing scripts and automations that pass strings keep working.
    """
    if not options:
        return {"text": {}}
    return {
        "select": {
            "options": options,
            "custom_value": True,
            "mode": "dropdown",
            "sort": False,
        }
    }


def _build_fields(hass: HomeAssistant, *, include_force: bool) -> dict[str, Any]:
    """Build service field descriptions with live book/device dropdowns."""
    item_choices, device_names = _aggregate_choices(hass)
    fields: dict[str, Any] = {
        "item_id": {"required": True, "selector": _dropdown_selector(item_choices)},
        "device_name": {"required": False, "selector": _dropdown_selector(device_names)},
    }
    if include_force:
        fields["force"] = {"required": False, "default": False, "selector": {"boolean": {}}}
    return fields


@callback
def async_update_service_descriptions(hass: HomeAssistant) -> None:
    """Refresh service field selectors from current books and e-reader devices.

    Uses ``async_set_service_schema`` so the dropdowns reflect live server data
    instead of the static ``services.yaml`` text fields. Services that are not
    registered yet are skipped (``async_set_service_schema`` would otherwise
    raise while querying an unregistered service's response support).
    """
    for service, include_force in (
        (SERVICE_SEND_EBOOK_TO_DEVICE, True),
        (SERVICE_SEND_ITEM, True),
        (SERVICE_RESET_SENT_ITEM, False),
    ):
        if not hass.services.has_service(DOMAIN, service):
            continue
        async_set_service_schema(
            hass, DOMAIN, service, {"fields": _build_fields(hass, include_force=include_force)}
        )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services when no entries remain."""
    if hass.data.get(DOMAIN):
        return
    for service in (SERVICE_SEND_EBOOK_TO_DEVICE, SERVICE_SEND_ITEM, SERVICE_RESET_SENT_ITEM):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
