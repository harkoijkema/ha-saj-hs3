"""SAJ HS3 / Elekeeper integration."""

from __future__ import annotations

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SajElekeeperApiClient
from .const import (
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_BLUETOOTH_ADDRESS,
    CONF_EMANAGER_NAME,
    CONF_ENABLED_SOURCES,
    SOURCE_LOCAL_EMANAGER,
    SOURCE_OPEN_PLATFORM,
)
from .coordinator import SAJHS3DataUpdateCoordinator
from .local_client import SajLocalClient

PLATFORMS: tuple[Platform, ...] = (Platform.SENSOR,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up configured, strictly read-only sources."""
    sources = entry.data.get(CONF_ENABLED_SOURCES, [])
    api = None
    if SOURCE_OPEN_PLATFORM in sources:
        api = SajElekeeperApiClient(
            async_get_clientsession(hass),
            entry.data[CONF_APP_ID],
            entry.data[CONF_APP_SECRET],
        )

    local = None
    if SOURCE_LOCAL_EMANAGER in sources:
        address = entry.data[CONF_BLUETOOTH_ADDRESS]
        name = entry.data[CONF_EMANAGER_NAME]
        local = SajLocalClient(
            lambda: bluetooth.async_ble_device_from_address(
                hass, address, connectable=True
            ),
            address,
            name,
            lambda: (
                service_info.source
                if (
                    service_info := bluetooth.async_last_service_info(
                        hass, address, connectable=True
                    )
                )
                else None
            ),
        )

    coordinator = SAJHS3DataUpdateCoordinator(hass, entry, api, local)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: SAJHS3DataUpdateCoordinator = entry.runtime_data
    if coordinator.local is not None:
        await coordinator.local.async_close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
