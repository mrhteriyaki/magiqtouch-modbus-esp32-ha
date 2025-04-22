import requests
import aiohttp
import asyncio 
import logging  

from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

DOMAIN = "magiqtouch_modbus"
_LOGGER = logging.getLogger(__name__)

class MTMODCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config_entry):
        super().__init__(
            hass,
            logger=_LOGGER,  # your logger
            name="MTMOD Coordinator",
            update_method=self._async_update,
            update_interval=timedelta(seconds=1),
        )
        self.entry = config_entry
        self.url = config_entry.data["HVAC URL"]
        
    async def _async_update(self):
        # Fetch and return data from your API
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        _LOGGER.error(f"Error fetching HVAC status response code: {response.status}")
        except requests.RequestException as ex:
            _LOGGER.error("Error getting status from HVAC Magiqtouch Modbus Interface: %s", ex)
        