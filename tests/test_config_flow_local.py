"""Offline config-flow tests for local eManager selection."""

from __future__ import annotations

import asyncio
from types import MethodType, SimpleNamespace
from typing import Any

from custom_components.saj_hs3.config_flow import SAJHS3ConfigFlow, _is_emanager
from custom_components.saj_hs3.const import (
    CONF_BLUETOOTH_ADDRESS,
    CONF_EMANAGER_NAME,
    CONF_ENABLED_SOURCES,
    SOURCE_LOCAL_EMANAGER,
)


def test_emanager_identity_filter() -> None:
    assert _is_emanager("eManager:TEST123")
    assert not _is_emanager("eManager:")
    assert not _is_emanager("unrelated")
    assert not _is_emanager(None)


def test_bluetooth_confirmation_supplies_name_placeholder() -> None:
    flow = SAJHS3ConfigFlow()
    flow._discovery = SimpleNamespace(address="test-address", name="eManager:TEST123")

    result = asyncio.run(flow.async_step_bluetooth_confirm())

    assert result["type"] == "form"
    assert result["description_placeholders"] == {"name": "eManager:TEST123"}


def test_bluetooth_confirmation_has_safe_generic_name() -> None:
    flow = SAJHS3ConfigFlow()

    result = asyncio.run(flow.async_step_bluetooth_confirm())

    assert result["description_placeholders"] == {"name": "eManager"}


async def _set_unique_id(self: SAJHS3ConfigFlow, unique_id: str) -> None:
    assert unique_id == "local:test-address"


def test_local_selection_creates_entry(monkeypatch: Any) -> None:
    flow = SAJHS3ConfigFlow()
    flow._selected_sources = [SOURCE_LOCAL_EMANAGER]
    flow.hass = SimpleNamespace()
    flow.async_set_unique_id = MethodType(_set_unique_id, flow)  # type: ignore[method-assign]
    flow._abort_if_unique_id_configured = lambda: None  # type: ignore[method-assign]
    info = SimpleNamespace(address="test-address", name="eManager:TEST123")
    monkeypatch.setattr(
        "custom_components.saj_hs3.config_flow.bluetooth.async_discovered_service_info",
        lambda hass, connectable: [info],
    )

    result = asyncio.run(
        flow.async_step_local_emanager({CONF_BLUETOOTH_ADDRESS: "test-address"})
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_ENABLED_SOURCES] == [SOURCE_LOCAL_EMANAGER]
    assert result["data"][CONF_EMANAGER_NAME] == "eManager:TEST123"


def test_local_selection_reports_no_discovered_device(monkeypatch: Any) -> None:
    flow = SAJHS3ConfigFlow()
    flow.hass = SimpleNamespace()
    monkeypatch.setattr(
        "custom_components.saj_hs3.config_flow.bluetooth.async_discovered_service_info",
        lambda hass, connectable: [],
    )

    result = asyncio.run(flow.async_step_local_emanager())
    assert result["type"] == "form"
    assert result["errors"] == {"base": "no_devices_found"}


def test_remote_proxy_discovery_is_not_tied_to_a_host_adapter(monkeypatch: Any) -> None:
    """A connectable advertisement from any HA scanner is selectable."""
    flow = SAJHS3ConfigFlow()
    flow._selected_sources = [SOURCE_LOCAL_EMANAGER]
    flow.hass = SimpleNamespace()
    flow.async_set_unique_id = MethodType(_set_unique_id, flow)  # type: ignore[method-assign]
    flow._abort_if_unique_id_configured = lambda: None  # type: ignore[method-assign]
    proxy_info = SimpleNamespace(
        address="test-address",
        name="eManager:TEST123",
        source="remote-esphome-proxy",
    )
    monkeypatch.setattr(
        "custom_components.saj_hs3.config_flow.bluetooth.async_discovered_service_info",
        lambda hass, connectable: [proxy_info] if connectable else [],
    )

    result = asyncio.run(
        flow.async_step_local_emanager({CONF_BLUETOOTH_ADDRESS: "test-address"})
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_BLUETOOTH_ADDRESS] == "test-address"


def test_best_entry_is_deduplicated_across_multiple_scanners(monkeypatch: Any) -> None:
    """HA's aggregated discovery result yields one stable device identity."""
    flow = SAJHS3ConfigFlow()
    flow.hass = SimpleNamespace()
    infos = [
        SimpleNamespace(
            address="test-address",
            name="eManager:TEST123",
            source="host-scanner",
        ),
        SimpleNamespace(
            address="test-address",
            name="eManager:TEST123",
            source="remote-esphome-proxy",
        ),
    ]
    monkeypatch.setattr(
        "custom_components.saj_hs3.config_flow.bluetooth.async_discovered_service_info",
        lambda hass, connectable: infos,
    )

    result = asyncio.run(flow.async_step_local_emanager())

    assert result["data_schema"]({CONF_BLUETOOTH_ADDRESS: "test-address"}) == {
        CONF_BLUETOOTH_ADDRESS: "test-address"
    }
