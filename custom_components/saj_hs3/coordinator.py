"""Coordinator state for the non-communicating alpha shell."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    COMMUNICATION_NOT_IMPLEMENTED,
    CONF_ENABLED_SOURCES,
    INTEGRATION_NAME,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SAJHS3CoordinatorData:
    """Non-sensitive integration status; it contains no invented device data."""

    fields: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    source_status: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    model: str | None = None
    device_type: str | None = None
    last_successful_update: str | None = None


class SAJHS3DataUpdateCoordinator(DataUpdateCoordinator[SAJHS3CoordinatorData]):
    """Hold alpha status without polling any local or cloud source."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize without scheduling updates or making requests."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=INTEGRATION_NAME,
            update_interval=None,
        )
        enabled_sources = entry.data.get(CONF_ENABLED_SOURCES, [])
        self.data = SAJHS3CoordinatorData(
            source_status=MappingProxyType(
                {source: COMMUNICATION_NOT_IMPLEMENTED for source in enabled_sources}
            )
        )

    async def _async_update_data(self) -> SAJHS3CoordinatorData:
        """Return local alpha status; deliberately perform no I/O."""
        return self.data
