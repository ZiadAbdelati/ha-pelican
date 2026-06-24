"""Switch platform for Pelican Panel: power a server on/off."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PelicanConfigEntry, PelicanCoordinator
from .entity import PelicanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PelicanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the power switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        PelicanPowerSwitch(coordinator, identifier)
        for identifier in coordinator.data
    )


class PelicanPowerSwitch(PelicanEntity, SwitchEntity):
    """Start/stop a server via a switch."""

    _attr_translation_key = "power"

    def __init__(self, coordinator: PelicanCoordinator, identifier: str) -> None:
        super().__init__(coordinator, identifier)
        self._attr_unique_id = f"{identifier}_power"

    @property
    def is_on(self) -> bool:
        return self.data.state in ("running", "starting")

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_power(self._identifier, "start")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_power(self._identifier, "stop")
