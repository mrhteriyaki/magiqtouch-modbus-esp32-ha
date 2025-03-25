from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN

DOMAIN = "magiqtouch_modbus"

PLATFORMS = ["climate"]

async def async_setup(hass: HomeAssistant, config: dict):
    return True  # Only needed for legacy YAML config

async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry):
    #api_url = config.data["api_url"]  # Retrieve the API URL from config entry
    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)   
    return True

async def async_unload_entry(hass: HomeAssistant, config: ConfigEntry):
    return await hass.config_entries.async_unload_platforms(config, PLATFORMS)