"""Privacy-safe diagnostics for SAJ HS3 / Elekeeper."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_ENABLED_SOURCES,
    DOMAIN,
    INTEGRATION_VERSION,
)
from .coordinator import SAJHS3DataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return status without addresses, identifiers, credentials or raw values."""
    del hass
    coordinator: SAJHS3DataUpdateCoordinator = entry.runtime_data
    remaining = coordinator.api.token_expires_in if coordinator.api else None
    return {
        "integration": {
            "domain": DOMAIN,
            "version": INTEGRATION_VERSION,
            "enabled_sources": list(entry.data.get(CONF_ENABLED_SOURCES, [])),
            "cloud_credentials_present": {
                "app_id": bool(entry.data.get(CONF_APP_ID)),
                "app_secret": bool(entry.data.get(CONF_APP_SECRET)),
            },
        },
        "coordinator": {
            "source_status": dict(coordinator.data.source_status),
            "last_successful_update": coordinator.data.last_successful_update,
            "available_field_count": len(coordinator.data.fields),
            "authenticated": coordinator.data.authenticated,
            "api_reachable": coordinator.data.api_reachable,
            "token_remaining_seconds_rounded": remaining // 60 * 60
            if remaining is not None
            else None,
            "authorized_plant_count": coordinator.data.authorized_plant_count,
            "local_connection_source": coordinator.local.last_connection_source
            if coordinator.local
            else None,
            "local_cycle": coordinator.local.cycle_diagnostics
            if coordinator.local
            else None,
        },
    }
