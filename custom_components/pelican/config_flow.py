"""Config flow for the Pelican Panel integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PelicanAuthError, PelicanClient, PelicanConnectionError
from .const import DOMAIN

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_URL): str, vol.Required(CONF_API_KEY): str}
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class PelicanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Pelican Panel config flow."""

    async def _validate(self, url: str, api_key: str) -> dict[str, str]:
        """Return an errors dict ({} means success)."""
        client = PelicanClient(async_get_clientsession(self.hass), url, api_key)
        errors: dict[str, str] = {}
        try:
            await client.async_get_servers()
        except PelicanAuthError:
            errors["base"] = "invalid_auth"
        except PelicanConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            errors["base"] = "unknown"
        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            errors = await self._validate(url, user_input[CONF_API_KEY])
            if not errors:
                return self.async_create_entry(
                    title=url,
                    data={CONF_URL: url, CONF_API_KEY: user_input[CONF_API_KEY]},
                )
        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            errors = await self._validate(
                reauth_entry.data[CONF_URL], user_input[CONF_API_KEY]
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"url": reauth_entry.data[CONF_URL]},
            errors=errors,
        )
