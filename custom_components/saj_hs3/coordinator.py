"""Coordinator for confirmed read-only SAJ sources."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SajApiError,
    SajAppDisabledError,
    SajAuthenticationError,
    SajConnectionError,
    SajElekeeperApiClient,
    SajRateLimitError,
)
from .const import (
    COMMUNICATION_NOT_IMPLEMENTED,
    CONF_ENABLED_SOURCES,
    INTEGRATION_NAME,
    OPEN_PLATFORM_UPDATE_INTERVAL_SECONDS,
    SOURCE_OPEN_PLATFORM,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SAJHS3CoordinatorData:
    """Non-sensitive runtime status without raw API resources."""

    fields: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    source_status: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    model: str | None = None
    device_type: str | None = None
    last_successful_update: str | None = None
    authenticated: bool = False
    api_reachable: bool = False
    authorized_plant_count: int | None = None
    last_update_error: str | None = None


class SAJHS3DataUpdateCoordinator(DataUpdateCoordinator[SAJHS3CoordinatorData]):
    """Poll exactly one confirmed read-only Open Platform endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: SajElekeeperApiClient | None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=entry,
            name=INTEGRATION_NAME,
            update_interval=timedelta(seconds=OPEN_PLATFORM_UPDATE_INTERVAL_SECONDS)
            if api is not None
            else None,
        )
        self.api = api
        enabled_sources = entry.data.get(CONF_ENABLED_SOURCES, [])
        source_status = {
            source: (
                "configured"
                if source == SOURCE_OPEN_PLATFORM
                else COMMUNICATION_NOT_IMPLEMENTED
            )
            for source in enabled_sources
        }
        self.data = SAJHS3CoordinatorData(source_status=MappingProxyType(source_status))

    async def _async_update_data(self) -> SAJHS3CoordinatorData:
        """Refresh only the confirmed authorized-plant count."""
        if self.api is None:
            return self.data

        try:
            plant_count = await self.api.async_get_authorized_plant_count()
        except SajAppDisabledError as err:
            raise UpdateFailed("SAJ developer app is not released") from err
        except SajAuthenticationError as err:
            raise ConfigEntryAuthFailed("SAJ authentication failed") from err
        except SajConnectionError as err:
            raise UpdateFailed("Unable to reach the SAJ Open Platform") from err
        except SajRateLimitError as err:
            raise UpdateFailed("SAJ Open Platform rate limit reached") from err
        except SajApiError as err:
            raise UpdateFailed("SAJ Open Platform update failed") from err

        source_status = dict(self.data.source_status)
        source_status[SOURCE_OPEN_PLATFORM] = "connected"
        return SAJHS3CoordinatorData(
            fields=self.data.fields,
            source_status=MappingProxyType(source_status),
            last_successful_update=datetime.now(UTC).isoformat(),
            authenticated=self.api.is_authenticated,
            api_reachable=True,
            authorized_plant_count=plant_count,
        )
