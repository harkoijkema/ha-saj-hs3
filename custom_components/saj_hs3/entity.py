"""Shared entity description model for future confirmed SAJ data points."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DEVICE_ROLE_NAMES, DOMAIN, SAJHS3DeviceRole


@dataclass(frozen=True, kw_only=True)
class SAJHS3SensorEntityDescription(SensorEntityDescription):
    """Describe provenance and interpretation of a confirmed data point."""

    source: str
    source_field: str
    transform: str
    availability_rule: str


@dataclass(frozen=True, slots=True)
class SAJHS3DeviceDescriptor:
    """Describe a device only after a source supplies a reliable identifier."""

    role: SAJHS3DeviceRole
    identifier: str | None
    model: str | None = None
    via_identifier: str | None = None


def device_info_from_descriptor(
    descriptor: SAJHS3DeviceDescriptor,
) -> DeviceInfo | None:
    """Build DeviceInfo only when evidence supplied a stable identifier."""
    if descriptor.identifier is None:
        return None

    device_info = DeviceInfo(
        identifiers={(DOMAIN, descriptor.identifier)},
        manufacturer="SAJ",
        name=DEVICE_ROLE_NAMES[descriptor.role],
        model=descriptor.model,
    )
    if descriptor.via_identifier is not None:
        device_info["via_device"] = (DOMAIN, descriptor.via_identifier)
    return device_info
