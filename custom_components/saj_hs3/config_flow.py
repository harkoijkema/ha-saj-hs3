"""Config flow for SAJ HS3 / Elekeeper."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector

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
    """Configure an explicitly non-communicating alpha entry."""

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
        """Collect confirmed Open Platform credential types without testing them."""
        if user_input is not None:
            return self.async_create_entry(
                title=INTEGRATION_NAME,
                data={
                    CONF_ENABLED_SOURCES: self._selected_sources,
                    CONF_APP_ID: user_input[CONF_APP_ID].strip(),
                    CONF_APP_SECRET: user_input[CONF_APP_SECRET],
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
        return self.async_show_form(step_id="open_platform", data_schema=schema)

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
