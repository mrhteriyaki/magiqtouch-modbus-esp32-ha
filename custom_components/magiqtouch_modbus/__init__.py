from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from .coordinator import MTMODCoordinator

DOMAIN = "magiqtouch_modbus"
PLATFORMS = ["climate"]

async def async_setup(hass: HomeAssistant, config: dict):
    return True  # Only needed for legacy YAML config

async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry):
    coordinator = MTMODCoordinator(hass, config)
    hass.data.setdefault(DOMAIN, {})[config.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)   
    return True

async def async_unload_entry(hass: HomeAssistant, config: ConfigEntry):
    return await hass.config_entries.async_unload_platforms(config, PLATFORMS)