"""Button platform for Pelican Panel: power signals."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PelicanConfigEntry, PelicanCoordinator
from .entity import PelicanEntity


@dataclass(frozen=True, kw_only=True)
class PelicanButtonDescription(ButtonEntityDescription):
    """Button description carrying the power signal to send."""

    signal: str


BUTTONS: tuple[PelicanButtonDescription, ...] = (
    PelicanButtonDescription(key="start", translation_key="start", signal="start"),
    PelicanButtonDescription(key="stop", translation_key="stop", signal="stop"),
    PelicanButtonDescription(
        key="restart",
        translation_key="restart",
        device_class=ButtonDeviceClass.RESTART,
        signal="restart",
    ),
    PelicanButtonDescription(key="kill", translation_key="kill", signal="kill"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PelicanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the power buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        PelicanButton(coordinator, identifier, description)
        for identifier in coordinator.data
        for description in BUTTONS
    )


class PelicanButton(PelicanEntity, ButtonEntity):
    """Sends a single power signal when pressed."""

    entity_description: PelicanButtonDescription

    def __init__(
        self,
        coordinator: PelicanCoordinator,
        identifier: str,
        description: PelicanButtonDescription,
    ) -> None:
        super().__init__(coordinator, identifier)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}_{description.key}"

    async def async_press(self) -> None:
        await self.coordinator.async_send_power(
            self._identifier, self.entity_description.signal
        )
