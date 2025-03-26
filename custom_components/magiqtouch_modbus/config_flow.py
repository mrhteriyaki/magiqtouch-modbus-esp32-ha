import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

DOMAIN = "magiqtouch_modbus"

#Requirements.
CONFIG_SCHEMA = vol.Schema({
    vol.Required("HVAC URL"): str,  # User enters API URL
    vol.Required("Zones",default=1): int,
    vol.Required("Evaporative Unit",default=True): bool,
    vol.Required("Heater Unit",default=True): bool,
})

class MagiqtouchModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Test if API is reachable
            session = aiohttp_client.async_get_clientsession(self.hass)
            try:
                async with session.get(user_input["HVAC URL"]) as resp:
                    if resp.status != 200:
                        errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(title="MagiqTouch Modbus", data=user_input)

        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA, errors=errors)
    