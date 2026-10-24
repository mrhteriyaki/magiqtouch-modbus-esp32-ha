from typing import Any

import voluptuous as vol
from aiohttp import ClientError, ClientTimeout

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_EVAP, CONF_HEATER, CONF_URL, CONF_ZONES, DOMAIN, MAX_ZONES

REQUEST_TIMEOUT = ClientTimeout(total=10)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_URL, default=defaults.get(CONF_URL, vol.UNDEFINED)): str,  # User enters API URL
        vol.Required(CONF_ZONES, default=defaults.get(CONF_ZONES, 1)): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_ZONES)),
        vol.Required(CONF_EVAP, default=defaults.get(CONF_EVAP, True)): bool,
        vol.Required(CONF_HEATER, default=defaults.get(CONF_HEATER, True)): bool,
    })


class MagiqtouchModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 2

    async def _async_validate(self, user_input: dict[str, Any]) -> dict[str, str]:
        user_input[CONF_URL] = user_input[CONF_URL].strip().rstrip("/")
        if not user_input[CONF_URL].startswith(("http://", "https://")):
            return {CONF_URL: "invalid_url"}
        if not user_input[CONF_EVAP] and not user_input[CONF_HEATER]:
            return {"base": "no_units"}
        # Test if API is reachable
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(user_input[CONF_URL], timeout=REQUEST_TIMEOUT) as resp:
                if resp.status != 200:
                    return {"base": "cannot_connect"}
        except (ClientError, TimeoutError, ValueError):
            return {"base": "cannot_connect"}
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._async_validate(user_input)
            if not errors:
                await self.async_set_unique_id(user_input[CONF_URL])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="MagiqTouch Modbus", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema(user_input or {}), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._async_validate(user_input)
            if not errors:
                url = user_input[CONF_URL]
                if any(other.entry_id != entry.entry_id and other.unique_id == url for other in self._async_current_entries()):
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(entry, unique_id=url, data_updates=user_input)

        return self.async_show_form(step_id="reconfigure", data_schema=_schema(user_input or dict(entry.data)), errors=errors)
