"""Config flow for Audiobookshelf Kindle."""

from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import AudiobookshelfClient
from .const import (
    CONF_ABS_TOKEN,
    CONF_ABS_URL,
    CONF_ACCEPTED_FORMATS,
    CONF_AUTO_SEND,
    CONF_HA_LOCAL_ROOT,
    CONF_LOCAL_ABS_ROOT,
    CONF_MAX_ATTACHMENT_MB,
    CONF_RECIPIENT_EMAIL,
    CONF_SENDER_EMAIL,
    CONF_SMTP_HOST,
    CONF_SMTP_PASSWORD,
    CONF_SMTP_PORT,
    CONF_SMTP_STARTTLS,
    CONF_SMTP_USERNAME,
    CONF_VERIFY_SSL,
    CONF_WEBHOOK_ID,
    DEFAULT_ACCEPTED_FORMATS,
    DEFAULT_AUTO_SEND,
    DEFAULT_MAX_ATTACHMENT_MB,
    DEFAULT_NAME,
    DEFAULT_SMTP_PORT,
    DEFAULT_SMTP_STARTTLS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .exceptions import CannotConnect, InvalidAuth


async def _async_validate(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate ABS connection credentials."""
    session = async_create_clientsession(
        hass,
        verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
    )
    try:
        client = AudiobookshelfClient(
            session=session,
            base_url=data[CONF_ABS_URL],
            token=data[CONF_ABS_TOKEN],
        )
        return await client.async_validate()
    finally:
        await session.close()


def _connection_schema(defaults: dict[str, Any], *, token_optional: bool = False) -> vol.Schema:
    """Build connection schema."""
    token_key = vol.Optional(CONF_ABS_TOKEN) if token_optional else vol.Required(CONF_ABS_TOKEN)
    return vol.Schema(
        {
            vol.Required(CONF_ABS_URL, default=defaults.get(CONF_ABS_URL, "")): TextSelector(),
            token_key: TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required(CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)): BooleanSelector(),
        }
    )


def _mail_schema(defaults: dict[str, Any], *, password_optional: bool = False) -> vol.Schema:
    """Build mail schema."""
    password_key = vol.Optional(CONF_SMTP_PASSWORD) if password_optional else vol.Required(CONF_SMTP_PASSWORD)
    return vol.Schema(
        {
            vol.Required(CONF_RECIPIENT_EMAIL, default=defaults.get(CONF_RECIPIENT_EMAIL, "")): TextSelector(),
            vol.Required(CONF_SENDER_EMAIL, default=defaults.get(CONF_SENDER_EMAIL, "")): TextSelector(),
            vol.Required(CONF_SMTP_HOST, default=defaults.get(CONF_SMTP_HOST, "")): TextSelector(),
            vol.Required(CONF_SMTP_PORT, default=defaults.get(CONF_SMTP_PORT, DEFAULT_SMTP_PORT)): NumberSelector(NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)),
            vol.Optional(CONF_SMTP_USERNAME, default=defaults.get(CONF_SMTP_USERNAME, "")): TextSelector(),
            password_key: TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required(CONF_SMTP_STARTTLS, default=defaults.get(CONF_SMTP_STARTTLS, DEFAULT_SMTP_STARTTLS)): BooleanSelector(),
        }
    )


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build options schema."""
    return vol.Schema(
        {
            vol.Required(CONF_AUTO_SEND, default=defaults.get(CONF_AUTO_SEND, DEFAULT_AUTO_SEND)): BooleanSelector(),
            vol.Required(CONF_ACCEPTED_FORMATS, default=defaults.get(CONF_ACCEPTED_FORMATS, DEFAULT_ACCEPTED_FORMATS)): SelectSelector(
                SelectSelectorConfig(options=["epub", "pdf"], multiple=True, mode=SelectSelectorMode.DROPDOWN)
            ),
            vol.Required(CONF_MAX_ATTACHMENT_MB, default=defaults.get(CONF_MAX_ATTACHMENT_MB, DEFAULT_MAX_ATTACHMENT_MB)): NumberSelector(NumberSelectorConfig(min=1, max=200, mode=NumberSelectorMode.BOX)),
            vol.Optional(CONF_LOCAL_ABS_ROOT, default=defaults.get(CONF_LOCAL_ABS_ROOT, "")): TextSelector(),
            vol.Optional(CONF_HA_LOCAL_ROOT, default=defaults.get(CONF_HA_LOCAL_ROOT, "")): TextSelector(),
        }
    )


class AudiobookshelfKindleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._data: dict[str, Any] = {}
        self._title = DEFAULT_NAME

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AudiobookshelfKindleOptionsFlow:
        """Return options flow."""
        return AudiobookshelfKindleOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle initial setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            try:
                user = await _async_validate(self.hass, data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                user_id = str(user.get("id") or user.get("username") or data[CONF_ABS_URL]).lower()
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                self._title = data.pop(CONF_NAME) or DEFAULT_NAME
                self._data.update(data)
                return await self.async_step_mail()

        schema = _connection_schema({CONF_NAME: DEFAULT_NAME, **(user_input or {})})
        schema = schema.extend({vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector()})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_mail(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect Send to Kindle SMTP settings."""
        if user_input is not None:
            data = dict(user_input)
            data[CONF_SMTP_PORT] = int(data[CONF_SMTP_PORT])
            data[CONF_WEBHOOK_ID] = f"abs_kindle_{secrets.token_urlsafe(24)}"
            self._data.update(data)
            return self.async_create_entry(
                title=self._title,
                data=self._data,
                options={
                    CONF_AUTO_SEND: DEFAULT_AUTO_SEND,
                    CONF_ACCEPTED_FORMATS: DEFAULT_ACCEPTED_FORMATS,
                    CONF_MAX_ATTACHMENT_MB: DEFAULT_MAX_ATTACHMENT_MB,
                    CONF_LOCAL_ABS_ROOT: "",
                    CONF_HA_LOCAL_ROOT: "",
                },
            )
        return self.async_show_form(step_id="mail", data_schema=_mail_schema({}))

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reconfiguration."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            if not user_input.get(CONF_ABS_TOKEN):
                data[CONF_ABS_TOKEN] = entry.data[CONF_ABS_TOKEN]
            try:
                user = await _async_validate(self.hass, data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(user.get("id") or user.get("username") or data[CONF_ABS_URL]).lower())
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(entry.data, token_optional=True),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start reauth."""
        del entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect a new token."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                await _async_validate(self.hass, data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_ABS_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}),
            errors=errors,
        )


class AudiobookshelfKindleOptionsFlow(OptionsFlow):
    """Handle options."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=dict(user_input))
        defaults = {
            CONF_AUTO_SEND: DEFAULT_AUTO_SEND,
            CONF_ACCEPTED_FORMATS: DEFAULT_ACCEPTED_FORMATS,
            CONF_MAX_ATTACHMENT_MB: DEFAULT_MAX_ATTACHMENT_MB,
            CONF_LOCAL_ABS_ROOT: "",
            CONF_HA_LOCAL_ROOT: "",
            **dict(self._entry.options),
        }
        return self.async_show_form(step_id="init", data_schema=_options_schema(defaults))
