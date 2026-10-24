from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_EVAP, CONF_HEATER, CONF_ZONES, DOMAIN, EVENT_FAN_SPEED_CHANGED
from .coordinator import MagiqtouchConfigEntry, MTMODCoordinator

#system_mode values reported by the module.
MODE_FAN_EXTERNAL = 0
MODE_FAN_RECYCLE = 1
MODE_COOLER_MANUAL = 2
MODE_COOLER_AUTO = 3
MODE_HEATER = 4

FAN_SPEEDS = [str(speed) for speed in range(1, 11)]
FAN_MODE_TEMPERATURE = "Temperature"

SWING_ZONE_OPEN = "Zone Open"
SWING_ZONE_CLOSED = "Zone Closed"
SWING_EXTERNAL = "External"
SWING_RECYCLE = "Recycle"

UNREPORTED_TEMPERATURE = 157 #Default temperature when sensor not reported.


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MagiqtouchConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = config_entry.runtime_data
    zone_count = config_entry.data[CONF_ZONES]
    evap_enabled = config_entry.data[CONF_EVAP]
    heater_enabled = config_entry.data[CONF_HEATER]

    #Input filters.
    if not evap_enabled and not heater_enabled:
        return

    #Determine modes per zone.
    zones: list[MagiqtouchZone] = []
    for zone in range(1, zone_count + 1):
        if zone == 1: #Evap cooler and fan only controlled by zone 1.
            supportedmodes = [HVACMode.OFF, HVACMode.FAN_ONLY]
            if evap_enabled:
                supportedmodes.append(HVACMode.COOL)
            if heater_enabled:
                supportedmodes.append(HVACMode.HEAT)
            zones.append(MagiqtouchMainZone(coordinator, config_entry, zone, supportedmodes))
        elif heater_enabled: #Zones 2+ are heater zones only.
            zones.append(MagiqtouchHeaterZone(coordinator, config_entry, zone, [HVACMode.OFF, HVACMode.HEAT]))

    async_add_entities(zones)


class MagiqtouchZone(CoordinatorEntity[MTMODCoordinator], ClimateEntity):
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS #HA < 2026.11
    _attr_precision = PRECISION_WHOLE
    _attr_target_temperature_step = 1.0
    _attr_min_temp = 0
    _attr_max_temp = 28

    def __init__(self, coordinator: MTMODCoordinator, config_entry: MagiqtouchConfigEntry, zone: int, supportedmodes: list[HVACMode]):
        super().__init__(coordinator)
        self.zone = zone
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone}"
        self._attr_name = f"Zone {zone}"
        self._attr_hvac_modes = supportedmodes
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="Magiqtouch ESP32 Controller",
            model="Modbus ESP32 Interface",
            configuration_url=coordinator.url,
        )
        self._current_temperature: float | None = None
        self._target_temperature: float | None = None
        self._update_from_data()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_from_data()
        super()._handle_coordinator_update()

    def _update_from_data(self) -> None:
        raise NotImplementedError

    @property
    def native_current_temperature(self) -> float | None:
        return self._current_temperature

    current_temperature = native_current_temperature #HA < 2026.11

    @property
    def native_target_temperature(self) -> float | None:
        return self._target_temperature

    target_temperature = native_target_temperature #HA < 2026.11

    def _read_current_temperature(self) -> float | None:
        temperature = self.coordinator.data.get(f"zone{self.zone}_temp_sensor")
        if temperature == UNREPORTED_TEMPERATURE:
            return None
        return temperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(hvac_mode)
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        zoneprefix = "" if self.zone == 1 else str(self.zone)
        await self.coordinator.async_send_command(f"temp{zoneprefix}={round(temperature)}")


class MagiqtouchMainZone(MagiqtouchZone):
    """Zone 1, controls the system power, mode and fan speed."""

    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.SWING_MODE
    )

    def __init__(self, *args: Any):
        self._logged_fan_speed: str | None = None
        super().__init__(*args)

    @callback
    def _handle_coordinator_update(self) -> None:
        previous_speed = self._logged_fan_speed
        super()._handle_coordinator_update()
        #Log changes for Manual speed adjustment on primary zone.
        if self._logged_fan_speed != previous_speed:
            self.hass.bus.async_fire(EVENT_FAN_SPEED_CHANGED, {
                "name": self.name,
                "entity_id": self.entity_id,
                "oldspeed": previous_speed or "None",
                "newspeed": self._logged_fan_speed,
            })

    def _update_from_data(self) -> None:
        data = self.coordinator.data
        systemmode = data.get("system_mode")
        systempower = data.get("system_power")
        both_units = HVACMode.COOL in self.hvac_modes and HVACMode.HEAT in self.hvac_modes

        #Mode.
        hvacmode = None
        if systempower == 0:
            hvacmode = HVACMode.OFF
        elif systemmode in (MODE_FAN_EXTERNAL, MODE_FAN_RECYCLE):
            hvacmode = HVACMode.FAN_ONLY
        elif systemmode in (MODE_COOLER_MANUAL, MODE_COOLER_AUTO):
            hvacmode = HVACMode.COOL
        elif systemmode == MODE_HEATER:
            hvacmode = HVACMode.HEAT
        if hvacmode not in self.hvac_modes:
            hvacmode = HVACMode.OFF #Mode not in the modes list - return OFF.
        self._attr_hvac_mode = hvacmode

        #Temperature.
        self._target_temperature = None
        if hvacmode not in (HVACMode.FAN_ONLY, HVACMode.OFF) and systemmode != MODE_COOLER_MANUAL:
            self._target_temperature = data.get("target_temp")
        self._current_temperature = None
        if systemmode is not None and systemmode > MODE_COOLER_MANUAL:
            self._current_temperature = self._read_current_temperature()

        #Swing mode used for heater zone open/closed and fan external/recycle.
        self._attr_swing_modes = None
        self._attr_swing_mode = None
        if systempower != 0:
            if hvacmode == HVACMode.HEAT:
                self._attr_swing_modes = [SWING_ZONE_CLOSED, SWING_ZONE_OPEN]
                heatzonepower = data.get(f"heater_zone{self.zone}_enabled")
                if heatzonepower == 0:
                    self._attr_swing_mode = SWING_ZONE_CLOSED
                elif heatzonepower == 1:
                    self._attr_swing_mode = SWING_ZONE_OPEN
            elif hvacmode == HVACMode.FAN_ONLY and both_units: #Only show if both Cooler and Heater available.
                self._attr_swing_modes = [SWING_EXTERNAL, SWING_RECYCLE]
                self._attr_swing_mode = SWING_EXTERNAL if systemmode == MODE_FAN_EXTERNAL else SWING_RECYCLE

        #Fan Settings.
        self._attr_fan_modes = None
        self._attr_fan_mode = None
        if systempower == 0 or systemmode == MODE_HEATER:
            return #No Fan Speed Modes for Heater.
        if systemmode in (MODE_COOLER_MANUAL, MODE_COOLER_AUTO):
            #Cooler Modes - add Temperature to Fan speed options.
            self._attr_fan_modes = [FAN_MODE_TEMPERATURE, *FAN_SPEEDS]
        else:
            self._attr_fan_modes = FAN_SPEEDS

        if systemmode == MODE_COOLER_AUTO: #Cooler Temperature Mode
            self._attr_fan_mode = FAN_MODE_TEMPERATURE
        else:
            #Recycle Fan uses heater fanspeed.
            fanspeed = data.get("heater_fanspeed" if systemmode == MODE_FAN_RECYCLE else "evap_fanspeed") or 0
            if fanspeed <= 0:
                #Speed reads 0 while swapping modes, show the min fan speed and don't log it.
                self._attr_fan_mode = FAN_SPEEDS[0]
                return
            self._attr_fan_mode = str(fanspeed)
        self._logged_fan_speed = self._attr_fan_mode

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.FAN_ONLY:
            await self.coordinator.async_send_command(f"mode={MODE_FAN_EXTERNAL}")
        elif hvac_mode == HVACMode.COOL:
            await self.coordinator.async_send_command(f"mode={MODE_COOLER_MANUAL}")
        elif hvac_mode == HVACMode.HEAT:
            await self.coordinator.async_send_command(f"mode={MODE_HEATER}")
            await self.coordinator.async_send_command(f"zone{self.zone}=on")

        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        await self.coordinator.async_send_command("power=on")

    async def async_turn_off(self) -> None:
        await self.coordinator.async_send_command("power=off")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        systemmode = self.coordinator.data.get("system_mode")
        #Automatic Temperature
        if fan_mode == FAN_MODE_TEMPERATURE:
            if systemmode != MODE_COOLER_AUTO:
                await self.coordinator.async_send_command(f"mode={MODE_COOLER_AUTO}")
            return
        #Manual Fan Speed
        if systemmode == MODE_COOLER_AUTO: #Swap mode from Auto.
            await self.coordinator.async_send_command(f"mode={MODE_COOLER_MANUAL}")
        await self.coordinator.async_send_command(f"fanspeed={fan_mode}")

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        if swing_mode == SWING_ZONE_OPEN:
            await self.coordinator.async_send_command(f"zone{self.zone}=on")
        elif swing_mode == SWING_ZONE_CLOSED:
            await self.coordinator.async_send_command(f"zone{self.zone}=off")
        elif swing_mode == SWING_EXTERNAL:
            await self.coordinator.async_send_command(f"mode={MODE_FAN_EXTERNAL}")
        elif swing_mode == SWING_RECYCLE:
            await self.coordinator.async_send_command(f"mode={MODE_FAN_RECYCLE}")


class MagiqtouchHeaterZone(MagiqtouchZone):
    """Zones 2+, on/off opens/closes the zone. Selecting heat while the system isn't heating switches the whole system to heat."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def _system_heating(self) -> bool:
        data = self.coordinator.data
        return data.get("system_power") != 0 and data.get("system_mode") == MODE_HEATER

    def _update_from_data(self) -> None:
        data = self.coordinator.data
        heating = self._system_heating()
        zone_open = data.get(f"heater_zone{self.zone}_enabled") == 1
        self._attr_hvac_mode = HVACMode.HEAT if heating and zone_open else HVACMode.OFF
        #Target stays adjustable while the zone is closed.
        self._target_temperature = data.get(f"target_temp_zone{self.zone}") if heating else None
        self._current_temperature = None
        if data.get("system_mode") is not None:
            self._current_temperature = self._read_current_temperature()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_send_command(f"zone{self.zone}=off")
        elif hvac_mode == HVACMode.HEAT:
            if self._system_heating():
                await self.coordinator.async_send_command(f"zone{self.zone}=on")
                return
            await self.coordinator.async_send_command(f"mode={MODE_HEATER}")
            await self.coordinator.async_send_command(f"zone{self.zone}=on")
            await self.coordinator.async_send_command("power=on")

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)
