"""Binary sensor platform for Pelican Panel: server running state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PelicanConfigEntry, PelicanCoordinator
from .entity import PelicanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PelicanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the running binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        PelicanRunningSensor(coordinator, identifier)
        for identifier in coordinator.data
    )


class PelicanRunningSensor(PelicanEntity, BinarySensorEntity):
    """Reports whether a server is running."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "running"

    def __init__(self, coordinator: PelicanCoordinator, identifier: str) -> None:
        super().__init__(coordinator, identifier)
        self._attr_unique_id = f"{identifier}_running"

    @property
    def is_on(self) -> bool:
        return self.data.state == "running"
