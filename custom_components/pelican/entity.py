"""Base entity for the Pelican Panel integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PelicanData
from .const import DOMAIN
from .coordinator import PelicanCoordinator


class PelicanEntity(CoordinatorEntity[PelicanCoordinator]):
    """Base class for entities tied to a single Pelican server."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PelicanCoordinator, identifier: str) -> None:
        super().__init__(coordinator)
        self._identifier = identifier
        # Entities are only created for identifiers present in coordinator.data
        # (after the coordinator's first refresh), so this lookup is safe.
        server = coordinator.data[identifier]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, server.uuid)},
            name=server.name,
            manufacturer="Pelican",
            model="Game Server",
            configuration_url=f"{coordinator.base_url}/server/{identifier}",
        )

    @property
    def data(self) -> PelicanData:
        """Current data for this server."""
        return self.coordinator.data[self._identifier]

    @property
    def available(self) -> bool:
        """Return True only while this server is still present in the data."""
        return super().available and self._identifier in self.coordinator.data
