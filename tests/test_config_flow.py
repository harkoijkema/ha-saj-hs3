"""Config-flow and entry lifecycle tests."""

from __future__ import annotations

import asyncio
from types import MethodType, SimpleNamespace
from typing import Any

from custom_components.saj_hs3 import async_setup_entry, async_unload_entry
from custom_components.saj_hs3.api import SajAuthenticationError
from custom_components.saj_hs3.config_flow import SAJHS3ConfigFlow
from custom_components.saj_hs3.const import (
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_ENABLED_SOURCES,
    SOURCE_OPEN_PLATFORM,
)


async def _validation_success(
    self: SAJHS3ConfigFlow,
    app_id: str,
    app_secret: str,
) -> None:
    del self, app_id, app_secret


async def _validation_failure(
    self: SAJHS3ConfigFlow,
    app_id: str,
    app_secret: str,
) -> None:
    del self, app_id, app_secret
    raise SajAuthenticationError("redacted")


async def _set_unique_id(self: SAJHS3ConfigFlow, unique_id: str) -> None:
    del self, unique_id


def test_config_flow_success() -> None:
    flow = SAJHS3ConfigFlow()
    flow._selected_sources = [SOURCE_OPEN_PLATFORM]
    flow._validate_cloud = MethodType(_validation_success, flow)  # type: ignore[method-assign]
    flow.async_set_unique_id = MethodType(_set_unique_id, flow)  # type: ignore[method-assign]
    flow._abort_if_unique_id_configured = lambda: None  # type: ignore[method-assign]

    result = asyncio.run(
        flow.async_step_open_platform(
            {CONF_APP_ID: " app-id ", CONF_APP_SECRET: "secret"}
        )
    )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_APP_ID] == "app-id"
    assert result["data"][CONF_APP_SECRET] == "secret"


def test_config_flow_auth_failure() -> None:
    flow = SAJHS3ConfigFlow()
    flow._selected_sources = [SOURCE_OPEN_PLATFORM]
    flow._validate_cloud = MethodType(_validation_failure, flow)  # type: ignore[method-assign]

    result = asyncio.run(
        flow.async_step_open_platform(
            {CONF_APP_ID: "app-id", CONF_APP_SECRET: "secret"}
        )
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


class FakeConfigEntries:
    """Minimal config entry manager for setup and unload."""

    def __init__(self) -> None:
        self.forwarded = False
        self.unloaded = False

    async def async_forward_entry_setups(self, entry: Any, platforms: Any) -> None:
        del entry, platforms
        self.forwarded = True

    async def async_unload_platforms(self, entry: Any, platforms: Any) -> bool:
        del entry, platforms
        self.unloaded = True
        return True


def test_setup_and_unload_config_entry(monkeypatch: Any) -> None:
    class FakeCoordinator:
        def __init__(self, hass: Any, entry: Any, api: Any, local: Any) -> None:
            del hass, entry, api
            self.local = local
            self.refreshed = False

        async def async_config_entry_first_refresh(self) -> None:
            self.refreshed = True

    import custom_components.saj_hs3 as integration

    monkeypatch.setattr(integration, "SAJHS3DataUpdateCoordinator", FakeCoordinator)
    monkeypatch.setattr(integration, "async_get_clientsession", lambda hass: object())

    config_entries = FakeConfigEntries()
    hass = SimpleNamespace(config_entries=config_entries)
    entry = SimpleNamespace(
        data={
            CONF_ENABLED_SOURCES: [SOURCE_OPEN_PLATFORM],
            CONF_APP_ID: "app-id",
            CONF_APP_SECRET: "secret",
        },
        runtime_data=None,
    )

    assert asyncio.run(async_setup_entry(hass, entry)) is True
    assert entry.runtime_data.refreshed is True
    assert config_entries.forwarded is True
    assert asyncio.run(async_unload_entry(hass, entry)) is True
    assert config_entries.unloaded is True
