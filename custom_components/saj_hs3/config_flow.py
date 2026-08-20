"""Config flow for SAJ HS3 / Elekeeper."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SajApiError,
    SajAppDisabledError,
    SajAuthenticationError,
    SajConnectionError,
    SajElekeeperApiClient,
    SajRateLimitError,
)
from .const import (
    CONF_APP_ID,
    CONF_APP_SECRET,
    CONF_BLUETOOTH_ADDRESS,
    CONF_EMANAGER_NAME,
    CONF_ENABLE_LOCAL_EMANAGER,
    CONF_ENABLE_OPEN_PLATFORM,
    CONF_ENABLED_SOURCES,
    DOMAIN,
    EMANAGER_LOCAL_NAME_PREFIX,
    INTEGRATION_NAME,
    SOURCE_LOCAL_EMANAGER,
    SOURCE_OPEN_PLATFORM,
)


class SAJHS3ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure local eManager and optional Open Platform access."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        self._selected_sources: list[str] = []
        self._entry_data: dict[str, Any] = {}
        self._discovery: BluetoothServiceInfoBleak | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select one or both independent read-only sources."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._selected_sources = [
                source
                for enabled, source in (
                    (user_input[CONF_ENABLE_LOCAL_EMANAGER], SOURCE_LOCAL_EMANAGER),
                    (user_input[CONF_ENABLE_OPEN_PLATFORM], SOURCE_OPEN_PLATFORM),
                )
                if enabled
            ]
            if not self._selected_sources:
                errors["base"] = "source_required"
            elif SOURCE_OPEN_PLATFORM in self._selected_sources:
                return await self.async_step_open_platform()
            else:
                return await self.async_step_local_emanager()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENABLE_LOCAL_EMANAGER, default=True): bool,
                    vol.Required(CONF_ENABLE_OPEN_PLATFORM, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle HA-native discovery of a connectable eManager."""
        if not _is_emanager(discovery_info.name):
            return self.async_abort(reason="not_emanager")
        await self.async_set_unique_id(f"local:{discovery_info.address}")
        self._abort_if_unique_id_configured()
        self._selected_sources = [SOURCE_LOCAL_EMANAGER]
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered local eManager."""
        if user_input is not None:
            assert self._discovery is not None
            return self._create_local_entry(
                self._discovery.address, self._discovery.name
            )
        discovered_name = (
            self._discovery.name
            if self._discovery is not None and self._discovery.name
            else "eManager"
        )
        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"name": discovered_name},
        )

    async def async_step_open_platform(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the live-confirmed cloud authentication and plant-list call."""
        errors: dict[str, str] = {}
        if user_input is not None:
            app_id, app_secret = (
                user_input[CONF_APP_ID].strip(),
                user_input[CONF_APP_SECRET],
            )
            try:
                await self._validate_cloud(app_id, app_secret)
            except SajAppDisabledError:
                errors["base"] = "app_not_enabled"
            except SajAuthenticationError:
                errors["base"] = "invalid_auth"
            except SajConnectionError:
                errors["base"] = "cannot_connect"
            except SajRateLimitError:
                errors["base"] = "rate_limited"
            except SajApiError:
                errors["base"] = "unknown"
            except Exception:
                errors["base"] = "unknown"
            else:
                self._entry_data.update(
                    {CONF_APP_ID: app_id, CONF_APP_SECRET: app_secret}
                )
                if SOURCE_LOCAL_EMANAGER in self._selected_sources:
                    return await self.async_step_local_emanager()
                await self.async_set_unique_id(f"cloud:{app_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=INTEGRATION_NAME,
                    data={
                        CONF_ENABLED_SOURCES: self._selected_sources,
                        **self._entry_data,
                    },
                )
        return self.async_show_form(
            step_id="open_platform",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_APP_ID): selector.TextSelector(),
                    vol.Required(CONF_APP_SECRET): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start Open Platform reauthentication."""
        del entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and replace rejected cloud credentials."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            app_id = user_input[CONF_APP_ID].strip()
            app_secret = user_input[CONF_APP_SECRET]
            try:
                await self._validate_cloud(app_id, app_secret)
            except SajAppDisabledError:
                errors["base"] = "app_not_enabled"
            except SajAuthenticationError:
                errors["base"] = "invalid_auth"
            except (SajConnectionError, SajRateLimitError):
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_APP_ID: app_id, CONF_APP_SECRET: app_secret},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_APP_ID, default=entry.data.get(CONF_APP_ID, "")
                    ): selector.TextSelector(),
                    vol.Required(CONF_APP_SECRET): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_local_emanager(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a currently discovered, connectable eManager."""
        devices = {
            info.address: info.name
            for info in bluetooth.async_discovered_service_info(
                self.hass, connectable=True
            )
            if _is_emanager(info.name)
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_BLUETOOTH_ADDRESS]
            if address not in devices:
                errors["base"] = "device_unavailable"
            else:
                await self.async_set_unique_id(f"local:{address}")
                self._abort_if_unique_id_configured()
                return self._create_local_entry(address, devices[address])
        if not devices:
            errors["base"] = "no_devices_found"
        return self.async_show_form(
            step_id="local_emanager",
            data_schema=vol.Schema(
                {vol.Required(CONF_BLUETOOTH_ADDRESS): vol.In(devices)}
            ),
            errors=errors,
        )

    def _create_local_entry(self, address: str, name: str) -> ConfigFlowResult:
        return self.async_create_entry(
            title=f"SAJ eManager ({name.removeprefix(EMANAGER_LOCAL_NAME_PREFIX)})",
            data={
                CONF_ENABLED_SOURCES: self._selected_sources,
                CONF_BLUETOOTH_ADDRESS: address,
                CONF_EMANAGER_NAME: name,
                **self._entry_data,
            },
        )

    async def _validate_cloud(self, app_id: str, app_secret: str) -> None:
        client = SajElekeeperApiClient(
            async_get_clientsession(self.hass), app_id, app_secret
        )
        await client.async_authenticate()
        await client.async_get_authorized_plant_count()


def _is_emanager(name: str | None) -> bool:
    return bool(
        name
        and name.startswith(EMANAGER_LOCAL_NAME_PREFIX)
        and name.removeprefix(EMANAGER_LOCAL_NAME_PREFIX).strip()
    )
