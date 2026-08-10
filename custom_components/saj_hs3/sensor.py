"""Prepared sensor metadata for SAJ HS3 / Elekeeper.

No entities are instantiated until a read-only transport produces confirmed
runtime fields.
"""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SOURCE_LOCAL_EMANAGER
from .entity import SAJHS3SensorEntityDescription


def _emsdataid(
    *,
    key: str,
    translation_key: str,
    source_field: str,
    device_class: SensorDeviceClass | None,
    state_class: SensorStateClass | None,
    unit: str | None,
    transform: str = "numeric transport value",
    availability_rule: str = "field present and errCode 0",
) -> SAJHS3SensorEntityDescription:
    """Build metadata only; this function never reads or transforms live data."""
    return SAJHS3SensorEntityDescription(
        key=key,
        translation_key=translation_key,
        device_class=device_class,
        state_class=state_class,
        native_unit_of_measurement=unit,
        source=SOURCE_LOCAL_EMANAGER,
        source_field=source_field,
        transform=transform,
        availability_rule=availability_rule,
    )


# The public alpha deliberately contains no private/research-derived source
# identifiers or register mappings. Confirmed mappings can be introduced later
# only after their publication status and implementation evidence are reviewed.
CANDIDATE_SENSOR_DESCRIPTIONS: tuple[SAJHS3SensorEntityDescription, ...] = ()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load the platform without exposing sensors backed by absent data."""
    del hass, entry, async_add_entities


# Keep imports and exports explicit for static analyzers.
DESCRIPTION_FACTORY: Callable[..., SAJHS3SensorEntityDescription] = _emsdataid
