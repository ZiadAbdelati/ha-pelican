"""The Pelican Panel integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import PelicanConfigEntry, PelicanCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: PelicanConfigEntry) -> bool:
    """Set up Pelican Panel from a config entry."""
    coordinator = PelicanCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


async def _async_reload_on_update(
    hass: HomeAssistant, entry: PelicanConfigEntry
) -> None:
    """Reload the entry when options change (applies the new scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PelicanConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
