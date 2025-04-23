import logging
import aiohttp
import asyncio

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant import config_entries
from datetime import timedelta
from typing import Callable, List
from homeassistant.components.climate.const import (
    ClimateEntityFeature
)
from .coordinator import MTMODCoordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity

DOMAIN = "magiqtouch_modbus"
_LOGGER = logging.getLogger(__name__)
MagiqtouchZones = []


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    zone_count = config_entry.data["Zones"]  
    evap_enabled = config_entry.data["Evaporative Unit"]
    heater_enabled = config_entry.data["Heater Unit"]
    
    #Input filters.
    if evap_enabled == False and heater_enabled == False:
        return
    
    if zone_count == 0:
        return
    
    #Determine modes per zone.
    #[HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.FAN_ONLY]
    for ZoneIndex in range(zone_count):
        supportedmodes = [HVACMode.OFF]
        if ZoneIndex == 0: #Evap cooler and fan only controlled by zone 1.
            supportedmodes.append(HVACMode.FAN_ONLY)
            if evap_enabled == True:
                supportedmodes.append(HVACMode.COOL) 
        if heater_enabled == True:
                supportedmodes.append(HVACMode.HEAT)   
        zone_index = ZoneIndex + 1
        zone_entity = MagiqtouchZone(coordinator,config_entry,zone_index,supportedmodes)
        MagiqtouchZones.append(zone_entity)
        
    async_add_entities(MagiqtouchZones)



class MagiqtouchZone(CoordinatorEntity,ClimateEntity):
    def __init__(self,coordinator,config_entry,zone,supportedmodes):
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"magiqtouch_zone_{str(zone)}"
        self.api_url = self._config_entry.data["HVAC URL"]
        
        self.zone = zone
        
        self._attr_name = "Zone " + str(zone)
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_fan_mode = None
        self._attr_fan_modes = [HVACMode.OFF]
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_swing_mode = None
        self._attr_swing_modes = None       
        self._attr_hvac_modes = supportedmodes
        
        self._attr_hvac_mode = HVACMode.OFF

   
    #Command Section
    async def send_hvac_command(self, payload):
        async with aiohttp.ClientSession() as session:
            commandurl = self.api_url + "/command"
            if str(self.api_url).endswith('/') == 1:
                commandurl = self.api_url + "command"
            async with session.post(commandurl, data=payload) as response:
                if response.status != 200:
                    _LOGGER.error(f"Failed to send command {payload}. Server: {commandurl} Response Status: {response.status}")

    #Mode Change.
    async def async_set_hvac_mode(self, new_hvac_mode: str):
        if new_hvac_mode == HVACMode.FAN_ONLY:
            await self.send_hvac_command("mode=0")
        elif new_hvac_mode == HVACMode.FAN_ONLY:
            await self.send_hvac_command("mode=1")
        elif new_hvac_mode == HVACMode.COOL:
            await self.send_hvac_command("mode=2")
        elif new_hvac_mode == HVACMode.HEAT:
            await self.send_hvac_command("mode=4")
            await self.send_hvac_command(f"zone{self.zone}=on")

        if new_hvac_mode == HVACMode.OFF:
            await self.send_hvac_command("power=off")
        else:
            await self.send_hvac_command("power=on")
        
         

    async def async_set_fan_mode(self, new_fan_mode: str):  
        if self.coordinator.data == None:
            return
        systemmode = self.coordinator.data.get('system_mode')
        #Automatic Temperature
        if systemmode == 2:
            if new_fan_mode == "Temperature":
                command = "mode=3"
                await self.send_hvac_command(command)
                return
        #Manual Fan Speed
        elif systemmode == 3:
            if new_fan_mode != "Temperature": #Swap mode from Auto.
                command = "mode=2"
                await self.send_hvac_command(command)
        command = f"fanspeed={new_fan_mode}"         
        await self.send_hvac_command(command)
        
    
        
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
        

    async def async_set_swing_mode(self, swing_mode: str):
        if swing_mode == "Zone Open":
            await self.send_hvac_command(f"zone{self.zone}=on")        
        elif swing_mode == "Zone Closed":
            await self.send_hvac_command(f"zone{self.zone}=off")            
        elif swing_mode == "External":
            await self.send_hvac_command("mode=0")
        elif swing_mode == "Recycle":
            await self.send_hvac_command("mode=1")

  
        
        
    @property
    def unique_id(self):
        return self._attr_unique_id
     
    @property
    def device_info(self):
        return {
        "identifiers": {(DOMAIN, self.api_url)},
        "name": "Magiqtouch Modbus Controller",
        "model": "Modbus ESP32 Interface",
        }   
       
       
    @property
    def supported_features(self) -> int:
        return ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.SWING_MODE

    @property
    def hvac_mode(self):
        if self.coordinator.data == None:
            return None
        systemmode = self.coordinator.data.get('system_mode')
        hvacmode = None
        if self.coordinator.data.get('system_power') == 0:
            hvacmode = HVACMode.OFF
        elif systemmode == 0:
            hvacmode = HVACMode.FAN_ONLY
        elif systemmode == 1:
            #return "Fan (Recycle)"
            hvacmode = HVACMode.FAN_ONLY
        elif systemmode == 2:
            #return "Cooler"   
            hvacmode = HVACMode.COOL
        elif systemmode == 3:
            #return "Cooler (Auto)"
            hvacmode = HVACMode.COOL
        elif systemmode == 4:
            #return "Heater"
            hvacmode = HVACMode.HEAT
        
        if hvacmode not in self._attr_hvac_modes:        
            return HVACMode.OFF #Mode not in the modes list - return OFF.

        self._attr_hvac_mode = hvacmode        
        return hvacmode


    #Swing mode used for heater zone enable/disable
    @property
    def swing_mode(self):
        if self.coordinator.data == None:
            return None
        if self._attr_swing_modes == None:
            return None
        systemmode = self.coordinator.data.get('system_mode')   
        systempower = self.coordinator.data.get('system_power')        
        if systempower == 0:
            return None
        
        if self._attr_hvac_mode == HVACMode.HEAT:
            heatzonepower = self.coordinator.data.get(f"heater_zone{self.zone}_enabled")
            if heatzonepower == 0:
                return "Zone Closed"
            elif heatzonepower == 1:
                return "Zone Open"
        elif self._attr_hvac_mode == HVACMode.FAN_ONLY and HVACMode.COOL in self._attr_hvac_modes and HVACMode.HEAT in self._attr_hvac_modes:
            if systemmode == 0:
                return "External"
            elif systemmode == 1:
                return "Recycle"  
        if self._attr_swing_modes != None: #Returning None when list swing will not support it.
            zoneliststring = ", ".join(self._attr_swing_modes)
            _LOGGER.warning(f"Swing Mode Set to None while system mode = {systemmode} and list of available modes is still {zoneliststring}")
        return None        

    @property
    def swing_modes(self):
        if self.coordinator.data == None:
            return None
        systempower = self.coordinator.data.get('system_power')
        if systempower == 0:
            return None
        systemmode = self.coordinator.data.get('system_mode')
        if systemmode == 4:
            self._attr_swing_modes = ["Zone Closed","Zone Open"]
            return self._attr_swing_modes
        elif HVACMode.COOL in self._attr_hvac_modes and HVACMode.HEAT in self._attr_hvac_modes: #Only show if both Cooler and Heater available.
            if systemmode == 0 or systemmode == 1:
                self._attr_swing_modes = ["External","Recycle"]
                return self._attr_swing_modes
        self._attr_swing_modes = None
        return self._attr_swing_modes
    

    #Fan Settings.

    @property
    def fan_modes(self):
        if self.coordinator.data == None:
            return None
        systemmode = self.coordinator.data.get('system_mode')
        systempower = self.coordinator.data.get('system_power')
        FAN_MODES = ["1","2","3","4","5","6","7","8","9","10"]
        if systemmode == 4 or systempower == 0:
            return None
        elif systemmode == 2 or systemmode == 3:
            #Cooler Modes - add Temperature to Fan speed options.
            return ["Temperature"] + FAN_MODES
        self._attr_fan_modes = FAN_MODES
        return FAN_MODES

    @property
    def fan_mode(self):
        if self.coordinator.data == None:
            return None
        if self._attr_fan_modes == None:
            _LOGGER.warning("Cannot return fan mode as no Fan Modes are set.")
            return None
            
        coolerfanspeed = self.coordinator.data.get('evap_fanspeed')
        heaterfanspeed = self.coordinator.data.get('heater_fanspeed')
        systemmode = self.coordinator.data.get('system_mode')
        currentfanspeed = None
        skip_log_mode_swap = False
        #if coolerfanspeed == 0 and heaterfanspeed == 0: #System is Off.
        #    return None 
        if systemmode == 0:
            if coolerfanspeed > 0:
                currentfanspeed = str(coolerfanspeed)
            else:
                skip_log_mode_swap = True
                currentfanspeed = "1" #Min fan speed for mode swaps.
        elif systemmode == 1: #Recycle Fan, use heater fanspeed.
            if heaterfanspeed > 0:
                currentfanspeed = str(heaterfanspeed)
            else:
                skip_log_mode_swap = True
                currentfanspeed = "1" #Min fan speed, occurs when swapping to mode.
        elif systemmode == 2:
            if coolerfanspeed > 0:
                currentfanspeed = str(coolerfanspeed)
            else:
                skip_log_mode_swap = True
                currentfanspeed = "1" #Account for the auto-mode having 0 State, increase to 1 as minimum speed.           
        elif systemmode == 3: #Cooler Temperature Mode
            currentfanspeed = "Temperature"
        elif systemmode == 4 and heaterfanspeed > 0:
            self._attr_fan_mode = None
            return self._attr_fan_mode #No Fan Speed Modes for Heater.
                
        #Log changes for Manual speed adjustment on primary zone.
        if skip_log_mode_swap == False and self.zone == 1:
            if currentfanspeed != None and currentfanspeed != self._attr_fan_mode:
                oldspeed = self._attr_fan_mode
                if oldspeed == None:
                    oldspeed = "None"
                #_LOGGER.warning(f"fan speed changed from {oldspeed} to {currentfanspeed}")
                self.hass.bus.async_fire("magiqtouch_fan_speed_changed_2", {
                "name": self._attr_name,
                "entity_id": self.entity_id,
                "oldspeed": oldspeed,
                "newspeed": currentfanspeed,
                })
            self._attr_fan_mode = currentfanspeed
        #if currentfanspeed == None:
        #    _LOGGER.warning(f"fan speed is set to none systemmode = {systemmode} cfs = {coolerfanspeed} hfs = {heaterfanspeed}")
        return currentfanspeed
        
    #Temperature.

    @property
    def target_temperature(self):
        if self.coordinator.data == None:
            return None
        systemmode = self.coordinator.data.get('system_mode')    
        if self.zone == 1:
            self._attr_target_temperature = self.coordinator.data.get('target_temp')
        else:
            targetzonekey = "target_temp_zone" + str(self.zone)
            self._attr_target_temperature = self.coordinator.data.get(targetzonekey)
        if self.hvac_mode is None:
            return None
        if self.hvac_mode == HVACMode.FAN_ONLY or self.hvac_mode == HVACMode.OFF:
            return None
        elif systemmode == 2:
            return None
        return self._attr_target_temperature

    @property
    def current_temperature(self):
        if self.coordinator.data == None:
            return None
        systemmode = self.coordinator.data.get('system_mode')        
        tempzonekey = "zone" + str(self.zone) + "_temp_sensor"
        self._attr_current_temperature = self.coordinator.data.get(tempzonekey)
        if systemmode is None:
            return None
        if systemmode <= 2 and self.zone == 1:
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
        
