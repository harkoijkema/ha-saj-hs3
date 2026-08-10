"""SAJ HS3 / Elekeeper alpha integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SajElekeeperApiClient
from .const import (
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_ENABLED_SOURCES,
    SOURCE_OPEN_PLATFORM,
)
from .coordinator import SAJHS3DataUpdateCoordinator

PLATFORMS: tuple[Platform, ...] = (Platform.SENSOR,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up confirmed read-only communication for configured sources."""
    enabled_sources = entry.data.get(CONF_ENABLED_SOURCES, [])
    api = None
    if SOURCE_OPEN_PLATFORM in enabled_sources:
        api = SajElekeeperApiClient(
            async_get_clientsession(hass),
            entry.data[CONF_APP_ID],
            entry.data[CONF_APP_SECRET],
        )

    coordinator = SAJHS3DataUpdateCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
