"""Central coordinator for local and cloud read-only sources."""

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
    CONF_ENABLED_SOURCES,
    INTEGRATION_NAME,
    LOCAL_UPDATE_INTERVAL_SECONDS,
    SOURCE_LOCAL_EMANAGER,
    SOURCE_OPEN_PLATFORM,
)
from .local_client import SajLocalClient, SajLocalConnectionError
from .local_protocol import SajLocalProtocolError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SAJHS3CoordinatorData:
    """Privacy-safe normalized coordinator data."""

    fields: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    source_status: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    last_successful_update: str | None = None
    authenticated: bool = False
    api_reachable: bool = False
    authorized_plant_count: int | None = None


class SAJHS3DataUpdateCoordinator(DataUpdateCoordinator[SAJHS3CoordinatorData]):
    """Serialize local reads and retain the proven cloud health check."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: SajElekeeperApiClient | None,
        local: SajLocalClient | None,
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=entry,
            name=INTEGRATION_NAME,
            update_interval=timedelta(
                seconds=LOCAL_UPDATE_INTERVAL_SECONDS if local else 3600
            ),
        )
        self.api = api
        self.local = local
        self.enabled_sources = tuple(entry.data.get(CONF_ENABLED_SOURCES, []))
        self.data = SAJHS3CoordinatorData(
            source_status=MappingProxyType(
                {source: "configured" for source in self.enabled_sources}
            )
        )

    async def _async_update_data(self) -> SAJHS3CoordinatorData:
        fields: dict[str, Any] = dict(self.data.fields)
        statuses = dict(self.data.source_status)
        plant_count = self.data.authorized_plant_count
        api_reachable = self.data.api_reachable

        if self.local is not None:
            try:
                fields.update(await self.local.async_read_confirmed_fields())
                statuses[SOURCE_LOCAL_EMANAGER] = "connected"
            except (SajLocalConnectionError, SajLocalProtocolError) as err:
                statuses[SOURCE_LOCAL_EMANAGER] = "unavailable"
                stage = (
                    err.stage
                    if isinstance(err, SajLocalConnectionError)
                    else self.local.cycle_diagnostics["stage"]
                )
                raise UpdateFailed(
                    f"Local eManager temporarily unavailable during {stage}"
                ) from err

        if self.api is not None:
            try:
                plant_count = await self.api.async_get_authorized_plant_count()
                statuses[SOURCE_OPEN_PLATFORM] = "connected"
                api_reachable = True
            except SajAppDisabledError as err:
                raise UpdateFailed("SAJ developer app is not released") from err
            except SajAuthenticationError as err:
                raise ConfigEntryAuthFailed("SAJ authentication failed") from err
            except (SajConnectionError, SajRateLimitError, SajApiError) as err:
                statuses[SOURCE_OPEN_PLATFORM] = "unavailable"
                if self.local is None:
                    raise UpdateFailed("SAJ Open Platform update failed") from err

        return SAJHS3CoordinatorData(
            fields=MappingProxyType(fields),
            source_status=MappingProxyType(statuses),
            last_successful_update=datetime.now(UTC).isoformat(),
            authenticated=self.api.is_authenticated if self.api else False,
            api_reachable=api_reachable,
            authorized_plant_count=plant_count,
        )
