"""Constants for the Pelican Panel integration."""

from homeassistant.const import Platform

DOMAIN = "pelican"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
]
