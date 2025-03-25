import logging
import aiohttp
import asyncio

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant import config_entries
from datetime import timedelta
#from .magiqtouchmodbus import MagiqtouchModbus
from typing import Callable, List
from homeassistant.components.climate.const import (
    ClimateEntityFeature
)


_LOGGER = logging.getLogger(__name__)

HVAC_MODES = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.FAN_ONLY]

SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_entry(hass, config_entry, async_add_entities):

    #mtmodbussystem: MagiqtouchModbus = MagiqtouchModbus()
    #set zone list.
    zone_count = config_entry.data["zone_count"]

    async_add_entities(
        [MagiqtouchZone(config_entry,ZoneIndex + 1) for ZoneIndex in range(zone_count)]
    )


async def fetch_hvac_status(api_url: str) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Error fetching HVAC status: {response.status}")
    except Exception as e:
        raise Exception(f"Failed to fetch data from HVAC server: {str(e)}")


class MagiqtouchZone(ClimateEntity):
    def __init__(
        self, 
        config_entry,
        zone
        ):
        self._config_entry = config_entry
        self.api_url = self._config_entry.data["api_url"]  # Get the API URL from the config entry        
        self.zone = zone
        self._attr_name = "MagiqTouch Zone " + str(zone)
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_mode = None
        self._attr_hvac_modes = HVAC_MODES
        self._attr_fan_mode = None
        self._attr_fan_modes = []
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self.systemmode = None

    #Stats update.
    async def async_update(self):
        data = await fetch_hvac_status(self.api_url)
        #self._attr_power_state = "on" if data.get('system_power') == 1 else "off"
        self.systemmode = data.get('system_mode')
        self._attr_hvac_mode = self._map_mode(self.systemmode, data.get('system_power'))

        #cooler mode - temp mode
        if self.systemmode == 3:
            self._attr_fan_mode = "Temperature"
        else:
            self._attr_fan_mode = self._map_fanspeed(data.get('evap_fanspeed'),data.get('heater_fanspeed'))

        tempzonekey = "zone" + str(self.zone) + "_temp_sensor"
        self._attr_current_temperature = data.get(tempzonekey)
        if self.zone == 1:
            self._attr_target_temperature = data.get('target_temp')
        else:
            targetzonekey = "target_temp_zone" + str(self.zone)
            self._attr_target_temperature = data.get(targetzonekey)

        self.async_write_ha_state()
        
    
    #Command Section
    async def send_hvac_command(self, payload):
        async with aiohttp.ClientSession() as session:
            commandurl = self.api_url + "/command"
            if str(self.api_url).endswith('/') == 1:
                commandurl = self.api_url + "command"
            async with session.post(commandurl, data=payload) as response:
                if response.status == 200:
                    self.async_write_ha_state()
                else:
                    _LOGGER.error(f"Failed to send command {payload}. Server: {commandurl} Response Status: {response.status}")
        await asyncio.sleep(2)  # Wait for 2 second for command to update on controller before calling update.
        await self.async_update_ha_state(force_refresh=True)

    #Mode Change.
    async def async_set_hvac_mode(self, new_hvac_mode: str):
        if new_hvac_mode == HVACMode.FAN_ONLY:
            await self.send_hvac_command("mode=0")
        elif new_hvac_mode == HVACMode.COOL:
            await self.send_hvac_command("mode=2")
        elif new_hvac_mode == HVACMode.HEAT:
            await self.send_hvac_command("mode=4")

        if new_hvac_mode == HVACMode.OFF:
            await self.send_hvac_command("power=off")
        else:
            await self.send_hvac_command("power=on")
         
        


    async def async_set_fan_mode(self, new_fan_mode: str):  
        command = f"fanspeed={new_fan_mode}" 
        if self.systemmode == 2: #If on manual mode and temperature selected, change command to mode change.
            if new_fan_mode == "Temperature":
                command = "mode=3"
        self._attr_fan_mode = new_fan_mode
        await self.send_hvac_command(command)
        self.async_write_ha_state()
    
        
    async def async_turn_on(self):
        await self.send_hvac_command("power=on")

    async def async_turn_off(self):
        await self.send_hvac_command("power=off")


    async def async_set_temperature(self, **kwargs):
        zoneprefix = str(self.zone)
        if self.zone == 1:
            zoneprefix = ""
        bodytext = "temp" + zoneprefix + "=" + str(int(kwargs.get("temperature")))
        await self.send_hvac_command(bodytext)
        self.async_write_ha_state()


    def _map_mode(self, mode, system_power):
        # Mapping system mode to Home Assistant modes
        if system_power == 0:
            return HVACMode.OFF
        elif mode == 0:
            return HVACMode.FAN_ONLY
        elif mode == 1:
            #return "Fan (Recycle)"
            return HVACMode.FAN_ONLY
        elif mode == 2:
            #return "Cooler"   
            return HVACMode.COOL
        elif mode == 3:
            #return "Cooler (Auto)"
            return HVACMode.COOL
        elif mode == 4:
            #return "Heater"
            return HVACMode.HEAT
        return None

    def _map_fanspeed(self, coolerfanspeed,heaterfanspeed):
        if self._attr_hvac_mode == HVACMode.HEAT:
            return heaterfanspeed
        return coolerfanspeed

    #@property
    #def unique_id(self) -> str:
        #return uid
        
    @property
    def supported_features(self) -> int:
        return ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF

    @property
    def hvac_mode(self):
        return self._attr_hvac_mode


    #Fan Settings.

    @property
    def fan_modes(self):
        FAN_MODES = ["1","2","3","4","5","6","7","8","9","10"]

        if self.hvac_mode == HVACMode.HEAT or self.hvac_mode == HVACMode.OFF:
            return None
        if self.hvac_mode == HVACMode.COOL:
            return ["Temperature"] + FAN_MODES
        return FAN_MODES

    @property
    def fan_mode(self):
        return str(self._attr_fan_mode)

    #Temperature.

    @property
    def target_temperature(self):
        if self.hvac_mode == HVACMode.FAN_ONLY or self.hvac_mode == HVACMode.OFF:
            return None
        elif self.systemmode == 2:
            return None
        return self._attr_target_temperature

    @property
    def current_temperature(self):
        if self.systemmode <= 2 and self.zone == 1:
            return None
        elif self._attr_current_temperature == 157: #Default temperature when code not reported.
            return None
        return self._attr_current_temperature;
    
    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS;

    @property
    def precision(self):
        return 1.0;

    @property
    def target_temperature_step(self):
        return 1.0


    @property
    def max_temp(self):
        return 28


    @property
    def min_temp(self):
        return 0