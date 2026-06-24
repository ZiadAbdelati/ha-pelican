"""Data update coordinator for the Pelican Panel integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    PelicanAuthError,
    PelicanClient,
    PelicanConnectionError,
    PelicanData,
    PelicanError,
)

SCAN_INTERVAL = timedelta(seconds=60)
_LOGGER = logging.getLogger(__name__)

type PelicanConfigEntry = ConfigEntry[PelicanCoordinator]


class PelicanCoordinator(DataUpdateCoordinator[dict[str, PelicanData]]):
    """Polls a Pelican panel for all servers the API key can access."""

    config_entry: PelicanConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: PelicanConfigEntry
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=config_entry.data[CONF_URL],
            config_entry=config_entry,
            update_interval=SCAN_INTERVAL,
        )
        self.base_url = config_entry.data[CONF_URL].rstrip("/")
        self.client = PelicanClient(
            async_get_clientsession(hass),
            self.base_url,
            config_entry.data[CONF_API_KEY],
        )

    async def _async_update_data(self) -> dict[str, PelicanData]:
        try:
            servers = await self.client.async_get_servers()
            result: dict[str, PelicanData] = {}
            for server in servers:
                identifier = server["identifier"]
                resources = await self.client.async_get_utilization(identifier)
                result[identifier] = PelicanData.from_api(server, resources)
            return result
        except PelicanAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PelicanConnectionError as err:
            raise UpdateFailed(str(err)) from err

    async def async_send_power(self, identifier: str, signal: str) -> None:
        """Send a power signal (user action), then refresh entities.

        Raises HomeAssistantError so a failed switch/button action surfaces a
        clean error in the UI. A genuine auth failure is handled by the next
        coordinator poll, which triggers reauth.
        """
        try:
            await self.client.async_send_power(identifier, signal)
        except PelicanError as err:
            raise HomeAssistantError(
                f"Failed to send '{signal}' to server {identifier}: {err}"
            ) from err
        await self.async_request_refresh()
