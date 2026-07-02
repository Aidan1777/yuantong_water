"""Config flow for 源通水务 integration."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, NAME, CONF_WATER_NUMBER, CONF_CODE

_LOGGER = logging.getLogger(__name__)


class SxxhynetConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 源通水务."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=f"{NAME} - {user_input[CONF_WATER_NUMBER]}",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_WATER_NUMBER): str,
                vol.Optional(CONF_CODE): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return SxxhynetOptionsFlowHandler(config_entry)


class SxxhynetOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_WATER_NUMBER,
                    default=self._config_entry.data.get(CONF_WATER_NUMBER, ""),
                ): str,
                vol.Optional(
                    CONF_CODE,
                    default=self._config_entry.data.get(CONF_CODE, ""),
                ): str,
            }),
        )