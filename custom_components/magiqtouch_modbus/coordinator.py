import requests
import aiohttp
import asyncio 
import logging  

from datetime import timedelta

from aiohttp import ClientError, ClientTimeout

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
        self.lastresult = None
        self.failcount = 0

    async def _async_update(self):
        timeout = ClientTimeout(total=4)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.url) as response:
                    response.raise_for_status()
                    self.lastresult = await response.json(content_type=None) #(content_type=None) Forces acceptance of the text/html
                    self.failcount = 0
                    return self.lastresult
        except (ClientError, asyncio.TimeoutError) as ex:
            _LOGGER.error("Error getting status from HVAC Magiqtouch Modbus Interface: %s", ex)
            if self.failcount < 5:
                self.failcount += 1
                return self.lastresult
            return None            
        