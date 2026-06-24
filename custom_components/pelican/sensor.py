"""Sensor platform for Pelican Panel servers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import PelicanData
from .coordinator import PelicanConfigEntry, PelicanCoordinator
from .entity import PelicanEntity


@dataclass(frozen=True, kw_only=True)
class PelicanSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor."""

    value_fn: Callable[[PelicanData], float | int | str | datetime | None]
    attrs_fn: Callable[[PelicanData], dict[str, Any]] | None = None


def _uptime(data: PelicanData) -> datetime | None:
    if data.state != "running" or not data.uptime:
        return None
    return dt_util.utcnow() - timedelta(seconds=data.uptime)


SENSORS: tuple[PelicanSensorDescription, ...] = (
    PelicanSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=["running", "starting", "stopping", "offline"],
        value_fn=lambda d: d.state,
    ),
    PelicanSensorDescription(
        key="cpu",
        translation_key="cpu",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.cpu,
        attrs_fn=lambda d: {"limit": d.cpu_limit},
    ),
    PelicanSensorDescription(
        key="memory",
        translation_key="memory",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.memory,
        attrs_fn=lambda d: {"limit": d.memory_limit},
    ),
    PelicanSensorDescription(
        key="disk",
        translation_key="disk",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.disk,
        attrs_fn=lambda d: {"limit": d.disk_limit},
    ),
    PelicanSensorDescription(
        key="network_rx",
        translation_key="network_rx",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda d: d.network_rx,
    ),
    PelicanSensorDescription(
        key="network_tx",
        translation_key="network_tx",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda d: d.network_tx,
    ),
    PelicanSensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_uptime,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PelicanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pelican sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        PelicanSensor(coordinator, identifier, description)
        for identifier in coordinator.data
        for description in SENSORS
    )


class PelicanSensor(PelicanEntity, SensorEntity):
    """A single Pelican server metric."""

    entity_description: PelicanSensorDescription

    def __init__(
        self,
        coordinator: PelicanCoordinator,
        identifier: str,
        description: PelicanSensorDescription,
    ) -> None:
        super().__init__(coordinator, identifier)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}_{description.key}"

    @property
    def native_value(self) -> float | int | str | datetime | None:
        return self.entity_description.value_fn(self.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.data)
