"""Config flow for SAJ HS3 / Elekeeper."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
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
    CONF_ENABLE_LOCAL_EMANAGER,
    CONF_ENABLE_OPEN_PLATFORM,
    CONF_ENABLED_SOURCES,
    DOMAIN,
    INTEGRATION_NAME,
    SOURCE_LOCAL_EMANAGER,
    SOURCE_OPEN_PLATFORM,
)


class SAJHS3ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure confirmed read-only data sources."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize flow-local source selection."""
        self._selected_sources: list[str] = []

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Let the user select future data sources."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._selected_sources = []
            if user_input[CONF_ENABLE_LOCAL_EMANAGER]:
                self._selected_sources.append(SOURCE_LOCAL_EMANAGER)
            if user_input[CONF_ENABLE_OPEN_PLATFORM]:
                self._selected_sources.append(SOURCE_OPEN_PLATFORM)

            if not self._selected_sources:
                errors["base"] = "source_required"
            elif SOURCE_OPEN_PLATFORM in self._selected_sources:
                return await self.async_step_open_platform()
            else:
                return await self.async_step_local_emanager()

        schema = vol.Schema(
            {
                vol.Required(CONF_ENABLE_LOCAL_EMANAGER, default=False): bool,
                vol.Required(CONF_ENABLE_OPEN_PLATFORM, default=True): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_open_platform(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Validate confirmed Open Platform credentials and read-only access."""
        errors: dict[str, str] = {}
        if user_input is not None:
            app_id = user_input[CONF_APP_ID].strip()
            app_secret = user_input[CONF_APP_SECRET]
            try:
                await self._async_validate_open_platform(app_id, app_secret)
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
                await self.async_set_unique_id(app_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=INTEGRATION_NAME,
                    data={
                        CONF_ENABLED_SOURCES: self._selected_sources,
                        CONF_APP_ID: app_id,
                        CONF_APP_SECRET: app_secret,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_APP_ID): selector.TextSelector(),
                vol.Required(CONF_APP_SECRET): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="open_platform", data_schema=schema, errors=errors
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Start reauthentication for an existing Open Platform entry."""
        del entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Validate replacement Open Platform credentials."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            app_id = user_input[CONF_APP_ID].strip()
            app_secret = user_input[CONF_APP_SECRET]
            try:
                await self._async_validate_open_platform(app_id, app_secret)
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
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_APP_ID: app_id,
                        CONF_APP_SECRET: app_secret,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_APP_ID,
                    default=reauth_entry.data.get(CONF_APP_ID, ""),
                ): selector.TextSelector(),
                vol.Required(CONF_APP_SECRET): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )

    async def _async_validate_open_platform(
        self,
        app_id: str,
        app_secret: str,
    ) -> None:
        """Authenticate and call exactly one confirmed read-only endpoint."""
        client = SajElekeeperApiClient(
            async_get_clientsession(self.hass),
            app_id,
            app_secret,
        )
        await client.async_authenticate()
        await client.async_get_authorized_plant_count()

    async def async_step_local_emanager(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Create a local architecture placeholder without connection parameters."""
        if user_input is not None:
            return self.async_create_entry(
                title=INTEGRATION_NAME,
                data={CONF_ENABLED_SOURCES: self._selected_sources},
            )

        return self.async_show_form(
            step_id="local_emanager",
            data_schema=vol.Schema({}),
        )
