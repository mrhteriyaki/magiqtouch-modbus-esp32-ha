import logging

from datetime import timedelta
from typing import Any

from aiohttp import ClientError, ClientTimeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = ClientTimeout(total=4)
#Consecutive failed polls where the last status is kept before entities go unavailable.
MAX_FAILURES = 5

type MagiqtouchConfigEntry = ConfigEntry[MTMODCoordinator]


class MTMODCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, config_entry: MagiqtouchConfigEntry):
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name="MTMOD Coordinator",
            update_interval=timedelta(seconds=1),
        )
        self.url = config_entry.data[CONF_URL].rstrip("/")
        self.session = async_get_clientsession(hass)
        self.failcount = 0

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            async with self.session.get(self.url, timeout=REQUEST_TIMEOUT) as response:
                response.raise_for_status()
                data = await response.json(content_type=None) #(content_type=None) Forces acceptance of the text/html
        except (ClientError, TimeoutError, ValueError) as ex:
            self.failcount += 1
            if self.data is not None and self.failcount <= MAX_FAILURES:
                _LOGGER.debug("Status poll %s failed, keeping last status: %s", self.failcount, ex)
                return self.data
            raise UpdateFailed(f"Error getting status from HVAC Magiqtouch Modbus Interface: {ex}") from ex
        self.failcount = 0
        return data

    async def async_send_command(self, payload: str) -> None:
        commandurl = self.url + "/command"
        try:
            async with self.session.post(commandurl, data=payload, timeout=REQUEST_TIMEOUT) as response:
                response.raise_for_status()
        except (ClientError, TimeoutError) as ex:
            raise HomeAssistantError(f"Failed to send command {payload} to {commandurl}: {ex}") from ex
