"""Shared entity models for confirmed SAJ data."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription


@dataclass(frozen=True, kw_only=True)
class SAJHS3SensorEntityDescription(SensorEntityDescription):
    """Describe a normalized, evidence-backed read-only field."""

    source: str
    source_field: str
    evidence: str
    availability_field: str | None = None
    device_role: str = "emanager"
