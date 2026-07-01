"""Audiobookshelf integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import AudiobookshelfClient
from .const import (
    CONF_ABS_TOKEN,
    CONF_ABS_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
    ISSUE_AUTH,
    ISSUE_CONNECTIVITY,
    PLATFORMS,
)
from .exceptions import CannotConnect, InvalidAuth
from .manager import AudiobookshelfManager
from .services import async_register_services, async_unregister_services
from .webhook import async_register_webhook

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the integration domain."""
    del config
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Audiobookshelf from a config entry."""
    session = async_create_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL])
    client = AudiobookshelfClient(
        session=session,
        base_url=entry.data[CONF_ABS_URL],
        token=entry.data[CONF_ABS_TOKEN],
    )
    manager = AudiobookshelfManager(hass, entry, client)
    await manager.async_load()

    try:
        await client.async_validate()
    except InvalidAuth as err:
        _create_setup_issue(hass, entry, ISSUE_AUTH, str(err))
        raise ConfigEntryAuthFailed(str(err)) from err
    except CannotConnect as err:
        _create_setup_issue(hass, entry, ISSUE_CONNECTIVITY, str(err))
        raise ConfigEntryNotReady(str(err)) from err
    else:
        _delete_setup_issues(hass, entry)

    await manager.async_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "manager": manager,
        "session": session,
    }

    await async_register_services(hass)
    async_register_webhook(hass, entry, manager)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Audiobookshelf config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, {})
        session = data.get("session")
        if session is not None:
            await session.close()
        async_unregister_services(hass)
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration after options changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry data."""
    data = dict(entry.data)
    if CONF_URL in data and CONF_ABS_URL not in data:
        data[CONF_ABS_URL] = data.pop(CONF_URL)
    if CONF_TOKEN in data and CONF_ABS_TOKEN not in data:
        data[CONF_ABS_TOKEN] = data.pop(CONF_TOKEN)
    if data != entry.data or entry.version < 2:
        hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True


def _create_setup_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
    issue_id: str,
    detail: str,
) -> None:
    """Create a setup repair issue."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{entry.entry_id}_{issue_id}",
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=issue_id,
        translation_placeholders={"detail": detail},
    )


def _delete_setup_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete setup repair issues."""
    for issue_id in (ISSUE_AUTH, ISSUE_CONNECTIVITY):
        ir.async_delete_issue(hass, DOMAIN, f"{entry.entry_id}_{issue_id}")
