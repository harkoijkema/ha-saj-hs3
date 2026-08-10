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
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics without credentials, tokens or device identifiers."""
    del hass
    coordinator: SAJHS3DataUpdateCoordinator = entry.runtime_data
    data = coordinator.data
    token_remaining = coordinator.api.token_expires_in if coordinator.api else None
    rounded_token_remaining = (
        max(0, token_remaining // 60 * 60) if token_remaining is not None else None
    )

    return {
        "integration": {
            "domain": DOMAIN,
            "version": INTEGRATION_VERSION,
            "enabled_sources": list(entry.data.get(CONF_ENABLED_SOURCES, [])),
            "credentials_present": {
                "app_id": bool(entry.data.get(CONF_APP_ID)),
                "app_secret": bool(entry.data.get(CONF_APP_SECRET)),
            },
        },
        "coordinator": {
            "source_status": dict(data.source_status),
            "authenticated": data.authenticated,
            "api_reachable": data.api_reachable,
            "token_remaining_seconds_rounded": rounded_token_remaining,
            "authorized_plant_count": data.authorized_plant_count,
            "last_successful_update": data.last_successful_update,
            "last_update_error": data.last_update_error,
            "available_field_count": len(data.fields),
            "model": data.model,
            "device_type": data.device_type,
        },
    }
